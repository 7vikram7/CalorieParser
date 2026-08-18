import json
from unittest.mock import MagicMock, patch

from app.core import agents


def _fake_groq_response(content: dict):
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=json.dumps(content)))]
    return response


def _mock_groq_client(*contents):
    client = MagicMock()
    client.chat.completions.create.side_effect = [_fake_groq_response(c) for c in contents]
    return client


def test_parse_meal_splits_into_items():
    client = _mock_groq_client({"items": ["butter chicken", "2 naan", "raita"]})
    with patch.object(agents, "groq_client", return_value=client):
        result = agents._parse_meal({"description": "butter chicken with 2 naan and raita"})
    assert result["parsed_items"] == ["butter chicken", "2 naan", "raita"]


def test_parse_meal_falls_back_to_whole_description_on_empty_items():
    client = _mock_groq_client({"items": []})
    with patch.object(agents, "groq_client", return_value=client):
        result = agents._parse_meal({"description": "some obscure dish"})
    assert result["parsed_items"] == ["some obscure dish"]


def test_research_items_runs_concurrently_and_merges_results():
    with patch.object(agents, "search_usda_foods", side_effect=lambda key, item: [{"description": item}]):
        result = agents._research_items({"parsed_items": ["banana", "rice"]})
    assert result["usda_data"] == {"banana": [{"description": "banana"}], "rice": [{"description": "rice"}]}


def test_research_items_handles_no_matches():
    with patch.object(agents, "search_usda_foods", return_value=[]):
        result = agents._research_items({"parsed_items": ["papadum"]})
    assert result["usda_data"] == {"papadum": []}


def test_estimate_nutrition_returns_one_item_per_parsed_item():
    """The estimator is asked for {"items": [...]} - one object per dish,
    not one combined object for the whole meal."""
    items_response = {
        "items": [
            {
                "name": "Rice", "serving_size_value": 1, "serving_size_unit": "bowl",
                "calories": 205, "protein_g": 4.3, "carbs_g": 45.0, "fat_g": 0.4,
                "confidence": 0.7, "notes": None,
            },
            {
                "name": "Milk", "serving_size_value": 1, "serving_size_unit": "glass",
                "calories": 150, "protein_g": 8.0, "carbs_g": 12.0, "fat_g": 8.0,
                "confidence": 0.9, "notes": None,
            },
        ]
    }
    client = _mock_groq_client(items_response)
    state = {
        "description": "rice and milk",
        "parsed_items": ["rice", "milk"],
        "usda_data": {"rice": [], "milk": []},
        "estimates": [],
        "validation_errors": [],
        "retries": 0,
    }
    with patch.object(agents, "groq_client", return_value=client):
        result = agents._estimate_nutrition(state)
    assert len(result["estimates"]) == 2
    assert result["estimates"][0]["name"] == "Rice"
    assert result["estimates"][1]["name"] == "Milk"


def test_full_pipeline_happy_path_returns_list_of_items():
    parse_response = {"items": ["a bowl of rice", "a glass of milk"]}
    good_estimate = {
        "items": [
            {
                "name": "Rice", "serving_size_value": 1.0, "serving_size_unit": "bowl",
                "calories": 205, "protein_g": 4.3, "carbs_g": 45.0, "fat_g": 0.4,
                "confidence": 0.7, "notes": None,
            },
            {
                "name": "Milk", "serving_size_value": 1.0, "serving_size_unit": "glass",
                "calories": 150, "protein_g": 8.0, "carbs_g": 12.0, "fat_g": 8.0,
                "confidence": 0.9, "notes": None,
            },
        ]
    }
    client = _mock_groq_client(parse_response, good_estimate)
    with patch.object(agents, "groq_client", return_value=client), \
         patch.object(agents, "search_usda_foods", return_value=[]):
        result = agents.run_meal_estimate_pipeline("a bowl of rice and a glass of milk")

    assert result == good_estimate["items"]
    assert client.chat.completions.create.call_count == 2  # parse + estimate, no retry needed


