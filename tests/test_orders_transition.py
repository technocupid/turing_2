import uuid

from app.database import db as file_db


def test_owner_can_transition_order(client, seeded_admin, temp_user, token_for, auth_header):
    # create product directly in DB
    prod = file_db.create_record("products", {"title": "Chair", "price": 500.0, "stock": 5}, id_field="id")
    pid = prod["id"]

    # user creates order
    user_token = token_for(temp_user["username"], temp_user["password"])
    headers_user = auth_header(user_token)

    order_payload = {"items": [{"product_id": pid, "unit_price": 500.0, "quantity": 1}]}
    resp = client.post("/api/orders/", json=order_payload, headers=headers_user)
    assert resp.status_code == 201, resp.text
    order = resp.json().get("order") or resp.json()
    oid = order["id"]

    # owner transitions to 'paid'
    resp = client.post(f"/api/orders/{oid}/transition", json={"status": "paid"}, headers=headers_user)
    assert resp.status_code == 200, resp.text
    assert resp.json()["order"]["status"] == "paid"


def test_invalid_transition_returns_400(client, seeded_admin, temp_user, token_for, auth_header):
    prod = file_db.create_record("products", {"title": "Table", "price": 200.0, "stock": 2}, id_field="id")
    pid = prod["id"]

    user_token = token_for(temp_user["username"], temp_user["password"])
    headers_user = auth_header(user_token)

    resp = client.post("/api/orders/", json={"items": [{"product_id": pid, "unit_price": 200.0, "quantity": 1}]}, headers=headers_user)
    assert resp.status_code == 201
    oid = resp.json().get("order")["id"]

    # invalid direct transition placed -> delivered
    resp = client.post(f"/api/orders/{oid}/transition", json={"status": "delivered"}, headers=headers_user)
    assert resp.status_code == 400


def test_admin_can_transition_any_order(client, seeded_admin, temp_user, token_for, auth_header):
    prod = file_db.create_record("products", {"title": "Lamp", "price": 50.0, "stock": 10}, id_field="id")
    pid = prod["id"]

    # user creates order
    user_token = token_for(temp_user["username"], temp_user["password"])
    headers_user = auth_header(user_token)
    resp = client.post("/api/orders/", json={"items": [{"product_id": pid, "unit_price": 50.0, "quantity": 1}]}, headers=headers_user)
    assert resp.status_code == 201
    oid = resp.json().get("order")["id"]

    # admin transitions order to 'paid'
    admin_token = token_for("admin", "adminpass")
    headers_admin = auth_header(admin_token)
    resp = client.post(f"/api/orders/{oid}/transition", json={"status": "paid"}, headers=headers_admin)
    assert resp.status_code == 200, resp.text
    assert resp.json()["order"]["status"] == "paid"


def test_optimistic_lock_conflict_returns_409(client, seeded_admin, temp_user, token_for, auth_header):
    prod = file_db.create_record("products", {"title": "Sofa", "price": 800.0, "stock": 1}, id_field="id")
    pid = prod["id"]

    user_token = token_for(temp_user["username"], temp_user["password"])
    headers_user = auth_header(user_token)
    resp = client.post("/api/orders/", json={"items": [{"product_id": pid, "unit_price": 800.0, "quantity": 1}]}, headers=headers_user)
    assert resp.status_code == 201
    oid = resp.json().get("order")["id"]

    # attempt with bad expected_version -> 409
    resp = client.post(f"/api/orders/{oid}/transition", json={"status": "paid", "expected_version": 999}, headers=headers_user)
    assert resp.status_code == 409


def test_non_owner_non_admin_cannot_transition(client, seeded_admin, temp_user, token_for, auth_header):
    # create a second user via register so we can request token
    other_username = f"user_{uuid.uuid4().hex[:6]}"
    other_password = "otherpass"
    resp = client.post("/api/auth/register", json={"username": other_username, "email": f"{other_username}@example.com", "password": other_password})
    assert resp.status_code in (200, 201), resp.text

    prod = file_db.create_record("products", {"title": "Shelf", "price": 60.0, "stock": 3}, id_field="id")
    pid = prod["id"]

    # temp_user creates order
    user_token = token_for(temp_user["username"], temp_user["password"])
    headers_user = auth_header(user_token)
    resp = client.post("/api/orders/", json={"items": [{"product_id": pid, "unit_price": 60.0, "quantity": 1}]}, headers=headers_user)
    assert resp.status_code == 201
    oid = resp.json().get("order")["id"]

    # other (not owner, not admin) tries to transition
    other_token = token_for(other_username, other_password)
    headers_other = auth_header(other_token)
    resp = client.post(f"/api/orders/{oid}/transition", json={"status": "paid"}, headers=headers_other)
    assert resp.status_code == 403