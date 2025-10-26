# tests/test_orders.py
import pytest

def test_create_order_and_list(client, seeded_admin):
    # create admin and product
    resp = client.post("/api/auth/token", data={"username": "admin", "password": "adminpass"})
    admin_token = resp.json()["access_token"]
    headers_admin = {"Authorization": f"Bearer {admin_token}"}

    prod_payload = {"title":"Chair","price":500.0,"stock":5}
    resp = client.post("/api/products/", json=prod_payload, headers=headers_admin)
    assert resp.status_code == 200, resp.text
    product = resp.json()
    pid = product["id"]

    # register user
    user_payload = {"username":"bob","email":"bob@example.com","password":"pass123","full_name":"Bob"}
    resp = client.post("/api/auth/register", json=user_payload)
    assert resp.status_code == 200, resp.text

    # user token
    resp = client.post("/api/auth/token", data={"username":"bob","password":"pass123"})
    user_token = resp.json()["access_token"]
    headers_user = {"Authorization": f"Bearer {user_token}"}

    # create order with items inline
    order_payload = {"items":[{"product_id": pid, "unit_price": product["price"], "quantity":2}], "shipping_address":"Addr"}
    resp = client.post("/api/orders/", json=order_payload, headers=headers_user)
    assert resp.status_code == 201, resp.text
    order = resp.json()["order"]
    order_id = order.get("id") or order.get("order_id")
    assert order_id

    # user fetch own order
    resp = client.get(f"/api/orders/{order_id}", headers=headers_user)
    assert resp.status_code == 200, resp.text

    # admin list orders (should include this one)
    resp = client.get("/api/orders/", headers=headers_admin)
    assert resp.status_code == 200, resp.text
    orders = resp.json()
    assert any(o.get("id")==order_id or o.get("order_id")==order_id for o in orders)
