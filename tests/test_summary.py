"""Summary aggregation + previous-month comparison."""


def _seed(client, headers, month: str, expense: int, income: int):
    client.post("/transaction", json={
        "date": f"{month}-15", "description": "Salary", "amount": income,
        "category": "Salary", "source": "manual"}, headers=headers)
    client.post("/transaction", json={
        "date": f"{month}-16", "description": "Groceries", "amount": -expense,
        "category": "Food", "source": "manual"}, headers=headers)


def test_summary_income_expense_net(client, headers):
    _seed(client, headers, "2026-06", expense=1_200_000, income=18_500_000)
    s = client.get("/summary?month=2026-06", headers=headers).json()
    assert s["total_income"] == 18_500_000
    assert s["total_expense"] == 1_200_000
    assert s["net"] == 17_300_000
    assert s["by_category"][0]["category"] == "Food"
    assert s["by_category"][0]["percentage"] == 100.0


def test_summary_previous_month_comparison(client, headers):
    _seed(client, headers, "2026-05", expense=1_000_000, income=10_000_000)
    _seed(client, headers, "2026-06", expense=1_500_000, income=10_000_000)
    s = client.get("/summary?month=2026-06", headers=headers).json()
    cmp = s["previous_month_comparison"]
    assert cmp["expense_change_pct"] == 50.0
    assert cmp["income_change_pct"] == 0.0


def test_summary_by_category_sorted_desc(client, headers):
    client.post("/transaction", json={"date": "2026-06-01", "description": "a", "amount": -100000, "category": "Food", "source": "manual"}, headers=headers)
    client.post("/transaction", json={"date": "2026-06-02", "description": "b", "amount": -500000, "category": "Shopping", "source": "manual"}, headers=headers)
    s = client.get("/summary?month=2026-06", headers=headers).json()
    amounts = [c["amount"] for c in s["by_category"]]
    assert amounts == sorted(amounts, reverse=True)
