import json
from fastapi.testclient import TestClient


def register_and_token(client: TestClient, username="u_test", email=None, password="pass"):
    if email is None:
        email = f"{username}@example.com"
    # register
    r = client.post("/api/auth/register", json={"username": username, "email": email, "password": password})
    assert r.status_code == 200, r.text
    # obtain token via OAuth2 form
    r2 = client.post("/api/auth/token", data={"username": username, "password": password})
    assert r2.status_code == 200, r2.text
    token = r2.json().get("access_token")
    assert token
    return token


def test_cancel_unpaid_order(client: TestClient):
    token = register_and_token(client, username="user_unpaid")
    headers = {"Authorization": f"Bearer {token}"}
    # create an order with inline items
    payload = {"items": [{"product_id": "p1", "unit_price": 10.0, "quantity": 2}], "shipping_address": "123 test"}
    r = client.post("/api/orders", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body.get("ok") is True
    order = body.get("order")
    assert order
    order_id = order.get("id") or order.get("order_id")
    assert order_id

    # cancel
    rc = client.post(f"/api/orders/{order_id}/cancel", json={}, headers=headers)
    assert rc.status_code == 200, rc.text
    cresp = rc.json()
    assert cresp.get("ok") is True
    updated = cresp.get("order")
    assert updated.get("status") == "cancelled"


def test_cancel_paid_order_with_refund(client: TestClient):
    token = register_and_token(client, username="user_paid")
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"items": [{"product_id": "p2", "unit_price": 5.0, "quantity": 1}], "shipping_address": "addr"}
    r = client.post("/api/orders", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body.get("ok") is True
    order = body.get("order")
    order_id = order.get("id") or order.get("order_id")
    assert order_id

    # pay using test-success card (card_last4 == 4242)
    rp = client.post(f"/api/orders/{order_id}/pay", json={"type": "card", "card_last4": "4242"}, headers=headers)
    assert rp.status_code == 200, rp.text
    payres = rp.json()
    assert payres.get("ok") is True
    # ensure order marked paid in DB
    got = client.get(f"/api/orders/{order_id}", headers=headers)
    assert got.status_code == 200, got.text
    row = got.json()
    assert row.get("status") == "paid" or row.get("last_payment_success") in (True, "True", "1", 1)

    # cancel -> should attempt refund and succeed
    rc = client.post(f"/api/orders/{order_id}/cancel", json={}, headers=headers)
    assert rc.status_code == 200, rc.text
    cresp = rc.json()
    assert cresp.get("ok") is True
    updated = cresp.get("order")
    assert updated.get("status") == "cancelled"
    # refund fields should be present and indicate success
    assert updated.get("last_refund_success") in (True, "True", "1", 1)
    assert updated.get("last_refund_tx") is not None
    assert updated.get("refunded_at") is not None