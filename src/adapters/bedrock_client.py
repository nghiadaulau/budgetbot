"""Shared Bedrock runtime client factory.

Centralizes the boto3 ``bedrock-runtime`` client so every AI adapter gets the
same adaptive retry/backoff. Adaptive mode retries throttling/5xx with
exponential backoff + client-side rate limiting, so a transient
ThrottlingException is retried before we ever degrade to LocalAI (brief §Fail
loud at boundaries, fail soft at edges).
"""
from __future__ import annotations

from typing import Any

import boto3
from botocore.config import Config

from ..config import config


def make_runtime(region: str) -> Any:
    """A bedrock-runtime client with adaptive retry/backoff configured."""
    return boto3.client(
        "bedrock-runtime",
        region_name=region,
        config=Config(
            retries={"mode": "adaptive", "max_attempts": config.bedrock_max_attempts},
        ),
    )
