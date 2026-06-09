"""LocalStorage adapter — round-trip + presign fallback (S3 path needs moto/live)."""
from src.adapters.storage import LocalStorage


def test_local_storage_put_get_roundtrip(tmp_path):
    s = LocalStorage(base_dir=str(tmp_path / "up"))
    s.put("u1/stmt.csv", b"date,amount\n2026-06-01,-1000\n")
    assert s.get("u1/stmt.csv").startswith(b"date,amount")


def test_local_storage_list_prefix(tmp_path):
    s = LocalStorage(base_dir=str(tmp_path / "up"))
    s.put("u1/a.csv", b"a")
    s.put("u1/b.csv", b"b")
    assert len(s.list("u1/")) >= 2


def test_local_storage_presign_returns_none(tmp_path):
    s = LocalStorage(base_dir=str(tmp_path / "up"))
    assert s.generate_presigned_put("u1/stmt.csv") is None
