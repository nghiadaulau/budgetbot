"""Transaction store adapters.

Interface:
    add_transaction(user_id, txn) -> None       # txn = {date, description, amount, category, confidence}
    list_transactions(user_id, month=None) -> list[dict]
    summary(user_id, month=None) -> {category: {"total": float, "count": int}}
"""
import json
import sqlite3
import threading
import uuid
from collections import defaultdict
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


def _now() -> str:
    return datetime.now(UTC).isoformat()


class DynamoDBUserStore:
    """PK=user_id, SK=TXN#<date>#<id>. Aggregations require Scan or GSI — accept the trade-off."""

    def __init__(self, table_name: str, region: str):
        import boto3
        if not table_name:
            raise ValueError("USERSTORE_TABLE must be set for DynamoDB backend")
        self.table = boto3.resource("dynamodb", region_name=region).Table(table_name)

    def add_transaction(self, user_id: str, txn: dict) -> None:
        import uuid
        from decimal import Decimal
        sk = f"TXN#{txn['date']}#{uuid.uuid4().hex[:8]}"
        item = {**txn, "amount": Decimal(str(txn["amount"]))} if "amount" in txn else txn
        self.table.put_item(Item={"user_id": user_id, "sk": sk, "created_at": _now(), **item})

    def list_transactions(self, user_id: str, month: str | None = None) -> list:
        kwargs = {
            "KeyConditionExpression": "user_id = :u AND begins_with(sk, :p)",
            "ExpressionAttributeValues": {":u": user_id, ":p": f"TXN#{month}" if month else "TXN#"},
        }
        resp = self.table.query(**kwargs)
        return [_decimal_to_float(item) for item in resp.get("Items", [])]

    def summary(self, user_id: str, month: str | None = None) -> dict:
        return _aggregate(self.list_transactions(user_id, month))

    def set_budget(self, user_id: str, category: str, amount: float) -> None:
        from decimal import Decimal
        sk = f"BUDGET#{category}"
        self.table.put_item(Item={"user_id": user_id, "sk": sk, "category": category, "amount": Decimal(str(amount)), "updated_at": _now()})

    def get_budgets(self, user_id: str) -> dict:
        kwargs = {
            "KeyConditionExpression": "user_id = :u AND begins_with(sk, :p)",
            "ExpressionAttributeValues": {":u": user_id, ":p": "BUDGET#"},
        }
        resp = self.table.query(**kwargs)
        return {item["category"]: float(item["amount"]) for item in resp.get("Items", [])}


def _decimal_to_float(item: dict) -> dict:
    from decimal import Decimal
    return {k: (float(v) if isinstance(v, Decimal) else v) for k, v in item.items()}


