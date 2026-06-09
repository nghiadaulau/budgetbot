"""Standalone SQS poller worker — runs as a second ECS Fargate service
(``CMD ["python", "-m", "src.worker"]``), reusing the same image, IAM role, and
RDS/security-group as the API.

Long-polls ``SQS_QUEUE_URL`` and feeds each message to ``handlers.process_job``
(the shared core). A message is deleted only after the job succeeds; on failure
it reappears after the visibility timeout and, after ``maxReceiveCount``, lands
in the DLQ. SIGTERM/SIGINT → finish the current batch, then exit cleanly so ECS
deploys/scale-ins don't drop work.
"""
from __future__ import annotations

import json
import signal
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from loguru import logger

from . import handlers
from .adapters import factory
from .config import config
from .cost_tracker import CostTracker

VISIBILITY_TIMEOUT = 300
WAIT_SECONDS = 20
BATCH = 5

_running = True


def _stop(_signum: int, _frame: Any) -> None:
    global _running
    logger.info("worker received shutdown signal; draining")
    _running = False


def main() -> None:
    if not config.sqs_queue_url:
        raise SystemExit("SQS_QUEUE_URL is not set — nothing to poll")

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    sqs = boto3.client("sqs", region_name=config.aws_region)
    storage = factory.make_storage()
    ai_client = factory.make_ai()
    userstore = factory.make_userstore()
    cost_tracker = CostTracker(userstore)
    logger.info("worker started; queue={}", config.sqs_queue_url)

    while _running:
        try:
            resp = sqs.receive_message(
                QueueUrl=config.sqs_queue_url,
                MaxNumberOfMessages=BATCH,
                WaitTimeSeconds=WAIT_SECONDS,
                VisibilityTimeout=VISIBILITY_TIMEOUT,
            )
        except (BotoCoreError, ClientError):
            logger.exception("sqs receive failed; backing off")
            continue

        for msg in resp.get("Messages", []):
            try:
                handlers.process_job(
                    json.loads(msg["Body"]), storage, ai_client, userstore, cost_tracker
                )
                sqs.delete_message(QueueUrl=config.sqs_queue_url, ReceiptHandle=msg["ReceiptHandle"])
            except Exception:  # noqa: BLE001 — leave message for retry/DLQ, keep polling
                logger.exception("job failed; leaving message for retry/DLQ")

    logger.info("worker stopped")


if __name__ == "__main__":
    main()
