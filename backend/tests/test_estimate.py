from unittest.mock import patch

from app.core import llm

FAKE_ITEM = {
    "name": "Banana",
    "serving_size_value": 1.0,
    "serving_size_unit": "medium",
    "calories": 105,
    "protein_g": 1.3,
    "carbs_g": 27.0,
    "fat_g": 0.4,
    "confidence": 0.9,
    "notes": None,
}
FAKE_ESTIMATE = {"items": [FAKE_ITEM]}

FAKE_TWO_ITEM_ESTIMATE = {
    "items": [
        FAKE_ITEM,
        {
            "name": "Milk",
            "serving_size_value": 1.0,
            "serving_size_unit": "glass",
            "calories": 150,
            "protein_g": 8.0,
            "carbs_g": 12.0,
            "fat_g": 8.0,
            "confidence": 0.9,
            "notes": None,
        },
    ]
}


def test_empty_description_returns_422(anon_client):
    r = anon_client.post("/v1/foods/estimate", json={"description": "   "})
    assert r.status_code == 422


def test_description_over_500_chars_returns_422(anon_client):
    r = anon_client.post("/v1/foods/estimate", json={"description": "a" * 501})
    assert r.status_code == 422


def test_simple_description_routes_to_groq_not_gemini(anon_client):
    with patch.object(llm, "get_cached_estimate", return_value=None), \
         patch.object(llm, "set_cached_estimate") as mock_set, \
         patch.object(llm, "estimate_simple", return_value=FAKE_ESTIMATE) as mock_simple, \
         patch.object(llm, "estimate_grounded") as mock_grounded:
        r = anon_client.post("/v1/foods/estimate", json={"description": "a banana"})

    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["calories"] == 105
    assert body["total"]["calories"] == 105
    mock_simple.assert_called_once()
    mock_grounded.assert_not_called()
    mock_set.assert_called_once_with("a banana", FAKE_ESTIMATE, source="groq")


def test_complex_description_routes_to_grounded_pipeline_and_sums_total(anon_client):
    description = "butter chicken with 2 naan, raita, and gulab jamun"
    with patch.object(llm, "get_cached_estimate", return_value=None), \
         patch.object(llm, "set_cached_estimate") as mock_set, \
         patch.object(llm, "estimate_simple") as mock_simple, \
         patch.object(llm, "estimate_grounded", return_value=FAKE_TWO_ITEM_ESTIMATE) as mock_grounded:
        r = anon_client.post("/v1/foods/estimate", json={"description": description})

    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2
    # total is a plain sum, not independently estimated - 105 + 150 = 255
    assert body["total"]["calories"] == 255
    mock_grounded.assert_called_once()
    mock_simple.assert_not_called()
    mock_set.assert_called_once_with(description, FAKE_TWO_ITEM_ESTIMATE, source="gemini")


def test_cache_hit_skips_both_providers(anon_client):
    with patch.object(llm, "get_cached_estimate", return_value=FAKE_ESTIMATE), \
         patch.object(llm, "set_cached_estimate") as mock_set, \
         patch.object(llm, "estimate_simple") as mock_simple, \
         patch.object(llm, "estimate_grounded") as mock_grounded:
        r = anon_client.post("/v1/foods/estimate", json={"description": "a banana"})

    assert r.status_code == 200
    assert r.json()["items"][0]["calories"] == 105
    mock_simple.assert_not_called()
    mock_grounded.assert_not_called()
    mock_set.assert_not_called()


def test_malformed_provider_response_returns_502_not_500(anon_client):
    """A provider returning JSON missing a required field (e.g. no
    "calories") should surface as a clean 502 ("AI estimation failed"),
    not an unhandled 500 - the route wraps NutritionalEstimate(**item)
    construction in the same try/except as the provider calls themselves.
    """
    with patch.object(llm, "get_cached_estimate", return_value=None), \
         patch.object(llm, "set_cached_estimate"), \
         patch.object(llm, "estimate_simple", return_value={"items": [{"name": "Banana"}]}):
        r = anon_client.post("/v1/foods/estimate", json={"description": "a banana"})
    assert r.status_code == 502


def test_empty_items_list_returns_502_not_500(anon_client):
    with patch.object(llm, "get_cached_estimate", return_value=None), \
         patch.object(llm, "set_cached_estimate"), \
         patch.object(llm, "estimate_simple", return_value={"items": []}):
        r = anon_client.post("/v1/foods/estimate", json={"description": "a banana"})
    assert r.status_code == 502


def test_estimate_grounded_falls_back_through_full_chain_never_502(anon_client):
    """Integration-style test of llm.estimate_grounded's own fallback
    chain (agent pipeline -> Gemini -> Groq), through the real endpoint
    rather than calling estimate_grounded directly - confirms the route
    layer doesn't accidentally swallow or shortcut the fallback.
    """
    with patch.object(llm, "get_cached_estimate", return_value=None), \
         patch.object(llm, "set_cached_estimate"), \
         patch.object(llm, "estimate_agentic", side_effect=RuntimeError("pipeline bug")), \
         patch.object(llm, "_gemini_grounded", side_effect=RuntimeError("gemini also down")), \
         patch.object(llm, "estimate_simple", return_value=FAKE_ESTIMATE) as mock_simple:
        r = anon_client.post(
            "/v1/foods/estimate",
            json={"description": "a very long multi item description, with commas, and stuff"},
        )

    assert r.status_code == 200
    assert r.json()["items"][0]["calories"] == 105
    mock_simple.assert_called_once()
