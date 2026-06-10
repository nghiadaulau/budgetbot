"""Smoke tests — health, budgets, and the chat money-coach (kept endpoints)."""


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    # /health is public — internal backend names are intentionally NOT disclosed.
    assert "ai_backend" not in body and "db_backend" not in body
    assert "require_auth" in body
    assert "Salary" in body["categories"] and "Bills" in body["categories"]


def test_budget_status_uses_abs_spending_and_month_filter(client, headers):
    client.post("/transaction", json={
        "date": "2026-04-03", "description": "Pizza", "amount": -170000,
        "category": "Food", "source": "manual"}, headers=headers)
    client.post("/transaction", json={
        "date": "2026-05-03", "description": "Coffee", "amount": -99000,
        "category": "Food", "source": "manual"}, headers=headers)

    res = client.post("/budgets", json={"category": "Ăn uống", "amount": 100000}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["category"] == "Food"

    april = client.get("/budgets?month=2026-04", headers=headers).json()
    assert april["status"][0]["spent"] == 170000
    assert april["status"][0]["exceeded"] is True

    may = client.get("/budgets?month=2026-05", headers=headers).json()
    assert may["status"][0]["spent"] == 99000
    assert may["status"][0]["exceeded"] is False


def test_transactions_isolated_per_user(client):
    a = {"X-User-Id": "iso-A"}
    b = {"X-User-Id": "iso-B"}
    client.delete("/transactions", headers=a)
    client.delete("/transactions", headers=b)
    client.post("/transaction", json={"date": "2026-06-01", "description": "x", "amount": -1000, "category": "Food", "source": "manual"}, headers=a)
    assert client.get("/transactions", headers=a).json()["total"] == 1
    assert client.get("/transactions", headers=b).json()["total"] == 0


def test_chat_memory_isolated_per_user(app_module):
    store = app_module.userstore
    store.get_or_create_chat_session("chat-a", "session-a")
    store.add_chat_message("chat-a", "session-a", "user", "Tôi muốn tiết kiệm 5 triệu")
    store.get_or_create_chat_session("chat-b", "session-b")
    store.add_chat_message("chat-b", "session-b", "user", "Tôi muốn giảm ăn ngoài")

    a = store.list_recent_chat_messages("chat-a", "session-a", limit=8)
    b = store.list_recent_chat_messages("chat-b", "session-b", limit=8)
    assert "5 triệu" in a[0]["text"]
    assert len(b) == 1 and "ăn ngoài" in b[0]["text"]


def test_chat_endpoint_streams(client, headers, app_module):
    client.post("/transaction", json={"date": "2026-06-01", "description": "Highlands", "amount": -65000, "category": "Food", "source": "manual"}, headers=headers)

    class FakeChatbot:
        def chat(self, **kwargs):
            yield "Bạn đã chi cho ăn uống."

        def summarize_memory(self, existing, messages):
            return existing

    app_module.chatbot_client = FakeChatbot()
    r = client.post("/chat", json={"message": "Tôi chi bao nhiêu?", "session_id": "s1"}, headers=headers)
    assert r.status_code == 200
    assert "ăn uống" in r.text
