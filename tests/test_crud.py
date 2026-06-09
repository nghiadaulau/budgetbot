"""Transaction CRUD + list filters + cost report."""


def _create(client, headers, **over):
    payload = {"date": "2026-06-10", "description": "Test txn", "amount": -100000,
               "category": "Food", "source": "manual"}
    payload.update(over)
    return client.post("/transaction", json=payload, headers=headers).json()["transaction"]


def test_update_partial(client, headers):
    txn = _create(client, headers)
    r = client.put(f"/transaction/{txn['id']}", json={"category": "Transport"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["transaction"]["category"] == "Transport"
    assert r.json()["transaction"]["description"] == "Test txn"


def test_update_not_found(client, headers):
    assert client.put("/transaction/999999", json={"category": "Food"}, headers=headers).status_code == 404


def test_delete(client, headers):
    txn = _create(client, headers)
    assert client.delete(f"/transaction/{txn['id']}", headers=headers).status_code == 204
    assert client.get("/transactions", headers=headers).json()["total"] == 0


def test_list_filters(client, headers):
    _create(client, headers, description="Food A", category="Food", amount=-10000)
    _create(client, headers, description="Shop B", category="Shopping", amount=-20000)
    _create(client, headers, description="Food C", category="Food", amount=-30000)
    by_cat = client.get("/transactions?category=Food", headers=headers).json()
    assert by_cat["total"] == 2
    by_search = client.get("/transactions?search=shop", headers=headers).json()
    assert by_search["total"] == 1


def test_list_pagination(client, headers):
    for i in range(10):
        _create(client, headers, description=f"txn {i}")
    page1 = client.get("/transactions?page=1&page_size=4", headers=headers).json()
    assert page1["total"] == 10 and len(page1["transactions"]) == 4
    page3 = client.get("/transactions?page=3&page_size=4", headers=headers).json()
    assert len(page3["transactions"]) == 2


def test_cost_report_shape(client, headers):
    _create(client, headers)
    r = client.get("/admin/cost-report?month=2026-06", headers=headers).json()
    assert "total_cost_usd" in r and "by_flow" in r and "tokens_total" in r
