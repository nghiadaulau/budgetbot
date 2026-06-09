"""Chat cost tracking (P0): the money-coach is the most token-heavy flow and
must show up in the cost log."""
from fakes import FakeBedrockRuntime, stream_text

from src import handlers
from src.adapters.ai import TokenUsage
from src.adapters.chatbot import ChatbotAI
from src.adapters.userstore import SQLiteUserStore
from src.cost_tracker import CostTracker


class _FakeChatbot:
    """Minimal chatbot that pushes usage into cost_sink and streams text."""

    def chat(self, *, cost_sink=None, **kwargs):
        if cost_sink is not None:
            cost_sink.append(TokenUsage.for_bedrock("haiku", 120, 30, 5))

        def gen():
            yield "Xin chào! "
            yield "Tháng này bạn chi tiêu ổn."

        return gen()

    def summarize_memory(self, *args, **kwargs):
        return "", TokenUsage.zero()


def test_handle_chat_records_cost(tmp_path):
    store = SQLiteUserStore(db_path=str(tmp_path / "t.db"))
    tracker = CostTracker(store)

    gen = handlers.handle_chat(
        "user-cost", "hi", None, None, store, _FakeChatbot(), tracker
    )
    text = "".join(gen)

    assert "Xin chào" in text
    report = store.aggregate_costs("user-cost")
    assert report["by_flow"].get("chat", 0) > 0
    assert report["tokens_total"]["input"] == 120


def test_chatbot_stream_captures_usage_into_cost_sink():
    bot = ChatbotAI(region="x", model_id="haiku")
    bot.runtime = FakeBedrockRuntime(
        stream_events=stream_text("ok", input_tokens=200, output_tokens=15)
    )
    sink: list[TokenUsage] = []
    gen = bot.chat(
        user_id="u",
        messages_context=[{"role": "user", "text": "hi"}],
        transactions=[],
        budgets={},
        summary={},
        cost_sink=sink,
    )
    out = "".join(gen)

    assert out == "ok"
    assert len(sink) == 1
    assert sink[0].input_tokens == 200 and sink[0].output_tokens == 15
