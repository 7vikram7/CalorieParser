import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.core.clients import GROQ_MODEL, groq_client
from app.core.config import settings
from app.core.usda import search_usda_foods

logger = logging.getLogger(__name__)

PARSE_SYSTEM_PROMPT = """Split the user's meal description into a list of individual
food items. Preserve quantity words exactly as given (e.g. "2 rotis", not just
"rotis") so portion size information isn't lost. Keep each item short - a simple
food name, not a full sentence.

Respond with JSON only, matching: {"items": ["item1", "item2", ...]}"""

ESTIMATE_SYSTEM_PROMPT = """You are a professional nutritionist AI. You will be given
a meal's individual food items, and for each item, standardized per-100g USDA
nutrition data if a good match was found (some items may have none - use your own
knowledge for those). Combine them into a single nutritional estimate for the whole
meal, using the USDA data to ground your portion/calorie assumptions wherever it's
available.

Be realistic. If you're not confident, lower the confidence score rather than
guessing wildly. If the previous attempt's validation feedback is included, fix
those specific problems.

Respond with a single JSON object with exactly these fields:
- name: short descriptive name for the meal
- serving_size_value: numeric amount (e.g. 1.0, 200.0)
- serving_size_unit: unit string (e.g. "serving", "ml", "g", "piece")
- calories: integer total kcal for the whole meal
- protein_g: grams of protein (decimal)
- carbs_g: grams of carbohydrates (decimal)
- fat_g: grams of fat (decimal)
- confidence: float 0.0-1.0 - higher if grounded in real USDA data, lower if
  estimated from general knowledge alone
- notes: string with any caveats, assumptions, or clarifications (null if none)"""

# Retries are for a validation *failure* (the estimate came back with
# implausible numbers), not a transport/API failure - those propagate as
# exceptions out of run_meal_estimate_pipeline() and are handled by the
# fallback chain in llm.py's estimate_grounded(), not retried here.
MAX_VALIDATION_RETRIES = 2


class MealEstimateState(TypedDict):
    description: str
    parsed_items: list[str]
    usda_data: dict[str, list[dict]]
    estimate: dict
    validation_errors: list[str]
    retries: int


