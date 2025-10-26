# tests/test_products.py
import pytest

def test_admin_create_and_get_product(client, seeded_admin):
    # obtain admin token
    resp = client.post("/api/auth/token", data={"username": "admin", "password": "adminpass"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # create product
    payload = {
        "title": "Test Wooden Bowl",
        "description": "Handmade wooden bowl",
        "category": "kitchen",
        "price": 999.0,
        "stock": 10,
        "image_filename": None,
    }
    resp = client.post("/api/products/", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    product = resp.json()
    assert product["title"] == payload["title"]
    pid = product.get("id")
    assert pid

    # fetch product
    resp = client.get(f"/api/products/{pid}")
    assert resp.status_code == 200, resp.text
    fetched = resp.json()
    assert fetched["id"] == pid
    assert fetched["price"] == pytest.approx(999.0)
