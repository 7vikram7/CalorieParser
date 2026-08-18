from unittest.mock import MagicMock, patch

from app.core import llm

ITEMS_SHAPE = {
    "items": [
        {
            "name": "Banana", "serving_size_value": 1.0, "serving_size_unit": "medium",
            "calories": 105, "protein_g": 1.3, "carbs_g": 27.0, "fat_g": 0.4,
            "confidence": 0.9, "notes": None,
        }
    ]
}


def test_set_cached_estimate_stores_items_shape():
    fake_db = MagicMock()
    with patch.object(llm, "get_service_role_client", return_value=fake_db):
        llm.set_cached_estimate("a banana", ITEMS_SHAPE, source="groq")

    upsert_call = fake_db.table.return_value.upsert.call_args
    stored_row = upsert_call.args[0]
    assert stored_row["estimate"] == ITEMS_SHAPE
    assert stored_row["source"] == "groq"


def test_get_cached_estimate_returns_items_shape():
    fake_db = MagicMock()
    fake_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"estimate": ITEMS_SHAPE}
    ]
    with patch.object(llm, "get_service_role_client", return_value=fake_db):
        result = llm.get_cached_estimate("a banana")

    assert result == ITEMS_SHAPE
    assert "items" in result


def test_get_cached_estimate_returns_none_on_miss():
    fake_db = MagicMock()
    fake_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    with patch.object(llm, "get_service_role_client", return_value=fake_db):
        result = llm.get_cached_estimate("something never asked before")

    assert result is None


def test_set_cached_estimate_write_failure_does_not_raise():
    """Caching is best-effort - a write failure shouldn't fail a request
    that already has a perfectly good estimate."""
    fake_db = MagicMock()
    fake_db.table.return_value.upsert.return_value.execute.side_effect = Exception("connection reset")
    with patch.object(llm, "get_service_role_client", return_value=fake_db):
        llm.set_cached_estimate("a banana", ITEMS_SHAPE, source="groq")  # should not raise
