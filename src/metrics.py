"""Custom CloudWatch metrics for BudgetBot W7."""

import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from loguru import logger

NAMESPACE = "BudgetBot/W7"

_cloudwatch = boto3.client(
    "cloudwatch",
    region_name=(
        os.getenv("AWS_REGION_NAME")
        or os.getenv("AWS_DEFAULT_REGION")
        or "us-west-2"
    ),
)


def _dimensions(route: str | None = None, user_id: str | None = None) -> list[dict]:
    dims = [
        {"Name": "Service", "Value": "BudgetBot"},
        {"Name": "Env", "Value": os.getenv("APP_ENV", "dev")},
    ]

    if route:
        dims.append({"Name": "Route", "Value": route})

    if user_id:
        dims.append({"Name": "UserId", "Value": user_id})

    return dims


def put_metric(
    name: str,
    value: float = 1,
    unit: str = "Count",
    route: str | None = None,
    user_id: str | None = None,
) -> None:
    try:
        metric_data = [
            {
                "MetricName": name,
                "Value": value,
                "Unit": unit,
                "Dimensions": _dimensions(route=route, user_id=user_id),
            }
        ]

        if user_id:
            metric_data.append(
                {
                    "MetricName": name,
                    "Value": value,
                    "Unit": unit,
                    "Dimensions": _dimensions(route=route, user_id=None),
                }
            )

        _cloudwatch.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=metric_data,
        )

    except (BotoCoreError, ClientError) as exc:
        logger.warning(
            "cloudwatch_metric_failed metric={} route={} user={} error={}",
            name, route, (f"{user_id[:3]}***" if user_id else "-"), type(exc).__name__,
        )