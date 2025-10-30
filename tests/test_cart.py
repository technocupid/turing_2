import json
from app.models.cart import Cart

def test_create_and_get_cart(client):
    payload = {
        "user_id": "test_user_1",
        "items": [
            {"product_id": "p1", "title": "Item One", "unit_price": 10.5, "quantity": 2}
        ],
        "updated_at": ""
    }
    # create
    r = client.post("/api/cart", json=payload)
    assert r.status_code == 200
    created = r.json()
    assert "id" in created
    cart_id = created["id"]

    # ensure stored user_id matches (Cart.to_dict uses empty string when missing)
    assert created.get("user_id", "") == payload["user_id"]

    # get
    g = client.get(f"/api/cart/{cart_id}")
    assert g.status_code == 200
    got = g.json()
    assert got["id"] == cart_id

    # items are stored as JSON string per Cart.to_dict
    items_raw = got.get("items", "[]")
    items = json.loads(items_raw) if isinstance(items_raw, str) else items_raw
    assert isinstance(items, list)
    assert len(items) == 1
    assert items[0]["product_id"] == "p1"
    assert float(items[0]["unit_price"]) == 10.5
    assert int(items[0]["quantity"]) == 2

def test_add_item_to_existing_cart(client):
    payload = {
        "user_id": "user_add_test",
        "items": [
            {"product_id": "pA", "title": "A", "unit_price": 1.0, "quantity": 1}
        ],
    }
    r = client.post("/api/cart", json=payload)
    assert r.status_code == 200
    created = r.json()
    cart_id = created["id"]

    # add another item
    item = {"product_id": "pB", "title": "B", "unit_price": 2.5, "quantity": 3}
    r2 = client.post(f"/api/cart/{cart_id}/items", json=item)
    assert r2.status_code == 200
    updated = r2.json()
    items_raw = updated.get("items", "[]")
    items = json.loads(items_raw) if isinstance(items_raw, str) else items_raw
    # expect two items now
    assert any(it.get("product_id") == "pA" for it in items)
    assert any(it.get("product_id") == "pB" for it in items)