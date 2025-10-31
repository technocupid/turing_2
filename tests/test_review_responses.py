# ...new file...
import uuid

from app.database import db as file_db

def test_admin_can_create_response(temp_user, seeded_admin, client, auth_header):
    # temp_user creates a review; admin posts a response
    user = temp_user["row"]
    user_id = user["id"]
    admin = seeded_admin
    admin_id = admin["id"]

    product = file_db.create_record(
        "products",
        {"name": "Responseable Product", "sku": f"sku-{uuid.uuid4().hex[:6]}", "price": "30.00"},
        id_field="id",
    )
    product_id = product["id"]

    # create a review by normal user
    r = client.post(f"/api/products/{product_id}/reviews", json={"rating": 4, "body": "Nice"}, headers=auth_header(user_id))
    assert r.status_code == 201
    review = r.json()
    review_id = review["id"]

    # admin creates response
    resp = client.post(f"/api/products/{product_id}/reviews/{review_id}/response", json={"body": "Thanks for the feedback!"}, headers=auth_header(admin_id))
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created.get("response_body") == "Thanks for the feedback!"
    assert created.get("response_author_id") == admin_id
    assert "response_created_at" in created


def test_non_admin_cannot_create_response(temp_user, client, auth_header):
    user = temp_user["row"]
    user_id = user["id"]

    product = file_db.create_record(
        "products",
        {"name": "NoResp Product", "sku": f"sku-{uuid.uuid4().hex[:6]}", "price": "12.00"},
        id_field="id",
    )
    product_id = product["id"]

    r = client.post(f"/api/products/{product_id}/reviews", json={"rating": 3}, headers=auth_header(user_id))
    assert r.status_code == 201
    review_id = r.json()["id"]

    # same normal user attempts to create response -> forbidden
    resp = client.post(f"/api/products/{product_id}/reviews/{review_id}/response", json={"body": "Owner reply"}, headers=auth_header(user_id))
    assert resp.status_code == 403


def test_cannot_create_duplicate_response(temp_user, seeded_admin, client, auth_header):
    user = temp_user["row"]
    user_id = user["id"]
    admin = seeded_admin
    admin_id = admin["id"]

    product = file_db.create_record(
        "products",
        {"name": "DupResp Product", "sku": f"sku-{uuid.uuid4().hex[:6]}", "price": "18.00"},
        id_field="id",
    )
    product_id = product["id"]

    r = client.post(f"/api/products/{product_id}/reviews", json={"rating": 5}, headers=auth_header(user_id))
    assert r.status_code == 201
    review_id = r.json()["id"]

    # create first response
    resp1 = client.post(f"/api/products/{product_id}/reviews/{review_id}/response", json={"body": "First"}, headers=auth_header(admin_id))
    assert resp1.status_code == 201

    # attempt second -> 400
    resp2 = client.post(f"/api/products/{product_id}/reviews/{review_id}/response", json={"body": "Second"}, headers=auth_header(admin_id))
    assert resp2.status_code == 400


def test_admin_can_edit_response(temp_user, seeded_admin, client, auth_header):
    user = temp_user["row"]
    user_id = user["id"]
    admin = seeded_admin
    admin_id = admin["id"]

    product = file_db.create_record(
        "products",
        {"name": "EditResp Product", "sku": f"sku-{uuid.uuid4().hex[:6]}", "price": "22.00"},
        id_field="id",
    )
    product_id = product["id"]

    r = client.post(f"/api/products/{product_id}/reviews", json={"rating": 4}, headers=auth_header(user_id))
    review_id = r.json()["id"]

    client.post(f"/api/products/{product_id}/reviews/{review_id}/response", json={"body": "Original reply"}, headers=auth_header(admin_id))

    # edit
    resp = client.put(f"/api/products/{product_id}/reviews/{review_id}/response", json={"body": "Updated reply"}, headers=auth_header(admin_id))
    assert resp.status_code == 200, resp.text
    updated = resp.json()
    assert updated.get("response_body") == "Updated reply"
    assert "response_updated_at" in updated


def test_edit_nonexistent_response_returns_404(temp_user, seeded_admin, client, auth_header):
    user = temp_user["row"]
    user_id = user["id"]
    admin = seeded_admin
    admin_id = admin["id"]

    product = file_db.create_record(
        "products",
        {"name": "NoEditResp Product", "sku": f"sku-{uuid.uuid4().hex[:6]}", "price": "8.00"},
        id_field="id",
    )
    product_id = product["id"]

    r = client.post(f"/api/products/{product_id}/reviews", json={"rating": 2}, headers=auth_header(user_id))
    review_id = r.json()["id"]

    # attempt to edit when no response exists
    resp = client.put(f"/api/products/{product_id}/reviews/{review_id}/response", json={"body": "Try edit"}, headers=auth_header(admin_id))
    assert resp.status_code == 404


def test_admin_can_delete_response(temp_user, seeded_admin, client, auth_header):
    user = temp_user["row"]
    user_id = user["id"]
    admin = seeded_admin
    admin_id = admin["id"]

    product = file_db.create_record(
        "products",
        {"name": "DelResp Product", "sku": f"sku-{uuid.uuid4().hex[:6]}", "price": "11.00"},
        id_field="id",
    )
    product_id = product["id"]

    r = client.post(f"/api/products/{product_id}/reviews", json={"rating": 5}, headers=auth_header(user_id))
    review_id = r.json()["id"]

    client.post(f"/api/products/{product_id}/reviews/{review_id}/response", json={"body": "To be deleted"}, headers=auth_header(admin_id))

    resp = client.delete(f"/api/products/{product_id}/reviews/{review_id}/response", headers=auth_header(admin_id))
    assert resp.status_code == 204

    # ensure response gone on review record
    rev = file_db.get_record("reviews", "id", review_id)
    assert rev is not None
    assert not rev.get("response_body")