class PostgresUserStore:
    """RDS Postgres store backed by a thread-safe connection POOL.

    FastAPI serves sync routes from a thread pool; a single shared connection
    would serialize every request (and isn't safe to use concurrently). A
    ThreadedConnectionPool hands each in-flight request its own connection and
    returns it after, so requests run in parallel up to ``maxconn`` (bounded so we
    never exhaust RDS max_connections). Each `_cursor()` block is one transaction
    (commit on success / rollback on error) — multi-statement methods are atomic.
    """

    def __init__(self, url: str, minconn: int = 1, maxconn: int = 10):
        try:
            from psycopg2 import pool as _pgpool
        except ImportError as exc:
            raise ImportError("psycopg2 not installed. Run: pip install psycopg2-binary") from exc
        if not url:
            raise ValueError("USERSTORE_POSTGRES_URL must be set for Postgres backend")
        self._pool = _pgpool.ThreadedConnectionPool(minconn, maxconn, dsn=url)
        self._init_schema()

    @contextmanager
    def _cursor(self):
        """Check out a pooled connection, yield a cursor, commit/rollback, return it."""
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    def _init_schema(self):
        with self._cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id BIGSERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    txn_date DATE NOT NULL,
                    description TEXT,
                    amount NUMERIC(14,2),
                    category TEXT,
                    confidence TEXT,
                    source TEXT DEFAULT 'csv',
                    fingerprint TEXT,
                    file_id TEXT,
                    needs_review BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                -- Upgrade older deployments in place (no migration script needed).
                ALTER TABLE transactions ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'csv';
                ALTER TABLE transactions ADD COLUMN IF NOT EXISTS fingerprint TEXT;
                ALTER TABLE transactions ADD COLUMN IF NOT EXISTS file_id TEXT;
                ALTER TABLE transactions ADD COLUMN IF NOT EXISTS needs_review BOOLEAN DEFAULT FALSE;
                CREATE INDEX IF NOT EXISTS txn_user_date_idx ON transactions(user_id, txn_date);
                CREATE INDEX IF NOT EXISTS txn_user_cat_idx ON transactions(user_id, category);
                CREATE INDEX IF NOT EXISTS txn_user_fp_idx ON transactions(user_id, fingerprint);
                CREATE TABLE IF NOT EXISTS cost_log (
                    id BIGSERIAL PRIMARY KEY,
                    ts TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    flow TEXT NOT NULL,
                    model_id TEXT,
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    cache_read_tokens INTEGER DEFAULT 0,
                    cache_write_tokens INTEGER DEFAULT 0,
                    latency_ms INTEGER DEFAULT 0,
                    estimated_cost_usd DOUBLE PRECISION DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS cost_user_ts_idx ON cost_log(user_id, ts);
                CREATE TABLE IF NOT EXISTS uploaded_files (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    filename TEXT,
                    file_type TEXT,
                    file_size INTEGER,
                    transaction_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'processed',
                    uploaded_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS uploaded_user_hash_idx ON uploaded_files(user_id, file_hash);
                CREATE TABLE IF NOT EXISTS receipt_extractions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    pdf_hash TEXT,
                    extracted_fingerprint TEXT,
                    extracted_raw TEXT,
                    transaction_id BIGINT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS receipt_user_fp_idx ON receipt_extractions(user_id, extracted_fingerprint);
                CREATE TABLE IF NOT EXISTS merchant_catalog (
                    user_id TEXT NOT NULL,
                    desc_hash TEXT NOT NULL,
                    category TEXT NOT NULL,
                    confidence_sum DOUBLE PRECISION NOT NULL DEFAULT 0,
                    sample_count INTEGER NOT NULL DEFAULT 0,
                    last_seen TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (user_id, desc_hash)
                );
                CREATE TABLE IF NOT EXISTS classification_audit (
                    id BIGSERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    transaction_id TEXT,
                    source TEXT,
                    category TEXT,
                    confidence TEXT,
                    needs_review BOOLEAN DEFAULT FALSE,
                    prompt_version TEXT,
                    model_id TEXT,
                    ts TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS audit_user_txn_idx ON classification_audit(user_id, transaction_id);
                CREATE TABLE IF NOT EXISTS idempotency (
                    user_id TEXT NOT NULL,
                    idem_key TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (user_id, idem_key)
                );
                CREATE TABLE IF NOT EXISTS upload_jobs (
                    job_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    s3_key TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'QUEUED',
                    rows_inserted INTEGER DEFAULT 0,
                    error TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS budgets (
                    user_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    amount NUMERIC(14,2) NOT NULL,
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (user_id, category)
                );
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    profile_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                    message_count INTEGER NOT NULL DEFAULT 0,
                    summarized_through_id BIGINT NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS chat_sessions_user_idx ON chat_sessions(user_id, updated_at DESC);
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id BIGSERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    token_estimate INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS chat_messages_session_id_idx ON chat_messages(session_id, id DESC);
            """)

    _COLS = "id, txn_date, description, amount, category, confidence, source, needs_review"

    @staticmethod
    def _row_to_dict(r) -> dict:
        return {
            "id": str(r[0]), "date": str(r[1]), "description": r[2],
            "amount": float(r[3]) if r[3] is not None else 0.0,
            "category": r[4], "confidence": r[5], "source": r[6] or "csv",
            "needs_review": bool(r[7]),
        }

    @staticmethod
    def _as_id(txn_id) -> int | None:
        try:
            return int(txn_id)
        except (TypeError, ValueError):
            return None

    def add_transaction(self, user_id: str, txn: dict) -> str:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO transactions "
                "(user_id, txn_date, description, amount, category, confidence, source, fingerprint, file_id, needs_review) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (user_id, txn["date"], txn["description"], float(txn["amount"]),
                 txn["category"], txn.get("confidence", ""), txn.get("source", "csv"),
                 txn.get("fingerprint"), txn.get("file_id"), bool(txn.get("needs_review"))),
            )
            return str(cur.fetchone()[0])

    def list_transactions(self, user_id: str, month: str | None = None) -> list:
        sql = f"SELECT {self._COLS} FROM transactions WHERE user_id = %s"
        params: list = [user_id]
        if month:
            sql += " AND to_char(txn_date, 'YYYY-MM') = %s"
            params.append(month)
        sql += " ORDER BY txn_date DESC, id DESC"
        with self._cursor() as cur:
            cur.execute(sql, params)
            return [self._row_to_dict(r) for r in cur.fetchall()]

    def get_transaction(self, user_id: str, txn_id: str) -> dict | None:
        tid = self._as_id(txn_id)
        if tid is None:
            return None
        with self._cursor() as cur:
            cur.execute(f"SELECT {self._COLS} FROM transactions WHERE user_id = %s AND id = %s", (user_id, tid))
            r = cur.fetchone()
            return self._row_to_dict(r) if r else None

    def update_transaction(self, user_id: str, txn_id: str, fields: dict) -> dict | None:
        """Partial update; clears needs_review on a manual category pick."""
        tid = self._as_id(txn_id)
        if tid is None:
            return None
        col_map = {"date": "txn_date", "amount": "amount", "description": "description", "category": "category"}
        sets, params = [], []
        for key, col in col_map.items():
            if fields.get(key) is not None:
                sets.append(f"{col} = %s")
                params.append(fields[key])
        if fields.get("category"):
            sets.append("needs_review = FALSE")
        if not sets:
            return self.get_transaction(user_id, txn_id)
        if "amount" in fields or "description" in fields:
            existing = self.get_transaction(user_id, txn_id)
            if existing:
                from ..dedup.normalize import transaction_fingerprint
                amt = fields.get("amount", existing["amount"])
                desc = fields.get("description", existing["description"])
                sets.append("fingerprint = %s")
                params.append(transaction_fingerprint(user_id, amt, desc))
        params += [user_id, tid]
        with self._cursor() as cur:
            cur.execute(f"UPDATE transactions SET {', '.join(sets)} WHERE user_id = %s AND id = %s", params)
        return self.get_transaction(user_id, txn_id)

    def list_filtered(self, user_id: str, month: str | None = None, category: str | None = None,
                      source: str | None = None, search: str | None = None,
                      page: int = 1, page_size: int = 50) -> tuple[list, int]:
        where = ["user_id = %s"]
        params: list = [user_id]
        if month:
            where.append("to_char(txn_date, 'YYYY-MM') = %s")
            params.append(month)
        if category:
            where.append("category = %s")
            params.append(category)
        if source:
            where.append("source = %s")
            params.append(source)
        if search:
            where.append("LOWER(description) LIKE %s")
            params.append(f"%{search.lower()}%")
        clause = " AND ".join(where)
        with self._cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM transactions WHERE {clause}", params)
            total = cur.fetchone()[0]
            offset = max(0, (page - 1) * page_size)
            cur.execute(
                f"SELECT {self._COLS} FROM transactions WHERE {clause} "
                "ORDER BY txn_date DESC, id DESC LIMIT %s OFFSET %s",
                [*params, page_size, offset],
            )
            return [self._row_to_dict(r) for r in cur.fetchall()], int(total)

    def find_transactions_by_fingerprint(self, user_id: str, fingerprint: str) -> list:
        with self._cursor() as cur:
            cur.execute(f"SELECT {self._COLS} FROM transactions WHERE user_id = %s AND fingerprint = %s",
                        (user_id, fingerprint))
            return [self._row_to_dict(r) for r in cur.fetchall()]

    def update_category(self, user_id: str, txn_id: int, new_category: str) -> None:
        with self._cursor() as cur:
            cur.execute(
                "UPDATE transactions SET category = %s, confidence = 'high', needs_review = FALSE "
                "WHERE user_id = %s AND id = %s",
                (new_category, user_id, self._as_id(txn_id))
            )

    def clear_transactions(self, user_id: str) -> None:
        with self._cursor() as cur:
            cur.execute("DELETE FROM transactions WHERE user_id = %s", (user_id,))

    def clear_chat_memory(self, user_id: str) -> None:
        with self._cursor() as cur:
            cur.execute("DELETE FROM chat_messages WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM chat_sessions WHERE user_id = %s", (user_id,))

    def clear_chat_session(self, user_id: str, session_id: str) -> None:
        with self._cursor() as cur:
            cur.execute("DELETE FROM chat_messages WHERE user_id = %s AND session_id = %s", (user_id, session_id))
            cur.execute("DELETE FROM chat_sessions WHERE user_id = %s AND id = %s", (user_id, session_id))

    def delete_transaction(self, user_id: str, txn_id: int) -> None:
        with self._cursor() as cur:
            cur.execute("DELETE FROM transactions WHERE user_id = %s AND id = %s", (user_id, txn_id))

    def summary(self, user_id: str, month: str | None = None) -> dict:
        sql = "SELECT category, SUM(amount), COUNT(*) FROM transactions WHERE user_id = %s"
        params: list = [user_id]
        if month:
            sql += " AND to_char(txn_date, 'YYYY-MM') = %s"
            params.append(month)
        sql += " GROUP BY category"
        with self._cursor() as cur:
            cur.execute(sql, params)
            return {r[0]: {"total": float(r[1]), "count": int(r[2])} for r in cur.fetchall()}

    def create_job(self, job_id: str, user_id: str, s3_key: str, filename: str) -> None:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO upload_jobs (job_id, user_id, s3_key, filename, status) VALUES (%s, %s, %s, %s, 'QUEUED')",
                (job_id, user_id, s3_key, filename),
            )

    def get_job(self, job_id: str) -> dict | None:
        with self._cursor() as cur:
            cur.execute(
                "SELECT job_id, user_id, status, rows_inserted, error, created_at, updated_at FROM upload_jobs WHERE job_id = %s",
                (job_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return {"job_id": r[0], "user_id": r[1], "status": r[2], "rows_inserted": r[3], "error": r[4], "created_at": str(r[5]), "updated_at": str(r[6])}

    def update_job_status(self, job_id: str, status: str, rows_inserted: int = 0, error: str = None) -> None:
        with self._cursor() as cur:
            cur.execute(
                "UPDATE upload_jobs SET status = %s, rows_inserted = %s, error = %s, updated_at = NOW() WHERE job_id = %s",
                (status, rows_inserted, error, job_id),
            )

    def set_budget(self, user_id: str, category: str, amount: float) -> None:
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO budgets (user_id, category, amount, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (user_id, category) DO UPDATE SET amount = EXCLUDED.amount, updated_at = NOW()
                """,
                (user_id, category, amount)
            )

    def get_budgets(self, user_id: str) -> dict:
        with self._cursor() as cur:
            cur.execute("SELECT category, amount FROM budgets WHERE user_id = %s", (user_id,))
            return {r[0]: float(r[1]) for r in cur.fetchall()}

    def get_or_create_chat_session(self, user_id: str, session_id: str | None = None) -> dict:
        session_id = session_id or str(uuid.uuid4())
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_sessions (id, user_id)
                VALUES (%s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (session_id, user_id),
            )
            cur.execute(
                """
                SELECT id, user_id, summary, profile_json, message_count, summarized_through_id
                FROM chat_sessions
                WHERE id = %s AND user_id = %s
                """,
                (session_id, user_id),
            )
            r = cur.fetchone()
            if not r:
                raise ValueError("Chat session does not belong to this user")
            profile = r[3] if isinstance(r[3], dict) else json.loads(r[3] or "{}")
            return {
                "id": r[0],
                "user_id": r[1],
                "summary": r[2] or "",
                "profile": profile,
                "message_count": int(r[4] or 0),
                "summarized_through_id": int(r[5] or 0),
            }

    def add_chat_message(self, user_id: str, session_id: str, role: str, content: str) -> int:
        if role not in {"user", "assistant"}:
            raise ValueError("role must be user or assistant")
        token_estimate = max(1, len(content) // 4)
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_messages (session_id, user_id, role, content, token_estimate)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (session_id, user_id, role, content, token_estimate),
            )
            message_id = cur.fetchone()[0]
            cur.execute(
                """
                UPDATE chat_sessions
                SET message_count = message_count + 1, updated_at = NOW()
                WHERE id = %s AND user_id = %s
                """,
                (session_id, user_id),
            )
            return int(message_id)

    def list_recent_chat_messages(self, user_id: str, session_id: str, limit: int = 8) -> list:
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT id, role, content, created_at
                FROM (
                    SELECT id, role, content, created_at
                    FROM chat_messages
                    WHERE user_id = %s AND session_id = %s
                    ORDER BY id DESC
                    LIMIT %s
                ) recent
                ORDER BY id ASC
                """,
                (user_id, session_id, limit),
            )
            return [{"id": r[0], "role": r[1], "text": r[2], "created_at": str(r[3])} for r in cur.fetchall()]

    def list_chat_messages_for_summary(self, user_id: str, session_id: str, keep_recent: int = 8, limit: int = 20) -> list:
        session = self.get_or_create_chat_session(user_id, session_id)
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT id, role, content
                FROM chat_messages
                WHERE user_id = %s AND session_id = %s AND id > %s
                ORDER BY id ASC
                """,
                (user_id, session_id, session["summarized_through_id"]),
            )
            rows = cur.fetchall()
        compactable = rows[:-keep_recent] if len(rows) > keep_recent else []
        return [{"id": r[0], "role": r[1], "text": r[2]} for r in compactable[:limit]]

    def update_chat_summary(self, user_id: str, session_id: str, summary: str, summarized_through_id: int) -> None:
        with self._cursor() as cur:
            cur.execute(
                """
                UPDATE chat_sessions
                SET summary = %s, summarized_through_id = GREATEST(summarized_through_id, %s), updated_at = NOW()
                WHERE id = %s AND user_id = %s
                """,
                (summary, summarized_through_id, session_id, user_id),
            )

    def find_uploaded_file(self, user_id: str, file_hash: str) -> dict | None:
        with self._cursor() as cur:
            cur.execute(
                "SELECT id, filename, file_type, transaction_count, uploaded_at "
                "FROM uploaded_files WHERE user_id = %s AND file_hash = %s ORDER BY uploaded_at DESC LIMIT 1",
                (user_id, file_hash),
            )
            r = cur.fetchone()
            if not r:
                return None
            return {"id": r[0], "filename": r[1], "file_type": r[2],
                    "transaction_count": r[3], "uploaded_at": str(r[4])}

    def save_uploaded_file(self, user_id: str, file_hash: str, filename: str,
                           file_type: str, file_size: int, transaction_count: int) -> str:
        file_id = str(uuid.uuid4())
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO uploaded_files (id, user_id, file_hash, filename, file_type, file_size, transaction_count) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (file_id, user_id, file_hash, filename, file_type, file_size, transaction_count),
            )
        return file_id

    def delete_transactions_by_file(self, user_id: str, file_id: str) -> int:
        with self._cursor() as cur:
            cur.execute("DELETE FROM transactions WHERE user_id = %s AND file_id = %s", (user_id, file_id))
            return cur.rowcount

    def save_receipt_extraction(self, user_id: str, pdf_hash: str, extracted_fingerprint: str,
                                extracted_raw: str, transaction_id: str | None = None) -> str:
        rid = str(uuid.uuid4())
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO receipt_extractions "
                "(id, user_id, pdf_hash, extracted_fingerprint, extracted_raw, transaction_id) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (rid, user_id, pdf_hash, extracted_fingerprint, extracted_raw, self._as_id(transaction_id)),
            )
        return rid

    def find_receipt_by_fingerprint(self, user_id: str, fingerprint: str) -> list:
        with self._cursor() as cur:
            cur.execute(
                "SELECT id, pdf_hash, created_at FROM receipt_extractions "
                "WHERE user_id = %s AND extracted_fingerprint = %s",
                (user_id, fingerprint),
            )
            return [{"id": r[0], "pdf_hash": r[1], "created_at": str(r[2])} for r in cur.fetchall()]

    def log_cost(self, entry: dict) -> None:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO cost_log "
                "(ts, user_id, flow, model_id, input_tokens, output_tokens, "
                "cache_read_tokens, cache_write_tokens, latency_ms, estimated_cost_usd) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (entry["ts"], entry["user_id"], entry["flow"], entry["model_id"],
                 entry["input_tokens"], entry["output_tokens"],
                 entry.get("cache_read_tokens", 0), entry.get("cache_write_tokens", 0),
                 entry["latency_ms"], entry["estimated_cost_usd"]),
            )

    def aggregate_costs(self, user_id: str, month: str | None = None) -> dict:
        where = ["user_id = %s"]
        params: list = [user_id]
        if month:
            where.append("substr(ts, 1, 7) = %s")
            params.append(month)
        clause = " AND ".join(where)
        with self._cursor() as cur:
            cur.execute(
                f"SELECT COALESCE(SUM(estimated_cost_usd),0), COALESCE(SUM(input_tokens),0), "
                f"COALESCE(SUM(output_tokens),0) FROM cost_log WHERE {clause}", params)
            total = cur.fetchone()
            cur.execute(f"SELECT flow, COALESCE(SUM(estimated_cost_usd),0) FROM cost_log WHERE {clause} GROUP BY flow", params)
            by_flow = cur.fetchall()
            cur.execute(
                f"SELECT substr(ts,1,10) d, COALESCE(SUM(estimated_cost_usd),0) "
                f"FROM cost_log WHERE {clause} GROUP BY d ORDER BY d", params)
            by_day = cur.fetchall()
        return {
            "total_cost_usd": round(total[0], 6),
            "tokens_total": {"input": int(total[1]), "output": int(total[2])},
            "by_flow": {r[0]: round(r[1], 6) for r in by_flow},
            "by_day": [{"date": r[0], "cost_usd": round(r[1], 6)} for r in by_day],
        }

    def usage_stats(self, user_id: str, month: str | None = None) -> dict:
        cost = self.aggregate_costs(user_id, month)
        awhere = ["user_id = %s"]
        aparams: list = [user_id]
        if month:
            awhere.append("to_char(ts, 'YYYY-MM') = %s")
            aparams.append(month)
        aclause = " AND ".join(awhere)
        cwhere = ["user_id = %s"]
        cparams: list = [user_id]
        if month:
            cwhere.append("substr(ts, 1, 7) = %s")
            cparams.append(month)
        cclause = " AND ".join(cwhere)
        with self._cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM classification_audit WHERE {aclause}", aparams)
            total = cur.fetchone()[0]
            cur.execute(f"SELECT source, COUNT(*) FROM classification_audit WHERE {aclause} GROUP BY source", aparams)
            by_source = {r[0]: r[1] for r in cur.fetchall()}
            cur.execute(f"SELECT COUNT(*) FROM classification_audit WHERE {aclause} AND needs_review = TRUE", aparams)
            review_cnt = cur.fetchone()[0]
            cur.execute(f"SELECT latency_ms FROM cost_log WHERE {cclause} AND latency_ms > 0", cparams)
            latencies = [r[0] for r in cur.fetchall()]

        def pct(n: int) -> float:
            return round(n / total * 100, 1) if total else 0.0

        return {
            "month": month,
            "total_cost_usd": cost["total_cost_usd"],
            "tokens_total": cost["tokens_total"],
            "by_flow": cost["by_flow"],
            "classifications": int(total),
            "by_source": by_source,
            "catalog_hit_rate_pct": pct(by_source.get("cache", 0)),
            "needs_review_rate_pct": pct(review_cnt),
            "latency_ms": {
                "p50": _percentile(latencies, 50),
                "p95": _percentile(latencies, 95),
                "max": max(latencies) if latencies else 0,
            },
        }

    def catalog_lookup(self, user_id: str, desc_hash: str) -> dict | None:
        with self._cursor() as cur:
            cur.execute(
                "SELECT category, confidence_sum, sample_count FROM merchant_catalog "
                "WHERE user_id = %s AND desc_hash = %s", (user_id, desc_hash))
            r = cur.fetchone()
        if not r:
            return None
        count = int(r[2] or 0)
        avg = (r[1] / count) if count else 0.0
        return {"category": r[0], "avg_confidence": round(avg, 4), "sample_count": count}

    def catalog_record(self, user_id: str, desc_hash: str, category: str, score: float) -> None:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO merchant_catalog (user_id, desc_hash, category, confidence_sum, sample_count, last_seen) "
                "VALUES (%s, %s, %s, %s, 1, NOW()) "
                "ON CONFLICT (user_id, desc_hash) DO UPDATE SET "
                "  confidence_sum = CASE WHEN merchant_catalog.category = EXCLUDED.category "
                "                   THEN merchant_catalog.confidence_sum + EXCLUDED.confidence_sum ELSE EXCLUDED.confidence_sum END, "
                "  sample_count = CASE WHEN merchant_catalog.category = EXCLUDED.category "
                "                 THEN merchant_catalog.sample_count + 1 ELSE 1 END, "
                "  category = EXCLUDED.category, last_seen = NOW()",
                (user_id, desc_hash, category, score),
            )

    def record_classification_audit(self, user_id: str, transaction_id: str | None, *, source: str,
                                    category: str, confidence: str, needs_review: bool,
                                    prompt_version: str, model_id: str) -> None:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO classification_audit "
                "(user_id, transaction_id, source, category, confidence, needs_review, prompt_version, model_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (user_id, transaction_id, source, category, confidence, bool(needs_review), prompt_version, model_id),
            )

    def list_classification_audit(self, user_id: str, transaction_id: str) -> list:
        with self._cursor() as cur:
            cur.execute(
                "SELECT source, category, confidence, needs_review, prompt_version, model_id, ts "
                "FROM classification_audit WHERE user_id = %s AND transaction_id = %s ORDER BY id DESC",
                (user_id, transaction_id),
            )
            return [
                {"source": r[0], "category": r[1], "confidence": r[2], "needs_review": bool(r[3]),
                 "prompt_version": r[4], "model_id": r[5], "ts": str(r[6])}
                for r in cur.fetchall()
            ]

    def idempotency_get(self, user_id: str, idem_key: str, ttl_days: int | None = None) -> str | None:
        sql = "SELECT response_json FROM idempotency WHERE user_id = %s AND idem_key = %s"
        params: list = [user_id, idem_key]
        if ttl_days:
            sql += " AND created_at >= NOW() - (%s * INTERVAL '1 day')"
            params.append(ttl_days)
        with self._cursor() as cur:
            cur.execute(sql, params)
            r = cur.fetchone()
            return r[0] if r else None

    def idempotency_put(self, user_id: str, idem_key: str, response_json: str, ttl_days: int | None = None) -> None:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO idempotency (user_id, idem_key, response_json) VALUES (%s, %s, %s) "
                "ON CONFLICT (user_id, idem_key) DO NOTHING",
                (user_id, idem_key, response_json),
            )
            if ttl_days:
                cur.execute("DELETE FROM idempotency WHERE created_at < NOW() - (%s * INTERVAL '1 day')", (ttl_days,))


