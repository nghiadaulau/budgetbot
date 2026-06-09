"""Manual entry flow — explicit category vs AI auto-classify."""


def test_manual_with_explicit_category(client, headers):
    r = client.post(
        "/transaction",
        json={"date": "2026-06-10", "description": "Random note", "amount": -100000,
              "category": "Shopping", "source": "manual"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["saved"] is True
    assert body["transaction"]["category"] == "Shopping"
    assert body["transaction"]["id"]


def test_manual_without_category_is_ai_classified(client, headers):
    r = client.post(
        "/transaction",
        json={"date": "2026-06-10", "description": "GRAB to airport", "amount": -210000,
              "source": "manual"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["transaction"]["category"] == "Transport"


def test_manual_income_positive_amount(client, headers):
    r = client.post(
        "/transaction",
        json={"date": "2026-06-01", "description": "freelance payout", "amount": 5000000,
              "source": "manual"},
        headers=headers,
    )
    assert r.json()["transaction"]["category"] == "Salary"
