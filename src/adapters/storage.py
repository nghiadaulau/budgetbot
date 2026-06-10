"""Object storage adapters (raw uploaded CSVs/PDFs). Same interface as StudyBot."""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class S3Storage:
    def __init__(self, bucket: str, region: str):
        import boto3
        from botocore.config import Config

        if not bucket:
            raise ValueError("STORAGE_BUCKET must be set for S3 backend")

        if not region:
            region = "us-west-2"

        self.s3 = boto3.client(
            "s3",
            region_name=region,
            config=Config(
                connect_timeout=10,
                read_timeout=30,
                retries={
                    "max_attempts": 2,
                    "mode": "standard"
                },
                s3={
                    "addressing_style": "virtual"
                }
            )
        )

        self.bucket = bucket

        logger.info({
            "event": "s3_client_created",
            "bucket": self.bucket,
            "region": self.s3.meta.region_name,
            "endpoint_url": self.s3.meta.endpoint_url
        })

    def put(self, key: str, data: bytes) -> str:
        logger.info({
            "event": "s3_put_start",
            "bucket": self.bucket,
            "key": key,
            "bytes": len(data),
            "region": self.s3.meta.region_name,
            "endpoint_url": self.s3.meta.endpoint_url
        })

        try:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data
            )

            logger.info({
                "event": "s3_put_success",
                "bucket": self.bucket,
                "key": key
            })

            return f"s3://{self.bucket}/{key}"

        except Exception as exc:
            logger.exception({
                "event": "s3_put_failed",
                "bucket": self.bucket,
                "key": key,
                "bytes": len(data),
                "region": self.s3.meta.region_name,
                "endpoint_url": self.s3.meta.endpoint_url,
                "error_type": type(exc).__name__,
                "error": str(exc)
            })
            raise

    def get(self, key: str) -> bytes:
        logger.info({
            "event": "s3_get_start",
            "bucket": self.bucket,
            "key": key,
            "region": self.s3.meta.region_name,
            "endpoint_url": self.s3.meta.endpoint_url
        })

        return self.s3.get_object(
            Bucket=self.bucket,
            Key=key
        )["Body"].read()

    def list(self, prefix: str = "") -> list:
        logger.info({
            "event": "s3_list_start",
            "bucket": self.bucket,
            "prefix": prefix,
            "region": self.s3.meta.region_name,
            "endpoint_url": self.s3.meta.endpoint_url
        })

        resp = self.s3.list_objects_v2(
            Bucket=self.bucket,
            Prefix=prefix
        )
        return [obj["Key"] for obj in resp.get("Contents", [])]

    def generate_presigned_put(self, key: str, expiry: int = 900) -> str:
        """Tạo presigned PUT URL để browser upload file trực tiếp lên S3 (không qua Lambda).

        NOTE: Nếu frontend chạy trên domain khác bucket, cần cấu hình CORS trên S3 bucket:
          AllowedMethods: [PUT], AllowedOrigins: ['*'] (hoặc domain cụ thể)
        """
        logger.info({
            "event": "s3_presign_put_start",
            "bucket": self.bucket,
            "key": key,
            "expiry": expiry,
        })
        url = self.s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ContentType": "application/octet-stream",
            },
            ExpiresIn=expiry,
        )
        logger.info({
            "event": "s3_presign_put_created",
            "bucket": self.bucket,
            "key": key,
        })
        return url


class LocalStorage:
    def __init__(self, base_dir: str):
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, key: str) -> Path:
        """Resolve `key` under base_dir, rejecting path traversal.

        `key` embeds the user-supplied filename, so a crafted value like
        ``../../etc/x`` must never escape the storage root.
        """
        path = (self.base / key).resolve()
        base = self.base.resolve()
        if path != base and base not in path.parents:
            raise ValueError(f"Path traversal rejected: {key!r}")
        return path

    def put(self, key: str, data: bytes) -> str:
        path = self._safe_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return f"file://{path}"

    def get(self, key: str) -> bytes:
        return self._safe_path(key).read_bytes()

    def list(self, prefix: str = "") -> list:
        return [
            str(p.relative_to(self.base))
            for p in self.base.rglob("*") if p.is_file() and str(p.relative_to(self.base)).startswith(prefix)
        ]

    def generate_presigned_put(self, key: str, expiry: int = 900):
        """LocalStorage không hỗ trợ presigned URL — trả về None để caller biết dùng fallback /upload."""
        logger.info({"event": "local_storage_presigned_put_not_supported", "key": key})
        return None
