"""Excel statement import — single signed amount, and debit/credit columns."""
import io

from openpyxl import Workbook


def _xlsx(headers: list[str], rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["SAO KÊ TÀI KHOẢN"])
    ws.append([])
    ws.append(headers)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_excel_signed_amount(client, headers):
    data = _xlsx(
        ["Ngày", "Diễn giải", "Số tiền"],
        [
            ["2026-06-01", "SALARY JUNE", 28000000],
            ["2026-06-02", "HIGHLANDS COFFEE", -65000],
            ["2026-06-03", "EVN TIEN DIEN", -850000],
        ],
    )
    r = client.post(
        "/upload",
        files={"file": ("sao-ke.xlsx", data,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows_inserted"] == 3
    cats = {t["category"] for t in body["transactions"]}
    assert {"Salary", "Food", "Bills"} <= cats


def test_excel_debit_credit_columns(client, headers):
    data = _xlsx(
        ["Ngày GD", "Nội dung", "Ghi nợ", "Ghi có"],
        [
            ["2026-06-01", "Luong thang 6", "", 28000000],
            ["2026-06-02", "GRAB CITY", 48000, ""],
        ],
    )
    r = client.post(
        "/upload",
        files={"file": ("vcb.xlsx", data,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    txns = {t["description"]: t["amount"] for t in r.json()["transactions"]}
    assert txns["Luong thang 6"] == 28000000
    assert txns["GRAB CITY"] == -48000


def test_excel_unrecognised_columns_400(client, headers):
    data = _xlsx(["Foo", "Bar", "Baz"], [["x", "y", "z"]])
    r = client.post(
        "/upload",
        files={"file": ("weird.xlsx", data,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert r.status_code == 400