def _timed(name: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(state: MealEstimateState) -> dict:
            start = time.monotonic()
            result = fn(state)
            logger.info("agents.%s took %.2fs", name, time.monotonic() - start)
            return result

        return wrapper

    return decorator


@_timed("parse")
def _parse_meal(state: MealEstimateState) -> dict:
    """Agent 1: split the description into individual food items via Groq."""
    response = groq_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": PARSE_SYSTEM_PROMPT},
            {"role": "user", "content": state["description"]},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    data = json.loads(response.choices[0].message.content)
    items = [item.strip() for item in data.get("items", []) if isinstance(item, str) and item.strip()]
    if not items:
        # Groq returned nothing usable - fall back to treating the whole
        # description as one item rather than researching/estimating
        # against an empty list.
        items = [state["description"]]
    logger.info("agents.parse: %r -> %r", state["description"], items)
    return {"parsed_items": items}


@_timed("research")
def _research_items(state: MealEstimateState) -> dict:
    """Agent 2: look up each parsed item in USDA FoodData Central. No LLM -
    pure API calls, run concurrently since search_usda_foods is a blocking
    HTTP request and this endpoint's latency already matters (see Phase 3b
    learnings).
    """
    items = state["parsed_items"]
    with ThreadPoolExecutor(max_workers=len(items)) as pool:
        results = list(pool.map(lambda item: search_usda_foods(settings.USDA_API_KEY, item), items))
    usda_data = dict(zip(items, results))
    matched = sum(1 for r in results if r)
    logger.info("agents.research: %d/%d items matched in USDA", matched, len(items))
    return {"usda_data": usda_data}


def _format_usda_context(usda_data: dict[str, list[dict]]) -> str:
    lines = []
    for item, results in usda_data.items():
        if results:
            top = results[0]
            lines.append(
                f"- {item}: USDA reference \"{top['description']}\" - "
                f"{top['calories_per_100g']} kcal, {top['protein_g_per_100g']}g protein, "
                f"{top['carbs_g_per_100g']}g carbs, {top['fat_g_per_100g']}g fat per 100g"
            )
        else:
            lines.append(f"- {item}: no USDA match, use your own knowledge")
    return "\n".join(lines)


@_timed("estimate")
def _estimate_nutrition(state: MealEstimateState) -> dict:
    """Agent 3: combine parsed items + USDA data (+ prior validation
    feedback, if this is a retry) into a final estimate via Groq."""
    user_message = (
        f"Original meal description: {state['description']}\n\n"
        f"Parsed items with USDA reference data where available:\n{_format_usda_context(state['usda_data'])}"
    )
    if state["validation_errors"]:
        user_message += "\n\nYour previous attempt had these problems - fix them:\n" + "\n".join(
            f"- {e}" for e in state["validation_errors"]
        )

    response = groq_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": ESTIMATE_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    data = json.loads(response.choices[0].message.content)
    logger.info("agents.estimate (attempt %d): %r", state["retries"] + 1, data)
    return {"estimate": data}


@_timed("validate")
def _validate_estimate(state: MealEstimateState) -> dict:
    """Agent 4: rules-based sanity checks, no LLM. Checks the estimate's
    macros roughly add up to its calorie count and that nothing is
    negative or wildly out of range for a single meal.
    """
    data = state["estimate"]
    errors: list[str] = []
    try:
        calories = float(data["calories"])
        protein = float(data["protein_g"])
        carbs = float(data["carbs_g"])
        fat = float(data["fat_g"])
    except (KeyError, TypeError, ValueError):
        errors.append("Missing or non-numeric calories/protein_g/carbs_g/fat_g fields.")
        logger.warning("agents.validate: FAILED (malformed estimate): %s", errors)
        return {"validation_errors": errors, "retries": state["retries"] + 1}

    if any(v < 0 for v in (calories, protein, carbs, fat)):
        errors.append("No macro or calorie value may be negative.")
    if not (0 < calories <= 5000):
        errors.append(f"Calories ({calories}) is outside a plausible range (0-5000) for a single meal.")

    macro_calories = protein * 4 + carbs * 4 + fat * 9
    if macro_calories > 0:
        diff_ratio = abs(macro_calories - calories) / macro_calories
        if diff_ratio > 0.35:
            errors.append(
                f"Reported calories ({calories}) don't roughly match the macros "
                f"(protein*4 + carbs*4 + fat*9 = {macro_calories:.0f}), off by {diff_ratio:.0%}."
            )

    if errors:
        logger.warning("agents.validate: FAILED (attempt %d): %s", state["retries"] + 1, errors)
        return {"validation_errors": errors, "retries": state["retries"] + 1}

    logger.info("agents.validate: passed")
    return {"validation_errors": []}


def _should_retry(state: MealEstimateState) -> str:
    if state["validation_errors"] and state["retries"] <= MAX_VALIDATION_RETRIES:
        return "retry"
    return "done"


def _build_graph():
    graph = StateGraph(MealEstimateState)
    graph.add_node("parse", _parse_meal)
    graph.add_node("research", _research_items)
    graph.add_node("estimate", _estimate_nutrition)
    graph.add_node("validate", _validate_estimate)
    graph.set_entry_point("parse")
    graph.add_edge("parse", "research")
    graph.add_edge("research", "estimate")
    graph.add_edge("estimate", "validate")
    graph.add_conditional_edges("validate", _should_retry, {"retry": "estimate", "done": END})
    return graph.compile()


_meal_estimate_graph = _build_graph()


def run_meal_estimate_pipeline(description: str) -> dict:
    """Runs the parse -> research -> estimate -> validate graph for a
    single meal description and returns the final estimate dict, even if
    validation never fully passed (best-effort - the last attempt is still
    a reasonable answer, and letting a persistent validation failure raise
    would just push this endpoint into the fallback chain for no good
    reason when it already has a usable, if imperfect, estimate).
    """
    result = _meal_estimate_graph.invoke(
        {
            "description": description,
            "parsed_items": [],
            "usda_data": {},
            "estimate": {},
            "validation_errors": [],
            "retries": 0,
        }
    )
    return result["estimate"]
