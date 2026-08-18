# Dish-Level Meal Logging — Plan

> Status: **Implemented and deployed (2026-08-18).** User approved the
> direction, asked for a written plan first (this doc), then gave the
> explicit go-ahead with a refined version of this plan. Verified against
> real Groq/USDA calls before shipping - see `docs/learning-log.md` Level
> 13 for what that verification actually found, including a dramatic
> accuracy improvement on the exact meal that motivated this work (953/
> 2953 kcal instability → a stable ~904-963 kcal, with the model now
> explicitly catching and disregarding bad USDA matches per item).

## Problem

Reported directly by the user, with a real example:

```
1 scoop whey isolate, 100gm dragon fruit, 50gm pear, 75gm guava,
300ml skmmied milk coffee which had 1tbsp sugar, 75gm mix grain puffs,
50gm steam matki, 30salted peanuts
```

→ "Protein-rich fruit & grain snack with milk coffee", 953 kcal, 60%
confidence. Re-running the *identical* description live gave **2953
kcal** the second time — a ~3x swing on the same input.

Two compounding problems, confirmed directly (not guessed at):

**1. USDA grounding data is frequently wrong, not just imprecise.**
`backend/app/core/usda.py`'s keyword search against USDA's Foundation/SR
Legacy dataset — small and US-centric — returns confidently wrong top
matches for anything even slightly regional or prepared:

| Query | Top USDA match | Reality |
|---|---|---|
| dragon fruit | **Candied fruit**, 322 kcal/100g | fresh fruit, ~60 kcal/100g |
| guava | **Guava pastries**, 380 kcal/100g | real match buried 3rd, 68 kcal/100g |
| skimmed milk coffee | **Chocolate-coated coffee candy**, 550 kcal/100g | a beverage, not candy |
| steamed matki | **Steamed corn (Navajo)**, 387 kcal/100g | matki isn't in USDA at all — matched on "steamed" |

Tested stripping quantity words before searching (`"100gm dragon fruit"`
→ `"dragon fruit"`) as a possible quick fix — it doesn't reliably help.
Dragon fruit and matki return the same garbage or nothing at all
regardless of query phrasing, because USDA genuinely has no entry for
them. This is a real data-coverage gap, not a query-tuning problem, and
no amount of prompt engineering the search step fixes it.

**2. The whole meal collapses into one opaque, uneditable row.** Today,
`/v1/foods/estimate` returns *one* combined `NutritionalEstimate` for the
entire description, and logging it creates exactly one `custom_foods` row
+ one `food_logs` row. Once logged, `PATCH /v1/logs/{id}` can only change
`quantity`/`meal_type`/`log_date` — never the underlying food's
name/calories/macros. If one ingredient (the coffee, say) got a wildly
wrong estimate, there is no way to see that, isolate it, or fix just that
one part. The error is invisible and unfixable after the fact.

## What other apps do (researched 2026-08-18)

Every serious competitor — AI-native or not — keeps a meal as a set of
**separate individual food entries**, not one combined blob:

- **MyFitnessPal**: a meal (breakfast/lunch/dinner/snack) is a *bucket*
  you add individual food-database entries to.
- **Cronometer**: same principle. Notably, Cronometer also sources from
  USDA + the Canadian Nutrient File, but curates and verifies ~400K
  entries rather than doing raw fuzzy keyword search — the exact step
  that's noisy in our pipeline.
- **Nutrola** (AI-native): "a chicken breast next to rice and a side
  salad is recognized as **three separate items, not one**."
- **Cal AI** (AI-native): "for complex recipes, you can create custom
  meals by adding individual ingredients, and it will calculate the
  total nutrition."

CalorieParser's current one-blob-per-meal design is the outlier. Keeping
items separate doesn't just organize the data better — it's the
mechanism that makes a bad AI guess on one ingredient correctable instead
of silently poisoning the whole total.

## The fix: per-item estimates, not per-meal

The agent pipeline (Phase 3d, `backend/app/core/agents.py`) already
parses a description into individual items internally
(`_parse_meal` → `parsed_items`) before the current code throws that
structure away and asks for one combined estimate. The fix is narrower
than a rearchitecture: stop throwing it away.

`food_logs` already supports multiple rows sharing one
`log_date`/`meal_type`, and `DailyLog.tsx` already renders them as an
independently editable/deletable flat list. That half of the "meal =
composition of dishes" model already exists — the gap is entirely at the
estimate/logging boundary.

### Backend changes

**1. `backend/app/models/estimation.py`**
- `NutritionalEstimate` stays the same shape (name, serving_size_value,
  serving_size_unit, calories, protein_g, carbs_g, fat_g, confidence,
  notes) — it now represents one *dish* instead of one *meal*.
