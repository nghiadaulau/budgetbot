"""Env-driven config for BudgetBot."""
import os
from dataclasses import dataclass

from loguru import logger

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Config:
    ai_backend: str = _env("AI_BACKEND", "local")
    ai_model_id: str = _env("AI_MODEL_ID", "us.amazon.nova-2-lite-v1:0")
    aws_region: str = _env("AWS_REGION") or _env("AWS_REGION_NAME") or "us-west-2"

    storage_backend: str = _env("STORAGE_BACKEND", "local")
    storage_bucket: str = _env("STORAGE_BUCKET", "")
    storage_local_dir: str = _env("STORAGE_LOCAL_DIR", "data/uploads")
    s3_bucket: str = _env("S3_BUCKET", "")
    s3_presign_expiry: int = int(_env("S3_PRESIGN_EXPIRY", "900"))
    max_upload_size: int = int(_env("MAX_UPLOAD_SIZE_MB", "50")) * 1024 * 1024
    sqs_queue_url: str = _env("SQS_QUEUE_URL", "")


    userstore_backend: str = _env("USERSTORE_BACKEND", "sqlite")
    userstore_table: str = _env("USERSTORE_TABLE", "")
    userstore_postgres_url: str = _env("USERSTORE_POSTGRES_URL", "")
    userstore_sqlite_path: str = _env("USERSTORE_SQLITE_PATH", "./_data/transactions.db")

    default_user_id: str = _env("DEFAULT_USER_ID", "test-user-001")
    log_level: str = _env("LOG_LEVEL", "INFO")


    serve_frontend: bool = _env("SERVE_FRONTEND", "true").lower() == "true"
    cors_origins: str = _env("CORS_ORIGINS", "*")

    userstore_mongo_url: str = _env("USERSTORE_MONGO_URL", "")
    userstore_mongo_db: str = _env("USERSTORE_MONGO_DB", "budgetbot")
    userstore_mongo_tls_ca: str = _env("USERSTORE_MONGO_TLS_CA", "")
    userstore_mysql_url: str = _env("USERSTORE_MYSQL_URL", "")

    app_version: str = "0.2.0"

    db_backend: str = _env("DB_BACKEND", "")
    db_path: str = _env("DB_PATH", "")

    pdf_backend: str = _env("PDF_BACKEND", "local")
    textract_enabled: bool = _env("TEXTRACT_ENABLED", "false").lower() == "true"

    bedrock_input_cost_per_1m: float = float(_env("BEDROCK_INPUT_COST_PER_1M", "0.25"))
    bedrock_output_cost_per_1m: float = float(_env("BEDROCK_OUTPUT_COST_PER_1M", "1.25"))
    csv_classify_batch_size: int = int(_env("CSV_CLASSIFY_BATCH_SIZE", "10"))
    max_pdf_size: int = int(_env("MAX_PDF_SIZE_MB", "5")) * 1024 * 1024

    dedup_enabled: bool = _env("DEDUP_ENABLED", "true").lower() == "true"
    dedup_date_tolerance_days: int = int(_env("DEDUP_DATE_TOLERANCE_DAYS", "1"))
    dedup_manual_warn_days: int = int(_env("DEDUP_MANUAL_WARN_DAYS", "3"))

    catalog_enabled: bool = _env("CATALOG_ENABLED", "true").lower() == "true"
    catalog_min_samples: int = int(_env("CATALOG_MIN_SAMPLES", "3"))
    catalog_min_confidence: float = float(_env("CATALOG_MIN_CONFIDENCE", "0.8"))

    max_cost_per_request_usd: float = float(_env("MAX_COST_PER_REQUEST_USD", "0.50"))
    max_cost_per_user_per_day_usd: float = float(_env("MAX_COST_PER_USER_PER_DAY_USD", "1.00"))
    est_tokens_per_row: int = int(_env("EST_TOKENS_PER_ROW", "60"))

    prompt_cache_enabled: bool = _env("PROMPT_CACHE_ENABLED", "true").lower() == "true"

    bedrock_max_attempts: int = int(_env("BEDROCK_MAX_ATTEMPTS", "3"))

    rate_limit_enabled: bool = _env("RATE_LIMIT_ENABLED", "false").lower() == "true"
    rate_limit_per_minute: int = int(_env("RATE_LIMIT_PER_MINUTE", "60"))
    redis_url: str = _env("REDIS_URL", "")

    idempotency_ttl_days: int = int(_env("IDEMPOTENCY_TTL_DAYS", "2"))

    cognito_user_pool_id: str = _env("COGNITO_USER_POOL_ID", "")
    cognito_client_id: str = _env("COGNITO_CLIENT_ID", "")
    cognito_region: str = _env("COGNITO_REGION", "")
    require_auth: bool = _env("REQUIRE_AUTH", "false").lower() == "true"

    @property
    def resolved_db_backend(self) -> str:
        """DB_BACKEND wins if set, else fall back to USERSTORE_BACKEND."""
        return self.db_backend or self.userstore_backend

    @property
    def resolved_sqlite_path(self) -> str:
        return self.db_path or self.userstore_sqlite_path

    def __post_init__(self):
        secret_name = _env("DB_SECRET_NAME", "")
        if secret_name and self.userstore_backend == "postgres":
            import json

            import boto3
            try:
                client = boto3.client("secretsmanager", region_name=self.aws_region)
                response = client.get_secret_value(SecretId=secret_name)
                secret = json.loads(response["SecretString"])
                
                username = secret.get("DB_USER") or secret.get("username") or "postgres"
                password = secret.get("DB_PASSWORD") or secret.get("password") or ""
                host = secret.get("DB_HOST") or secret.get("host") or ""
                port = secret.get("DB_PORT") or secret.get("port") or 5432
                dbname = secret.get("DB_NAME") or secret.get("dbname") or "budgetbot"
                
                sslmode = _env("DB_SSLMODE") or "require"
                url = f"postgresql://{username}:{password}@{host}:{port}/{dbname}?sslmode={sslmode}"
                object.__setattr__(self, "userstore_postgres_url", url)
                logger.info("SecretsManager: loaded DB credentials from {}", secret_name)
            except Exception as e:  # noqa: BLE001 — boot-time best effort
                logger.warning("SecretsManager: failed to load {}: {}", secret_name, e)

config = Config()
