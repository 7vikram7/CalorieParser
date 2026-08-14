import httpx

USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"


def search_usda_foods(api_key: str, query: str, max_results: int = 3) -> list[dict]:
    """Look up standardized per-100g nutrition facts for a food from USDA's
    FoodData Central, for grounding Gemini's estimate in real data.

    Restricted to Foundation/SR Legacy data types - USDA's curated reference
    foods (e.g. "Bananas, raw") - rather than the default "Branded" results,
    which are packaged products whose name/nutrition can be wildly
    unrepresentative of the generic ingredient being asked about (a search
    for "banana" surfaced a peanut-butter spread as the top Branded hit).

    Never raises - a lookup failure just means the tool call returns no
    grounding data and Gemini falls back to its own knowledge, same as
    before this tool existed. A flaky USDA API should degrade the estimate's
    confidence, not break the endpoint.
    """
    try:
        resp = httpx.get(
            USDA_SEARCH_URL,
            params={
                "query": query,
                "pageSize": max_results,
                "dataType": "Foundation,SR Legacy",
                "api_key": api_key,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError:
        return []

    results = []
    for food in data.get("foods", []):
        nutrients = {n["nutrientName"]: n for n in food.get("foodNutrients", [])}
        calories = _kcal(nutrients.get("Energy"))
        results.append(
            {
                "description": food.get("description"),
                "calories_per_100g": calories,
                "protein_g_per_100g": _value(nutrients.get("Protein")),
                "carbs_g_per_100g": _value(nutrients.get("Carbohydrate, by difference")),
                "fat_g_per_100g": _value(nutrients.get("Total lipid (fat)")),
            }
        )
    return results


def _value(nutrient: dict | None) -> float | None:
    return nutrient.get("value") if nutrient else None


def _kcal(energy: dict | None) -> float | None:
    """USDA sometimes reports Energy in kJ instead of kcal (seen on some
    Foundation entries) - normalize to kcal either way.
    """
    if not energy or energy.get("value") is None:
        return None
    value = energy["value"]
    unit = (energy.get("unitName") or "").upper()
    if unit == "KJ":
        return round(value / 4.184, 1)
    return round(value, 1)