- New `MealEstimateTotals` model: `calories, protein_g, carbs_g, fat_g`
  (no name/serving/confidence — a sum doesn't have those). Computed as a
  plain sum of the items in the route handler, never independently
  estimated by the LLM — avoids a combined total that doesn't match the
  sum of its own parts, which was part of today's problem.
- `FoodEstimateResponse`: `estimate: NutritionalEstimate` →
  `items: list[NutritionalEstimate]`, `total: MealEstimateTotals`.

**2. `backend/app/core/agents.py`**
- `MealEstimateState.estimate: dict` → `estimates: list[dict]`.
- `_estimate_nutrition`: prompt/schema changes from "return one JSON
  object for the whole meal" to "return `{"items": [...]}`, one object
  per dish" — reusing the same 9-field per-item shape. The model has
  reasonable discretion to merge/split relative to `parsed_items` (e.g.
  "milk" + "coffee" → one "milk coffee" dish is fine, that's a real
  loggable item) — don't strictly enforce a 1:1 count match.
- `_validate_estimate`: loop the existing checks (negative values,
  plausible range, macro/calorie consistency) per item instead of once
  for the whole meal. Tighten the plausible-calorie-range bound per
  single dish (today's 0–5000 kcal was sized for a whole multi-item
  meal). Retry feedback should name which specific item(s) failed.
- **Bundle in the same pass**: add an explicit instruction to
  `ESTIMATE_SYSTEM_PROMPT` telling the model to disregard a USDA
  reference match when its food category obviously doesn't fit the query
  (a candy/pastry/oil match for a raw fruit/vegetable, for instance) and
  fall back to its own nutrition knowledge instead. Cheap, directly
  targets problem #1 above, doesn't fix the underlying data gap but
  reduces how much the estimator gets misled by it.

**3. `backend/app/core/llm.py`**
- `estimate_simple`: wrap its prompt/response in the same `{"items":
  [...]}` shape for consistency, even though it's almost always a single
  item. Keeps the response shape uniform regardless of which path
  (`estimate_simple` vs the agent pipeline) served the request, so the
  frontend doesn't need two different code paths.
- `_gemini_grounded` (the fallback-of-a-fallback, rarely hit): simplest
  option is to wrap its single combined result as a one-item list rather
  than teaching Gemini's tool-calling flow the same per-item schema.
  Acceptable: this path only fires when the primary agent pipeline has
  already failed, so losing per-item breakdown *only* in that already-degraded
  case is a reasonable tradeoff, not a regression from today.

**4. `backend/app/api/v1/foods.py`**
- Compute `total` as a sum over `items` before constructing the response.
- Cache payload shape changes from one object to `{"items": [...],
  "total": {...}}` — same SHA256-of-description cache key, `jsonb`
  column needs no migration.
- `_needs_grounding()` routing logic is unchanged.

**5. Cache invalidation**
- Existing `estimate_cache` rows are in the *old* single-object shape —
  reading one back through new code would KeyError on `data["items"]`.
  Truncate `estimate_cache` as part of deploying this change. It's a
  pure optimization table; a few cache misses right after deploy is a
  fully acceptable cost, and simpler than writing shape-detection compat
  logic for a low-stakes cache.

### Frontend changes

**1. `frontend/src/lib/api.ts`**
- `NutritionalEstimate` type unchanged (per-dish shape).
- `FoodEstimateResponse`: `estimate` → `items: NutritionalEstimate[]`,
  add `total: { calories, protein_g, carbs_g, fat_g }`.

**2. `frontend/src/components/FoodEstimateForm.tsx`**
- Render a list of dish cards instead of one card — each with its own
  name/serving/calories/macros/confidence/notes, plus a per-item "remove"
  button so a dish that's clearly wrong (or wasn't actually eaten) can be
  dropped before logging, without discarding the rest.
- Show a running total (sum of the not-removed items) alongside the list.
- Meal type + date stay a single shared selector for the whole batch,
  same as today — applied to every row created.
- `handleLog()`: loop over the remaining items, `createCustomFood` +
  `createLog` for each (Promise.all, all sharing the same
  `log_date`/`meal_type`). Note: this is N independent two-step
  create-food-then-create-log calls, same partial-failure shape that
  already exists today for the single-item case (no cross-request
  transaction) — just repeated N times. Worth surfacing "X of N logged
  successfully" if any fail, not a new problem to solve from scratch.

**3. `frontend/src/components/DailyLog.tsx`**
- No changes required — already renders a flat list of `food_logs` rows;
  N items from one logged meal just show as N adjacent entries sharing a
  meal-type badge. *Optional future polish*: visually group entries
  logged within the same few seconds as one batch — not required for
  correctness, defer unless it turns out to matter in practice.

### Testing

- `backend/tests/test_estimate.py`: update routing tests for the new
  array response shape.
- `backend/tests/test_agents.py` / `test_validation.py`: per-item
  validation-loop tests (one item fails, others pass; retry feedback
  names the right item).
- New: cache stores/retrieves the array+total shape correctly.
- Manual E2E via curl against a real local server before shipping (same
  discipline as every other AI-pipeline change this project has made) —
  frontend visual verification still needs the user's own spot-check per
  the existing known gap (Claude can't reliably screenshot a browser in
  this dev environment).

### Rollout

This is a breaking change to `/v1/foods/estimate`'s response shape.
Since the only consumer is this project's own frontend (no external API
consumers, no mobile app yet), backend and frontend ship together in one
deploy, not independently — an old frontend against the new backend (or
vice versa) would break. Sequence: backend changes → backend tests green
→ frontend changes → `npm run build` clean → local E2E → deploy both →
truncate `estimate_cache` → `backend/scripts/smoke_test.py` → manual
spot-check of a real multi-item meal in production.

## Token/cost impact (asked directly, answered precisely)

Returning N per-item JSON objects instead of one combined object scales
**completion tokens roughly linearly with item count** — an 8-item meal
produces something like 8x the output tokens of today's single blob.
Relatively, yes, meaningfully more. In absolute cost on `gpt-oss-120b`'s
pricing ($0.60/1M completion tokens), that's the difference between
roughly $0.0001 and $0.001 per estimate — not "significantly more" in
any sense that matters at this project's volume. Input tokens (system
prompt, USDA context) are essentially unchanged.
