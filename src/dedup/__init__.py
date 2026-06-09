"""Deduplication — file-level, transaction-level, manual-warning, PDF-receipt."""
from .normalize import file_hash, normalize_description, transaction_fingerprint
from .service import DedupService, DuplicateFileError

__all__ = [
    "normalize_description",
    "transaction_fingerprint",
    "file_hash",
    "DedupService",
    "DuplicateFileError",
]
