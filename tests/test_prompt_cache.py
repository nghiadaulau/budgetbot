"""Bedrock prompt caching: the large static system prompt is sent as a cacheable
block separate from the per-request context (brief §AI/ML.4)."""
from fakes import FakeBedrockRuntime, stream_text

from src.adapters.chatbot import ChatbotAI


def _run_chat():
    bot = ChatbotAI(region="us-east-1", model_id="haiku")
    fake = FakeBedrockRuntime(stream_events=stream_text("hi"))
    bot.runtime = fake
    list(
        bot.chat(
            user_id="u",
            messages_context=[{"role": "user", "text": "hi"}],
            transactions=[],
            budgets={},
            summary={},
            cost_sink=[],
        )
    )
    return fake


def test_chat_system_has_cachepoint_and_static_prefix():
    fake = _run_chat()
    _, kwargs = fake.calls[0]
    system = kwargs["system"]
    assert system[0]["text"].startswith("You are an AI Money Coach")
    assert any("cachePoint" in block for block in system)
    assert any("Transactions context" in block.get("text", "") for block in system)
