"""Adapter factory — the ONE place backends are chosen.

Why the adapter pattern? BudgetBot must run two ways from the *same* code:
clone-and-run locally (rule-based AI, SQLite, filesystem, no AWS credentials),
and production on AWS (Bedrock, RDS/DynamoDB, S3). Each capability — AI
categorization, PDF extraction, object storage, the transaction store — hides
behind a small interface, and the concrete implementation is selected here from
env vars. Swapping a backend is a config change, never a code change; adding one
is a new class plus a branch in the matching `make_*` function. Business logic
(handlers.py) depends only on the interfaces, so it never knows or cares which
backend is live — which also makes it trivially testable with the local stubs.
"""
from ..config import config
from . import ai, pdf_extractor, storage, userstore


def make_ai():
    """AI categorizer: bedrock (Converse) | local (rule-based, offline)."""
    if config.ai_backend == "bedrock":
        return ai.BedrockAI(region=config.aws_region, model_id=config.ai_model_id)
    if config.ai_backend == "local":
        return ai.LocalAI()
    raise ValueError(f"Unknown AI_BACKEND: {config.ai_backend!r}")


def make_pdf_extractor():
    """Receipt PDF extractor: bedrock (Haiku vision) | local (offline stub)."""
    if config.pdf_backend == "bedrock":
        return pdf_extractor.BedrockPDFExtractor(
            region=config.aws_region, model_id=config.ai_model_id
        )
    if config.pdf_backend == "local":
        return pdf_extractor.LocalStubPDFExtractor()
    raise ValueError(f"Unknown PDF_BACKEND: {config.pdf_backend!r}")


def make_storage():
    """Object storage for raw uploads: s3 | local (filesystem)."""
    if config.storage_backend == "s3":
        return storage.S3Storage(bucket=config.storage_bucket, region=config.aws_region)
    if config.storage_backend == "local":
        return storage.LocalStorage(base_dir=config.storage_local_dir)
    raise ValueError(f"Unknown STORAGE_BACKEND: {config.storage_backend!r}")


def make_userstore():
    """Transaction store. DB_BACKEND wins over USERSTORE_BACKEND when set.

    sqlite (default, fully featured incl. dedup) | postgres | dynamodb |
    documentdb | mysql.
    """
    backend = config.resolved_db_backend
    if backend == "dynamodb":
        return userstore.DynamoDBUserStore(table_name=config.userstore_table, region=config.aws_region)
    if backend == "postgres":
        return userstore.PostgresUserStore(url=config.userstore_postgres_url)
    if backend == "sqlite":
        return userstore.SQLiteUserStore(db_path=config.resolved_sqlite_path)
    if backend == "documentdb":
        return userstore.DocumentDBUserStore(
            url=config.userstore_mongo_url,
            db_name=config.userstore_mongo_db,
            tls_ca_file=config.userstore_mongo_tls_ca,
        )
    if backend == "mysql":
        return userstore.MySQLUserStore(url=config.userstore_mysql_url)
    raise ValueError(
        f"Unknown DB backend: {backend!r} (expected sqlite|postgres|dynamodb|documentdb|mysql)"
    )