def test_pipeline_retries_estimate_on_validation_failure_then_succeeds():
    parse_response = {"items": ["a bowl of rice"]}
    bad_estimate = {
        "items": [
            {
                "name": "bad", "serving_size_value": 1, "serving_size_unit": "bowl",
                "calories": 100, "protein_g": 50, "carbs_g": 50, "fat_g": 50,  # macros wildly off
                "confidence": 0.3, "notes": None,
            }
        ]
    }
    good_estimate = {
        "items": [
            {
                "name": "good", "serving_size_value": 1, "serving_size_unit": "bowl",
                "calories": 205, "protein_g": 4.3, "carbs_g": 45.0, "fat_g": 0.4,
                "confidence": 0.7, "notes": None,
            }
        ]
    }
    client = _mock_groq_client(parse_response, bad_estimate, good_estimate)
    with patch.object(agents, "groq_client", return_value=client), \
         patch.object(agents, "search_usda_foods", return_value=[]):
        result = agents.run_meal_estimate_pipeline("a bowl of rice")

    assert result == good_estimate["items"]
    assert client.chat.completions.create.call_count == 3  # parse + 2 estimate attempts


def test_pipeline_gives_up_after_max_retries_and_returns_last_attempt():
    parse_response = {"items": ["a bowl of rice"]}
    always_bad = {
        "items": [
            {
                "name": "always bad", "serving_size_value": 1, "serving_size_unit": "bowl",
                "calories": 100, "protein_g": 50, "carbs_g": 50, "fat_g": 50,
                "confidence": 0.3, "notes": None,
            }
        ]
    }
    client = _mock_groq_client(parse_response, *([always_bad] * 5))
    with patch.object(agents, "groq_client", return_value=client), \
         patch.object(agents, "search_usda_foods", return_value=[]):
        result = agents.run_meal_estimate_pipeline("a bowl of rice")

    assert result == always_bad["items"]
    # parse (1) + estimate attempts 1, 2, 3 (initial + MAX_VALIDATION_RETRIES=2) = 4 total
    assert client.chat.completions.create.call_count == 1 + 1 + agents.MAX_VALIDATION_RETRIES


def test_pipeline_retry_isolates_which_item_failed():
    """A retry after one bad item among several should only need to
    re-estimate - the validation feedback text should name the specific
    failing item, not just say "something is wrong"."""
    parse_response = {"items": ["rice", "milk"]}
    bad_estimate = {
        "items": [
            {"name": "rice", "serving_size_value": 1, "serving_size_unit": "bowl",
             "calories": 100, "protein_g": 50, "carbs_g": 50, "fat_g": 50, "confidence": 0.3, "notes": None},
            {"name": "milk", "serving_size_value": 1, "serving_size_unit": "glass",
             "calories": 150, "protein_g": 8, "carbs_g": 12, "fat_g": 8, "confidence": 0.9, "notes": None},
        ]
    }
    good_estimate = {
        "items": [
            {"name": "rice", "serving_size_value": 1, "serving_size_unit": "bowl",
             "calories": 205, "protein_g": 4.3, "carbs_g": 45, "fat_g": 0.4, "confidence": 0.7, "notes": None},
            {"name": "milk", "serving_size_value": 1, "serving_size_unit": "glass",
             "calories": 150, "protein_g": 8, "carbs_g": 12, "fat_g": 8, "confidence": 0.9, "notes": None},
        ]
    }
    client = _mock_groq_client(parse_response, bad_estimate, good_estimate)
    with patch.object(agents, "groq_client", return_value=client), \
         patch.object(agents, "search_usda_foods", return_value=[]):
        result = agents.run_meal_estimate_pipeline("rice and milk")

    assert result == good_estimate["items"]
    # call 0 = parse, call 1 = estimate attempt 1 (returns bad_estimate),
    # call 2 = the retry - its prompt should name "rice" specifically as
    # feedback from the failed attempt.
    retry_messages = client.chat.completions.create.call_args_list[2].kwargs["messages"]
    user_message = next(m["content"] for m in retry_messages if m["role"] == "user")
    assert "rice" in user_message
