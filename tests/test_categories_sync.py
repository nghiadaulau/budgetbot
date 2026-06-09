"""Guard against category-enum drift across the AI layer (P0 regression).

The canonical enum lives in `categories.py`; chatbot + handlers must not
re-declare a stale copy (the old Utilities/Subscriptions/Income set).
"""
from src import handlers
from src.adapters import chatbot
from src.categories import CATEGORIES, CATEGORY_SET


def test_chatbot_uses_canonical_categories():
    assert chatbot.CATEGORIES == CATEGORIES
    assert "Bills" in chatbot.CATEGORIES and "Education" in chatbot.CATEGORIES
    assert "Utilities" not in chatbot.CATEGORIES


def test_set_budget_tool_enum_is_canonical():
    assert set(chatbot.CATEGORIES) == CATEGORY_SET


def test_chat_hint_keys_are_canonical():
    assert set(handlers._CATEGORY_HINTS).issubset(CATEGORY_SET)
