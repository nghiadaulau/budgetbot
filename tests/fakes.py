"""Reusable AI test doubles — no AWS, deterministic fixed-snapshot responses.

Used to exercise both success and failure modes of the Bedrock-backed adapters
without credentials or network. Pass a built response/stream, or `raise_exc` to
simulate throttling / transport errors.
"""
from __future__ import annotations

from typing import Any

from botocore.exceptions import ClientError


class FakeBedrockRuntime:
    """Stand-in for a boto3 ``bedrock-runtime`` client.

    Records every call in ``self.calls`` so tests can assert how many Bedrock
    requests were made (e.g. catalog-cache hits should reduce the count).
    """

    def __init__(
        self,
        *,
        converse_response: dict | None = None,
        converse_sequence: list[Any] | None = None,
        stream_events: list[dict] | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self._converse_response = converse_response
        self._converse_sequence = list(converse_sequence) if converse_sequence else None
        self._stream_events = stream_events or []
        self._raise = raise_exc
        self.calls: list[tuple[str, dict]] = []

    def converse(self, **kwargs: Any) -> dict:
        self.calls.append(("converse", kwargs))
        if self._raise is not None:
            raise self._raise
        if self._converse_sequence is not None:
            nxt = self._converse_sequence.pop(0)
            if isinstance(nxt, Exception):
                raise nxt
            return nxt
        return self._converse_response or {}

    def converse_stream(self, **kwargs: Any) -> dict:
        self.calls.append(("converse_stream", kwargs))
        if self._raise is not None:
            raise self._raise
        return {"stream": list(self._stream_events)}


def converse_text(text: str, *, input_tokens: int = 50, output_tokens: int = 10) -> dict:
    """A minimal Converse response carrying `text` + token usage."""
    return {
        "output": {"message": {"content": [{"text": text}]}},
        "usage": {"inputTokens": input_tokens, "outputTokens": output_tokens},
    }


def stream_text(text: str, *, input_tokens: int = 80, output_tokens: int = 20) -> list[dict]:
    """converse_stream events: one text delta + a trailing metadata usage event."""
    return [
        {"contentBlockDelta": {"delta": {"text": text}}},
        {
            "metadata": {
                "usage": {"inputTokens": input_tokens, "outputTokens": output_tokens},
                "metrics": {"latencyMs": 5},
            }
        },
    ]


def throttling_error() -> ClientError:
    """A Bedrock ThrottlingException as boto3 would raise it."""
    return ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "Converse",
    )