class SQLiteUserStore:
    """SQLite store. FastAPI runs sync routes in a thread pool, so requests hit
    the store concurrently — we give each thread its OWN connection (thread-local)
    plus WAL + busy_timeout, instead of sharing one connection (which races:
    'database is locked' / recursive cursor use). WAL allows concurrent readers
    with a single writer; busy_timeout makes a writer wait rather than error."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._local = threading.local()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @property
    def conn(self):
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(self._db_path, check_same_thread=False)
            c.execute("PRAGMA busy_timeout = 5000")
            c.execute("PRAGMA journal_mode = WAL")
            self._local.conn = c
        return c

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                txn_date TEXT NOT NULL,
                description TEXT,
                amount REAL,
                category TEXT,
                confidence TEXT,
                source TEXT DEFAULT 'csv',
                fingerprint TEXT,
                file_id TEXT,
                needs_review INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS txn_user_date_idx ON transactions(user_id, txn_date);
            CREATE INDEX IF NOT EXISTS txn_user_cat_idx ON transactions(user_id, category);
            CREATE INDEX IF NOT EXISTS txn_user_fp_idx ON transactions(user_id, fingerprint);
            CREATE TABLE IF NOT EXISTS cost_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                user_id TEXT NOT NULL,
                flow TEXT NOT NULL,
                model_id TEXT,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cache_read_tokens INTEGER DEFAULT 0,
                cache_write_tokens INTEGER DEFAULT 0,
                latency_ms INTEGER DEFAULT 0,
                estimated_cost_usd REAL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS cost_user_ts_idx ON cost_log(user_id, ts);
            CREATE TABLE IF NOT EXISTS uploaded_files (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                filename TEXT,
                file_type TEXT,
                file_size INTEGER,
                transaction_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'processed',
                uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS uploaded_user_hash_idx ON uploaded_files(user_id, file_hash);
            CREATE TABLE IF NOT EXISTS receipt_extractions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                pdf_hash TEXT,
                extracted_fingerprint TEXT,
                extracted_raw TEXT,
                transaction_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS receipt_user_fp_idx ON receipt_extractions(user_id, extracted_fingerprint);
            CREATE TABLE IF NOT EXISTS merchant_catalog (
                user_id TEXT NOT NULL,
                desc_hash TEXT NOT NULL,
                category TEXT NOT NULL,
                confidence_sum REAL NOT NULL DEFAULT 0,
                sample_count INTEGER NOT NULL DEFAULT 0,
                last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, desc_hash)
            );
            CREATE TABLE IF NOT EXISTS classification_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                transaction_id TEXT,
                source TEXT,
                category TEXT,
                confidence TEXT,
                needs_review INTEGER DEFAULT 0,
                prompt_version TEXT,
                model_id TEXT,
                ts TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS audit_user_txn_idx ON classification_audit(user_id, transaction_id);
            CREATE TABLE IF NOT EXISTS idempotency (
                user_id TEXT NOT NULL,
                idem_key TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, idem_key)
            );
            CREATE TABLE IF NOT EXISTS upload_jobs (
                job_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                s3_key TEXT NOT NULL,
                filename TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'QUEUED',
                rows_inserted INTEGER DEFAULT 0,
                error TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS budgets (
                user_id TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, category)
            );
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                profile_json TEXT NOT NULL DEFAULT '{}',
                message_count INTEGER NOT NULL DEFAULT 0,
                summarized_through_id INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS chat_sessions_user_idx ON chat_sessions(user_id, updated_at DESC);
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                token_estimate INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS chat_messages_session_id_idx ON chat_messages(session_id, id DESC);
        """)
        self.conn.commit()

    def add_transaction(self, user_id: str, txn: dict) -> str:
        """Insert a transaction; returns the new id as a string."""
        cur = self.conn.execute(
            "INSERT INTO transactions "
            "(user_id, txn_date, description, amount, category, confidence, source, fingerprint, file_id, needs_review) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id, txn["date"], txn["description"], float(txn["amount"]),
                txn["category"], txn.get("confidence", ""),
                txn.get("source", "csv"), txn.get("fingerprint"), txn.get("file_id"),
                1 if txn.get("needs_review") else 0,
            ),
        )
        self.conn.commit()
        return str(cur.lastrowid)

    def _row_to_dict(self, r) -> dict:
        return {
            "id": str(r[0]), "date": r[1], "description": r[2], "amount": r[3],
            "category": r[4], "confidence": r[5], "source": r[6] or "csv",
            "needs_review": bool(r[7]) if len(r) > 7 else False,
        }

    def list_transactions(self, user_id: str, month: str | None = None) -> list:
        sql = ("SELECT id, txn_date, description, amount, category, confidence, source, needs_review "
               "FROM transactions WHERE user_id = ?")
        params: list = [user_id]
        if month:
            sql += " AND substr(txn_date, 1, 7) = ?"
            params.append(month)
        sql += " ORDER BY txn_date DESC, id DESC"
        cur = self.conn.execute(sql, params)
        return [self._row_to_dict(r) for r in cur.fetchall()]

    def get_transaction(self, user_id: str, txn_id: str) -> dict | None:
        cur = self.conn.execute(
            "SELECT id, txn_date, description, amount, category, confidence, source, needs_review "
            "FROM transactions WHERE user_id = ? AND id = ?",
            (user_id, txn_id),
        )
        r = cur.fetchone()
        return self._row_to_dict(r) if r else None

    def update_transaction(self, user_id: str, txn_id: str, fields: dict) -> dict | None:
        """Partial update. Recomputes fingerprint when amount/description change."""
        col_map = {"date": "txn_date", "amount": "amount",
                   "description": "description", "category": "category"}
        sets, params = [], []
        for key, col in col_map.items():
            if key in fields and fields[key] is not None:
                sets.append(f"{col} = ?")
                params.append(fields[key])
        if fields.get("category"):
            sets.append("needs_review = 0")
        if not sets:
            return self.get_transaction(user_id, txn_id)
        if "amount" in fields or "description" in fields:
            existing = self.get_transaction(user_id, txn_id)
            if existing:
                from ..dedup.normalize import transaction_fingerprint
                amt = fields.get("amount", existing["amount"])
                desc = fields.get("description", existing["description"])
                sets.append("fingerprint = ?")
                params.append(transaction_fingerprint(user_id, amt, desc))
        params += [user_id, txn_id]
        self.conn.execute(
            f"UPDATE transactions SET {', '.join(sets)} WHERE user_id = ? AND id = ?",
            params,
        )
        self.conn.commit()
        return self.get_transaction(user_id, txn_id)

    def list_filtered(
        self, user_id: str, month: str | None = None, category: str | None = None,
        source: str | None = None, search: str | None = None,
        page: int = 1, page_size: int = 50,
    ) -> tuple[list, int]:
        """Filtered + paginated list. Returns (rows, total_matching)."""
        where = ["user_id = ?"]
        params: list = [user_id]
        if month:
            where.append("substr(txn_date, 1, 7) = ?")
            params.append(month)
        if category:
            where.append("category = ?")
            params.append(category)
        if source:
            where.append("source = ?")
            params.append(source)
        if search:
            where.append("LOWER(description) LIKE ?")
            params.append(f"%{search.lower()}%")
        clause = " AND ".join(where)

        total = self.conn.execute(
            f"SELECT COUNT(*) FROM transactions WHERE {clause}", params
        ).fetchone()[0]

        offset = max(0, (page - 1) * page_size)
        cur = self.conn.execute(
            "SELECT id, txn_date, description, amount, category, confidence, source, needs_review "
            f"FROM transactions WHERE {clause} ORDER BY txn_date DESC, id DESC LIMIT ? OFFSET ?",
            [*params, page_size, offset],
        )
        return [self._row_to_dict(r) for r in cur.fetchall()], int(total)

    def find_transactions_by_fingerprint(self, user_id: str, fingerprint: str) -> list:
        cur = self.conn.execute(
            "SELECT id, txn_date, description, amount, category, confidence, source, needs_review "
            "FROM transactions WHERE user_id = ? AND fingerprint = ?",
            (user_id, fingerprint),
        )
        return [self._row_to_dict(r) for r in cur.fetchall()]

    def find_uploaded_file(self, user_id: str, file_hash: str) -> dict | None:
        cur = self.conn.execute(
            "SELECT id, filename, file_type, transaction_count, uploaded_at "
            "FROM uploaded_files WHERE user_id = ? AND file_hash = ? "
            "ORDER BY uploaded_at DESC LIMIT 1",
            (user_id, file_hash),
        )
        r = cur.fetchone()
        if not r:
            return None
        return {"id": r[0], "filename": r[1], "file_type": r[2],
                "transaction_count": r[3], "uploaded_at": r[4]}

    def save_uploaded_file(self, user_id: str, file_hash: str, filename: str,
                           file_type: str, file_size: int, transaction_count: int) -> str:
        file_id = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO uploaded_files "
            "(id, user_id, file_hash, filename, file_type, file_size, transaction_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (file_id, user_id, file_hash, filename, file_type, file_size, transaction_count),
        )
        self.conn.commit()
        return file_id

    def delete_transactions_by_file(self, user_id: str, file_id: str) -> int:
        cur = self.conn.execute(
            "DELETE FROM transactions WHERE user_id = ? AND file_id = ?", (user_id, file_id)
        )
        self.conn.commit()
        return cur.rowcount

    def save_receipt_extraction(self, user_id: str, pdf_hash: str,
                                extracted_fingerprint: str, extracted_raw: str,
                                transaction_id: str | None = None) -> str:
        rid = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO receipt_extractions "
            "(id, user_id, pdf_hash, extracted_fingerprint, extracted_raw, transaction_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (rid, user_id, pdf_hash, extracted_fingerprint, extracted_raw, transaction_id),
        )
        self.conn.commit()
        return rid

    def find_receipt_by_fingerprint(self, user_id: str, fingerprint: str) -> list:
        cur = self.conn.execute(
            "SELECT id, pdf_hash, created_at FROM receipt_extractions "
            "WHERE user_id = ? AND extracted_fingerprint = ?",
            (user_id, fingerprint),
        )
        return [{"id": r[0], "pdf_hash": r[1], "created_at": r[2]} for r in cur.fetchall()]

    def log_cost(self, entry: dict) -> None:
        self.conn.execute(
            "INSERT INTO cost_log "
            "(ts, user_id, flow, model_id, input_tokens, output_tokens, "
            "cache_read_tokens, cache_write_tokens, latency_ms, estimated_cost_usd) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (entry["ts"], entry["user_id"], entry["flow"], entry["model_id"],
             entry["input_tokens"], entry["output_tokens"],
             entry.get("cache_read_tokens", 0), entry.get("cache_write_tokens", 0),
             entry["latency_ms"], entry["estimated_cost_usd"]),
        )
        self.conn.commit()

    def aggregate_costs(self, user_id: str, month: str | None = None) -> dict:
        where = ["user_id = ?"]
        params: list = [user_id]
        if month:
            where.append("substr(ts, 1, 7) = ?")
            params.append(month)
        clause = " AND ".join(where)
        total = self.conn.execute(
            f"SELECT COALESCE(SUM(estimated_cost_usd),0), COALESCE(SUM(input_tokens),0), "
            f"COALESCE(SUM(output_tokens),0) FROM cost_log WHERE {clause}", params
        ).fetchone()
        by_flow = self.conn.execute(
            f"SELECT flow, COALESCE(SUM(estimated_cost_usd),0) FROM cost_log WHERE {clause} GROUP BY flow",
            params,
        ).fetchall()
        by_day = self.conn.execute(
            f"SELECT substr(ts,1,10) d, COALESCE(SUM(estimated_cost_usd),0) "
            f"FROM cost_log WHERE {clause} GROUP BY d ORDER BY d", params
        ).fetchall()
        return {
            "total_cost_usd": round(total[0], 6),
            "tokens_total": {"input": int(total[1]), "output": int(total[2])},
            "by_flow": {r[0]: round(r[1], 6) for r in by_flow},
            "by_day": [{"date": r[0], "cost_usd": round(r[1], 6)} for r in by_day],
        }

    def catalog_lookup(self, user_id: str, desc_hash: str) -> dict | None:
        """Return {category, avg_confidence, sample_count} for a merchant, or None."""
        r = self.conn.execute(
            "SELECT category, confidence_sum, sample_count FROM merchant_catalog "
            "WHERE user_id = ? AND desc_hash = ?",
            (user_id, desc_hash),
        ).fetchone()
        if not r:
            return None
        count = int(r[2] or 0)
        avg = (r[1] / count) if count else 0.0
        return {"category": r[0], "avg_confidence": round(avg, 4), "sample_count": count}

    def catalog_record(self, user_id: str, desc_hash: str, category: str, score: float) -> None:
        """Accumulate a classification. Same category → running avg; a different
        category resets the entry to the new one (the merchant was re-labelled)."""
        self.conn.execute(
            "INSERT INTO merchant_catalog "
            "(user_id, desc_hash, category, confidence_sum, sample_count, last_seen) "
            "VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP) "
            "ON CONFLICT(user_id, desc_hash) DO UPDATE SET "
            "  confidence_sum = CASE WHEN category = excluded.category "
            "                   THEN confidence_sum + excluded.confidence_sum ELSE excluded.confidence_sum END, "
            "  sample_count = CASE WHEN category = excluded.category THEN sample_count + 1 ELSE 1 END, "
            "  category = excluded.category, "
            "  last_seen = CURRENT_TIMESTAMP",
            (user_id, desc_hash, category, score),
        )
        self.conn.commit()

    def idempotency_get(self, user_id: str, idem_key: str, ttl_days: int | None = None) -> str | None:
        sql = "SELECT response_json FROM idempotency WHERE user_id = ? AND idem_key = ?"
        params: list = [user_id, idem_key]
        if ttl_days:
            sql += " AND created_at >= datetime('now', ?)"
            params.append(f"-{ttl_days} days")
        r = self.conn.execute(sql, params).fetchone()
        return r[0] if r else None

    def idempotency_put(self, user_id: str, idem_key: str, response_json: str, ttl_days: int | None = None) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO idempotency (user_id, idem_key, response_json) VALUES (?, ?, ?)",
            (user_id, idem_key, response_json),
        )
        if ttl_days:
            self.conn.execute(
                "DELETE FROM idempotency WHERE created_at < datetime('now', ?)",
                (f"-{ttl_days} days",),
            )
        self.conn.commit()

    def record_classification_audit(
        self, user_id: str, transaction_id: str | None, *, source: str,
        category: str, confidence: str, needs_review: bool,
        prompt_version: str, model_id: str,
    ) -> None:
        """Append an audit row explaining how a transaction was categorized.

        PII-safe by construction: stores the classification source + version +
        model, never the raw prompt or description.
        """
        self.conn.execute(
            "INSERT INTO classification_audit "
            "(user_id, transaction_id, source, category, confidence, needs_review, prompt_version, model_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, transaction_id, source, category, confidence,
             1 if needs_review else 0, prompt_version, model_id),
        )
        self.conn.commit()

    def list_classification_audit(self, user_id: str, transaction_id: str) -> list[dict]:
        cur = self.conn.execute(
            "SELECT source, category, confidence, needs_review, prompt_version, model_id, ts "
            "FROM classification_audit WHERE user_id = ? AND transaction_id = ? ORDER BY id DESC",
            (user_id, transaction_id),
        )
        return [
            {"source": r[0], "category": r[1], "confidence": r[2],
             "needs_review": bool(r[3]), "prompt_version": r[4], "model_id": r[5], "ts": r[6]}
            for r in cur.fetchall()
        ]

    def usage_stats(self, user_id: str, month: str | None = None) -> dict:
        """Aggregate cost + audit into ops metrics: cost by flow, classification
        sources, catalog-hit %, needs-review %, and latency p50/p95."""
        cost = self.aggregate_costs(user_id, month)

        awhere = ["user_id = ?"]
        aparams: list = [user_id]
        if month:
            awhere.append("substr(ts, 1, 7) = ?")
            aparams.append(month)
        aclause = " AND ".join(awhere)

        total = self.conn.execute(
            f"SELECT COUNT(*) FROM classification_audit WHERE {aclause}", aparams
        ).fetchone()[0]
        by_source = {
            r[0]: r[1]
            for r in self.conn.execute(
                f"SELECT source, COUNT(*) FROM classification_audit WHERE {aclause} GROUP BY source",
                aparams,
            ).fetchall()
        }
        review_cnt = self.conn.execute(
            f"SELECT COUNT(*) FROM classification_audit WHERE {aclause} AND needs_review = 1",
            aparams,
        ).fetchone()[0]
        latencies = [
            r[0] for r in self.conn.execute(
                f"SELECT latency_ms FROM cost_log WHERE {aclause} AND latency_ms > 0",
                aparams,
            ).fetchall()
        ]

        def pct(n: int) -> float:
            return round(n / total * 100, 1) if total else 0.0

        return {
            "month": month,
            "total_cost_usd": cost["total_cost_usd"],
            "tokens_total": cost["tokens_total"],
            "by_flow": cost["by_flow"],
            "classifications": int(total),
            "by_source": by_source,
            "catalog_hit_rate_pct": pct(by_source.get("cache", 0)),
            "needs_review_rate_pct": pct(review_cnt),
            "latency_ms": {
                "p50": _percentile(latencies, 50),
                "p95": _percentile(latencies, 95),
                "max": max(latencies) if latencies else 0,
            },
        }

    def migrate(self) -> dict:
        """Idempotent: add dedup columns to existing DBs + backfill fingerprints."""
        from ..dedup.normalize import transaction_fingerprint

        existing_cols = {
            row[1] for row in self.conn.execute("PRAGMA table_info(transactions)").fetchall()
        }
        for col, ddl in (("source", "ALTER TABLE transactions ADD COLUMN source TEXT DEFAULT 'csv'"),
                         ("fingerprint", "ALTER TABLE transactions ADD COLUMN fingerprint TEXT"),
                         ("file_id", "ALTER TABLE transactions ADD COLUMN file_id TEXT")):
            if col not in existing_cols:
                self.conn.execute(ddl)
        self._init_schema()
        rows = self.conn.execute(
            "SELECT id, user_id, amount, description FROM transactions WHERE fingerprint IS NULL"
        ).fetchall()
        for r in rows:
            self.conn.execute(
                "UPDATE transactions SET fingerprint = ? WHERE id = ?",
                (transaction_fingerprint(r[1], r[2], r[3]), r[0]),
            )
        self.conn.commit()
        return {"backfilled": len(rows)}

    def update_category(self, user_id: str, txn_id: int, new_category: str) -> None:
        self.conn.execute(
            "UPDATE transactions SET category = ?, confidence = 'high', needs_review = 0 "
            "WHERE user_id = ? AND id = ?",
            (new_category, user_id, txn_id)
        )
        self.conn.commit()

    def clear_transactions(self, user_id: str) -> None:
        self.conn.execute("DELETE FROM transactions WHERE user_id = ?", (user_id,))
        self.conn.commit()

    def clear_chat_memory(self, user_id: str) -> None:
        self.conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,))
        self.conn.execute("DELETE FROM chat_sessions WHERE user_id = ?", (user_id,))
        self.conn.commit()

    def clear_chat_session(self, user_id: str, session_id: str) -> None:
        self.conn.execute("DELETE FROM chat_messages WHERE user_id = ? AND session_id = ?", (user_id, session_id))
        self.conn.execute("DELETE FROM chat_sessions WHERE user_id = ? AND id = ?", (user_id, session_id))
        self.conn.commit()

    def delete_transaction(self, user_id: str, txn_id: int) -> None:
        self.conn.execute("DELETE FROM transactions WHERE user_id = ? AND id = ?", (user_id, txn_id))
        self.conn.commit()

    def summary(self, user_id: str, month: str | None = None) -> dict:
        return _aggregate(self.list_transactions(user_id, month))

    def create_job(self, job_id: str, user_id: str, s3_key: str, filename: str) -> None:
        self.conn.execute(
            "INSERT INTO upload_jobs (job_id, user_id, s3_key, filename, status) VALUES (?, ?, ?, ?, 'QUEUED')",
            (job_id, user_id, s3_key, filename),
        )
        self.conn.commit()

    def get_job(self, job_id: str) -> dict | None:
        cur = self.conn.execute(
            "SELECT job_id, user_id, status, rows_inserted, error, created_at, updated_at FROM upload_jobs WHERE job_id = ?",
            (job_id,),
        )
        r = cur.fetchone()
        if not r:
            return None
        return {"job_id": r[0], "user_id": r[1], "status": r[2], "rows_inserted": r[3], "error": r[4], "created_at": r[5], "updated_at": r[6]}

    def update_job_status(self, job_id: str, status: str, rows_inserted: int = 0, error: str = None) -> None:
        self.conn.execute(
            "UPDATE upload_jobs SET status = ?, rows_inserted = ?, error = ?, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
            (status, rows_inserted, error, job_id),
        )
        self.conn.commit()

    def set_budget(self, user_id: str, category: str, amount: float) -> None:
        self.conn.execute(
            """
            INSERT INTO budgets (user_id, category, amount, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, category) DO UPDATE SET amount=excluded.amount, updated_at=CURRENT_TIMESTAMP
            """,
            (user_id, category, float(amount))
        )
        self.conn.commit()

    def get_budgets(self, user_id: str) -> dict:
        cur = self.conn.execute("SELECT category, amount FROM budgets WHERE user_id = ?", (user_id,))
        return {r[0]: r[1] for r in cur.fetchall()}

    def get_or_create_chat_session(self, user_id: str, session_id: str | None = None) -> dict:
        session_id = session_id or str(uuid.uuid4())
        self.conn.execute(
            "INSERT OR IGNORE INTO chat_sessions (id, user_id) VALUES (?, ?)",
            (session_id, user_id),
        )
        self.conn.commit()
        cur = self.conn.execute(
            "SELECT id, user_id, summary, profile_json, message_count, summarized_through_id "
            "FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        )
        r = cur.fetchone()
        if not r:
            raise ValueError("Chat session does not belong to this user")
        return {
            "id": r[0],
            "user_id": r[1],
            "summary": r[2] or "",
            "profile": json.loads(r[3] or "{}"),
            "message_count": int(r[4] or 0),
            "summarized_through_id": int(r[5] or 0),
        }

    def add_chat_message(self, user_id: str, session_id: str, role: str, content: str) -> int:
        if role not in {"user", "assistant"}:
            raise ValueError("role must be user or assistant")
        token_estimate = max(1, len(content) // 4)
        cur = self.conn.execute(
            "INSERT INTO chat_messages (session_id, user_id, role, content, token_estimate) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, user_id, role, content, token_estimate),
        )
        self.conn.execute(
            "UPDATE chat_sessions SET message_count = message_count + 1, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        )
        self.conn.commit()
        return int(cur.lastrowid or 0)

    def list_recent_chat_messages(self, user_id: str, session_id: str, limit: int = 8) -> list:
        cur = self.conn.execute(
            """
            SELECT id, role, content, created_at
            FROM (
                SELECT id, role, content, created_at
                FROM chat_messages
                WHERE user_id = ? AND session_id = ?
                ORDER BY id DESC
                LIMIT ?
            ) recent
            ORDER BY id ASC
            """,
            (user_id, session_id, limit),
        )
        return [{"id": r[0], "role": r[1], "text": r[2], "created_at": r[3]} for r in cur.fetchall()]

    def list_chat_messages_for_summary(self, user_id: str, session_id: str, keep_recent: int = 8, limit: int = 20) -> list:
        session = self.get_or_create_chat_session(user_id, session_id)
        cur = self.conn.execute(
            "SELECT id, role, content FROM chat_messages "
            "WHERE user_id = ? AND session_id = ? AND id > ? ORDER BY id ASC",
            (user_id, session_id, session["summarized_through_id"]),
        )
        rows = cur.fetchall()
        compactable = rows[:-keep_recent] if len(rows) > keep_recent else []
        return [{"id": r[0], "role": r[1], "text": r[2]} for r in compactable[:limit]]

    def update_chat_summary(self, user_id: str, session_id: str, summary: str, summarized_through_id: int) -> None:
        self.conn.execute(
            "UPDATE chat_sessions SET summary = ?, summarized_through_id = MAX(summarized_through_id, ?), "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
            (summary, summarized_through_id, session_id, user_id),
        )
        self.conn.commit()


def _percentile(values: list[int], p: int) -> int:
    """Nearest-rank percentile (p in 0–100); 0 for an empty list."""
    if not values:
        return 0
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, (p * len(ordered)) // 100))
    return int(ordered[k])


def _aggregate(rows: list) -> dict:
    agg: dict = defaultdict(lambda: {"total": 0.0, "count": 0})
    for r in rows:
        cat = r.get("category", "Other")
        agg[cat]["total"] += float(r.get("amount", 0))
        agg[cat]["count"] += 1
    return {k: v for k, v in agg.items()}


class DocumentDBUserStore:
    """MongoDB-compatible transactions store. AWS DocumentDB / MongoDB Atlas."""

    def __init__(self, url: str, db_name: str = "budgetbot", tls_ca_file: str = ""):
        try:
            from pymongo import MongoClient
        except ImportError as exc:
            raise ImportError("pymongo not installed. Run: pip install -r requirements-optional.txt") from exc
        if not url:
            raise ValueError("USERSTORE_MONGO_URL must be set")
        kwargs: dict = {}
        if "documentdb" in url.lower() or tls_ca_file:
            kwargs["tls"] = True
        if tls_ca_file:
            kwargs["tlsCAFile"] = tls_ca_file
        self.client = MongoClient(url, **kwargs)
        self.col = self.client[db_name]["transactions"]
        self.col.create_index([("user_id", 1), ("txn_date", -1)])
        self.col.create_index([("user_id", 1), ("category", 1)])
        self.budget_col = self.client[db_name]["budgets"]
        self.budget_col.create_index([("user_id", 1), ("category", 1)], unique=True)

    def add_transaction(self, user_id: str, txn: dict) -> None:
        self.col.insert_one({
            "user_id": user_id,
            "txn_date": txn["date"],
            "description": txn["description"],
            "amount": float(txn["amount"]),
            "category": txn["category"],
            "confidence": txn.get("confidence", ""),
            "created_at": _now(),
        })

    def list_transactions(self, user_id: str, month: str | None = None) -> list:
        q: dict = {"user_id": user_id}
        if month:
            q["txn_date"] = {"$regex": f"^{month}"}
        return [
            {"date": d["txn_date"], "description": d["description"], "amount": d["amount"],
             "category": d["category"], "confidence": d.get("confidence", "")}
            for d in self.col.find(q).sort("txn_date", -1)
        ]

    def summary(self, user_id: str, month: str | None = None) -> dict:
        return _aggregate(self.list_transactions(user_id, month))

    def set_budget(self, user_id: str, category: str, amount: float) -> None:
        self.budget_col.update_one(
            {"user_id": user_id, "category": category},
            {"$set": {"amount": float(amount), "updated_at": _now()}},
            upsert=True
        )

    def get_budgets(self, user_id: str) -> dict:
        return {d["category"]: d["amount"] for d in self.budget_col.find({"user_id": user_id})}


class MySQLUserStore:
    """RDS MySQL / Aurora MySQL adapter. Schema mirrors PostgresUserStore."""

    def __init__(self, url: str):
        try:
            from urllib.parse import urlparse

            import pymysql
        except ImportError as exc:
            raise ImportError("pymysql not installed. Run: pip install -r requirements-optional.txt") from exc
        if not url:
            raise ValueError("USERSTORE_MYSQL_URL must be set")
        p = urlparse(url)
        self.conn = pymysql.connect(
            host=p.hostname, port=p.port or 3306,
            user=p.username, password=p.password,
            database=p.path.lstrip("/"),
            charset="utf8mb4", autocommit=True,
        )
        self._init_schema()

    def _init_schema(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    txn_date DATE NOT NULL,
                    description TEXT,
                    amount DECIMAL(14,2),
                    category VARCHAR(64),
                    confidence VARCHAR(16),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_date (user_id, txn_date),
                    INDEX idx_user_cat (user_id, category)
                ) CHARACTER SET utf8mb4;
                CREATE TABLE IF NOT EXISTS budgets (
                    user_id VARCHAR(255) NOT NULL,
                    category VARCHAR(64) NOT NULL,
                    amount DECIMAL(14,2) NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, category)
                ) CHARACTER SET utf8mb4;
            """)

    def add_transaction(self, user_id: str, txn: dict) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO transactions (user_id, txn_date, description, amount, category, confidence) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (user_id, txn["date"], txn["description"], float(txn["amount"]),
                 txn["category"], txn.get("confidence", "")),
            )

    def list_transactions(self, user_id, month=None):
        sql = "SELECT id, txn_date, description, amount, category, confidence FROM transactions WHERE user_id = %s"
        params: list = [user_id]
        if month:
            sql += " AND DATE_FORMAT(txn_date, '%%Y-%%m') = %s"
            params.append(month)
        sql += " ORDER BY txn_date DESC"
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return [
                {"id": r[0], "date": str(r[1]), "description": r[2], "amount": float(r[3]),
                 "category": r[4], "confidence": r[5]}
                for r in cur.fetchall()
            ]

    def delete_transaction(self, user_id: str, txn_id: int) -> None:
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM transactions WHERE user_id = %s AND id = %s", (user_id, txn_id))

    def summary(self, user_id, month=None):
        sql = "SELECT category, SUM(amount), COUNT(*) FROM transactions WHERE user_id = %s"
        params: list = [user_id]
        if month:
            sql += " AND DATE_FORMAT(txn_date, '%%Y-%%m') = %s"
            params.append(month)
        sql += " GROUP BY category"
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return {r[0]: {"total": float(r[1]), "count": int(r[2])} for r in cur.fetchall()}

    def set_budget(self, user_id: str, category: str, amount: float) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO budgets (user_id, category, amount)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE amount = VALUES(amount)
                """,
                (user_id, category, float(amount))
            )

    def get_budgets(self, user_id: str) -> dict:
        with self.conn.cursor() as cur:
            cur.execute("SELECT category, amount FROM budgets WHERE user_id = %s", (user_id,))
            return {r[0]: float(r[1]) for r in cur.fetchall()}
