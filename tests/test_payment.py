# tests/test_payment.py
import pytest

def test_pay_order_flow(client, seeded_admin, admin_auth_header):
    # use admin_auth_header fixture
    headers_admin = admin_auth_header()

    # create product
    prod_payload = {"title":"Lamp","price":250.0,"stock":2}
    resp = client.post("/api/products/", json=prod_payload, headers=headers_admin)
    product = resp.json()
    pid = product["id"]

    # create user
    client.post("/api/auth/register", json={"username":"carlos","email":"carlos@example.com","password":"pw1234","full_name":"Carl"})
    resp = client.post("/api/auth/token", data={"username":"carlos","password":"pw1234"})
    user_token = resp.json()["access_token"]
    headers_user = {"Authorization": f"Bearer {user_token}"}

    # create order
    order_payload = {"items":[{"product_id": pid, "unit_price": product["price"], "quantity":1}], "shipping_address":"Here"}
    resp = client.post("/api/orders/", json=order_payload, headers=headers_user)
    assert resp.status_code == 201, resp.text
    order = resp.json()["order"]
    order_id = order.get("id") or order.get("order_id")

    # pay order with mock card that succeeds
    pay_payload = {"type":"card","card_last4":"4242"}
    resp = client.post(f"/api/orders/{order_id}/pay", json=pay_payload, headers=headers_user)
    assert resp.status_code == 200, resp.text
    j = resp.json()
    assert j.get("ok") is True

    # verify order status is paid
    resp = client.get(f"/api/orders/{order_id}", headers=headers_user)
    assert resp.status_code == 200, resp.text
    order_after = resp.json()
    assert order_after.get("status") == "paid"
