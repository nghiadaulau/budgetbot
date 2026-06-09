"""Async upload path (/enqueue + /job-status) and /admin/usage-stats."""

CSV = (
    b"date,description,amount\n"
    b"2026-06-01,HIGHLANDS COFFEE,-65000\n"
    b"2026-06-02,ZZZ UNKNOWN VENDOR 51,-90000\n"
)


def test_enqueue_inline_completes_and_persists(client, headers):
    r = client.post("/enqueue", files={"file": ("s.csv", CSV, "text/csv")}, headers=headers)
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["status"] == "COMPLETED"
    assert job["rows_inserted"] == 2

    st = client.get(f"/job-status/{job['job_id']}", headers=headers).json()
    assert st["status"] == "COMPLETED"

    listed = client.get("/transactions", headers=headers).json()
    assert listed["total"] == 2


def test_job_status_not_found(client, headers):
    st = client.get("/job-status/does-not-exist", headers=headers).json()
    assert st["status"] == "NOT_FOUND"


def test_usage_stats_reports_sources_and_rates(client, headers):
    client.post("/enqueue", files={"file": ("s.csv", CSV, "text/csv")}, headers=headers)
    stats = client.get("/admin/usage-stats?month=2026-06", headers=headers).json()
    assert stats["classifications"] >= 2
    assert stats["needs_review_rate_pct"] > 0
    assert isinstance(stats["by_source"], dict) and stats["by_source"]
    assert "csv" in stats["by_flow"]
    assert set(stats["latency_ms"]) == {"p50", "p95", "max"}
