from app.core.agents import _validate_estimate


def _state(estimate, retries=0):
    return {"estimate": estimate, "retries": retries}


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


def test_calories_over_5000_fails():
    result = _validate_estimate(_state({"calories": 50000, "protein_g": 100, "carbs_g": 100, "fat_g": 100}))
    assert any("plausible range" in e for e in result["validation_errors"])


def test_zero_calories_fails():
    result = _validate_estimate(_state({"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}))
    assert any("plausible range" in e for e in result["validation_errors"])


def test_missing_field_fails_gracefully():
    result = _validate_estimate(_state({"calories": 500, "protein_g": 30}))
    assert result["validation_errors"]
    assert result["retries"] == 1


def test_retries_counter_increments_on_failure():
    result = _validate_estimate(_state({"calories": 50000, "protein_g": 1, "carbs_g": 1, "fat_g": 1}, retries=1))
    assert result["retries"] == 2


def test_retries_counter_untouched_on_success():
    result = _validate_estimate(_state({"calories": 500, "protein_g": 30, "carbs_g": 50, "fat_g": 20}, retries=1))
    assert "retries" not in result
