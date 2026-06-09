"""AI output-validation failure modes (brief §AI/ML.6).

A bad Bedrock response must never crash a request: it degrades to a safe
category + needs_review=true via the pydantic validator, or to LocalAI on a
transport/throttle error.
"""
import json

from fakes import FakeBedrockRuntime, converse_text, throttling_error

from src.adapters.ai import BedrockAI

AMBIGUOUS = [
    {"description": "QWERTY VENDOR ALPHA", "amount": -100000},
    {"description": "QWERTY VENDOR BETA", "amount": -250000},
]


def _bedrock(fake) -> BedrockAI:
    bot = BedrockAI(region="us-east-1", model_id="haiku")
    bot.runtime = fake
    return bot


def test_valid_batch_high_confidence_not_flagged():
    items = [
        {"idx": 1, "category": "Food", "confidence": "high"},
        {"idx": 2, "category": "Shopping", "confidence": "high"},
    ]
    bot = _bedrock(FakeBedrockRuntime(converse_response=converse_text(json.dumps(items))))
    out, usage = bot.classify_batch(AMBIGUOUS)
    assert [r["category"] for r in out] == ["Food", "Shopping"]
    assert all(r["needs_review"] is False for r in out)
    assert usage.input_tokens > 0


def test_malformed_json_degrades_to_review():
    bot = _bedrock(FakeBedrockRuntime(converse_response=converse_text("totally not json")))
    out, _ = bot.classify_batch(AMBIGUOUS)
    assert all(r["category"] == "Other" and r["needs_review"] for r in out)


def test_invalid_enum_degrades_to_review():
    items = [
        {"idx": 1, "category": "Groceries", "confidence": "high"},
        {"idx": 2, "category": "Food", "confidence": "high"},
    ]
    bot = _bedrock(FakeBedrockRuntime(converse_response=converse_text(json.dumps(items))))
    out, _ = bot.classify_batch(AMBIGUOUS)
    assert out[0]["category"] == "Other" and out[0]["needs_review"] is True
    assert out[1]["category"] == "Food" and out[1]["needs_review"] is False


def test_partial_batch_missing_row_flagged():
    items = [{"idx": 1, "category": "Food", "confidence": "high"}]
    bot = _bedrock(FakeBedrockRuntime(converse_response=converse_text(json.dumps(items))))
    out, _ = bot.classify_batch(AMBIGUOUS)
    assert out[0]["needs_review"] is False
    assert out[1]["category"] == "Other" and out[1]["needs_review"] is True


def test_low_confidence_flagged_for_review():
    items = [
        {"idx": 1, "category": "Food", "confidence": "low"},
        {"idx": 2, "category": "Shopping", "confidence": "medium"},
    ]
    bot = _bedrock(FakeBedrockRuntime(converse_response=converse_text(json.dumps(items))))
    out, _ = bot.classify_batch(AMBIGUOUS)
    assert out[0]["needs_review"] is True
    assert out[1]["needs_review"] is False


def test_batch_throttle_falls_back_to_local():
    bot = _bedrock(FakeBedrockRuntime(raise_exc=throttling_error()))
    out, usage = bot.classify_batch(AMBIGUOUS)
    assert all(r["confidence"] == "low-fallback" and r["needs_review"] for r in out)
    assert usage.input_tokens == 0


def test_classify_one_throttle_falls_back_to_local():
    bot = _bedrock(FakeBedrockRuntime(raise_exc=throttling_error()))
    result, usage = bot.classify_one("QWERTY VENDOR GAMMA", -50000)
    assert result.needs_review is True
    assert result.confidence == "low-fallback"
    assert usage.model_id == "local-fallback"
