from app.core.agents import _validate_estimate


def _state(*items, retries=0):
    return {"estimates": list(items), "retries": retries}


def test_valid_macros_pass():
    result = _validate_estimate(_state({"calories": 500, "protein_g": 30, "carbs_g": 50, "fat_g": 20}))
    assert result["validation_errors"] == []


def test_negative_value_fails():
    result = _validate_estimate(_state({"calories": 500, "protein_g": -10, "carbs_g": 50, "fat_g": 20}))
    assert result["validation_errors"]
    assert result["retries"] == 1


def test_macro_calorie_mismatch_over_35_percent_fails():
    # protein*4 + carbs*4 + fat*9 = 850, reported 100 -> 88% off
    result = _validate_estimate(_state({"calories": 100, "protein_g": 50, "carbs_g": 50, "fat_g": 50}))
    assert any("match the macros" in e for e in result["validation_errors"])


def test_macro_calorie_mismatch_under_35_percent_passes():
    # protein*4 + carbs*4 + fat*9 = 500, reported 480 -> 4% off, within tolerance
    result = _validate_estimate(_state({"calories": 480, "protein_g": 30, "carbs_g": 65, "fat_g": 20}))
    assert result["validation_errors"] == []


def test_calories_over_2000_fails():
    # bound is per-dish now (was 0-5000 for a whole meal before per-item estimation)
    result = _validate_estimate(_state({"calories": 3000, "protein_g": 100, "carbs_g": 100, "fat_g": 100}))
    assert any("plausible range" in e for e in result["validation_errors"])


def test_zero_calories_fails():
    result = _validate_estimate(_state({"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}))
    assert any("plausible range" in e for e in result["validation_errors"])


def test_missing_field_fails_gracefully():
    result = _validate_estimate(_state({"calories": 500, "protein_g": 30}))
    assert result["validation_errors"]
    assert result["retries"] == 1


def test_empty_items_list_fails():
    result = _validate_estimate(_state(retries=0))
    assert result["validation_errors"]
    assert result["retries"] == 1


def test_retries_counter_increments_on_failure():
    result = _validate_estimate(_state({"calories": 3000, "protein_g": 1, "carbs_g": 1, "fat_g": 1}, retries=1))
    assert result["retries"] == 2


def test_retries_counter_untouched_on_success():
    result = _validate_estimate(_state({"calories": 500, "protein_g": 30, "carbs_g": 50, "fat_g": 20}, retries=1))
    assert "retries" not in result


def test_one_bad_item_among_several_is_named_and_others_pass():
    """The validator checks every item independently - one bad item
    shouldn't be lost in a generic "something's wrong" message, and a
    good item alongside it shouldn't cause a false failure.
    """
    good = {"name": "milk", "calories": 150, "protein_g": 8, "carbs_g": 12, "fat_g": 8}
    bad = {"name": "rice", "calories": 100, "protein_g": 50, "carbs_g": 50, "fat_g": 50}
    result = _validate_estimate(_state(good, bad))
    assert len(result["validation_errors"]) == 1
    assert "rice" in result["validation_errors"][0]
    assert "milk" not in result["validation_errors"][0]


def test_multiple_valid_items_pass():
    items = [
        {"calories": 150, "protein_g": 8, "carbs_g": 12, "fat_g": 8},
        {"calories": 205, "protein_g": 4.3, "carbs_g": 45, "fat_g": 0.4},
        {"calories": 95, "protein_g": 0.5, "carbs_g": 25, "fat_g": 0.3},
    ]
    result = _validate_estimate(_state(*items))
    assert result["validation_errors"] == []
