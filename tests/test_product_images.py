# tests/test_product_images.py
import os
import io
import json
from pathlib import Path
from datetime import datetime

import pytest
from PIL import Image
from passlib.context import CryptContext

# ensure project root is importable (conftest may already do this)
from app.database import db as file_db
from app.config import settings
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def make_sample_jpeg_bytes(size=(200, 200), color=(180, 120, 60)):
    """Create an in-memory JPEG image and return bytes."""
    bio = io.BytesIO()
    im = Image.new("RGB", size, color)
    im.save(bio, format="JPEG", quality=85)
    bio.seek(0)
    return bio.read()


@pytest.fixture
def isolated_image_dir(tmp_path, monkeypatch):
    """
    Create images directory under a temp path and point settings.image_dir to it.
    Returns the base image_dir path string.
    """
    image_dir = tmp_path / "static_images"
    image_dir = str(image_dir)  # convert to plain str for settings
    # monkeypatch the settings used by the app
    monkeypatch.setattr(settings, "image_dir", image_dir, raising=False)
    return image_dir


def create_admin_in_db(username="admin", password="adminpass", email="admin@example.com"):
    """
    Create an admin user directly in the file-backed DB using hashed password.
    Returns the created row dict.
    """
    hashed = pwd_ctx.hash(password)
    row = {
        "username": username,
        "email": email,
        "hashed_password": hashed,
        "is_admin": True,
        "full_name": "Admin",
        "created_at": datetime.utcnow().isoformat(sep=" "),
    }
    created = file_db.create_record("users", row, id_field="id")
    return created


def get_auth_header_for(username="admin", password="adminpass"):
    resp = client.post("/api/auth/token", data={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_product_as_admin(admin_header, title="ImgTest", price=100.0):
    payload = {
        "title": title,
        "description": "Image test product",
        "category": "decor",
        "price": price,
        "stock": 5,
    }
    resp = client.post("/api/products/", json=payload, headers=admin_header)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_image_upload_list_delete_flow(tmp_path, isolated_image_dir):
    """
    Full flow:
      - create admin user in test DB
      - create product as admin
      - upload an image (multipart)
      - verify file exists on disk
      - call list images endpoint -> URL list
      - delete the image with admin -> verify removed from disk and product record
      - non-admin cannot upload
    """
    # create admin user explicitly in temp DB
    admin_row = create_admin_in_db(username="admin", password="adminpass", email="admin@example.com")
    assert admin_row["username"] == "admin"

    # admin header
    admin_header = get_auth_header_for(username="admin", password="adminpass")

    # create product
    product = create_product_as_admin(admin_header)
    product_id = product.get("id")
    assert product_id

    # expected product images directory
    base_image_dir = isolated_image_dir
    expected_product_dir = Path(base_image_dir) / "products" / str(product_id)
    # ensure parent exists
    expected_product_dir.parent.mkdir(parents=True, exist_ok=True)

    # generate image bytes
    jpg_bytes = make_sample_jpeg_bytes()
    files = {"file": ("test.jpg", io.BytesIO(jpg_bytes), "image/jpeg")}

    # upload as admin
    up_url = f"/api/products/{product_id}/upload-image"
    resp = client.post(up_url, files=files, headers=admin_header)
    assert resp.status_code == 200, resp.text
    j = resp.json()
    assert j.get("ok") is True
    filenames = j.get("filenames") or []
    assert len(filenames) >= 1
    original_fname = filenames[0]

    # check file exists on disk
    path = expected_product_dir / original_fname
    assert path.exists(), f"Expected file saved at {path}"

    # list images via endpoint
    list_url = f"/api/products/{product_id}/images"
    resp = client.get(list_url)
    assert resp.status_code == 200, resp.text
    urls = resp.json()
    assert isinstance(urls, list)
    assert any(original_fname in u for u in urls)

    # delete image as admin
    del_url = f"/api/products/{product_id}/images/{original_fname}"
    resp = client.delete(del_url, headers=admin_header)
    assert resp.status_code == 200, resp.text
    j = resp.json()
    assert j.get("ok") is True
    remaining = j.get("remaining", [])
    assert original_fname not in remaining

    # verify file removed from disk (and any variants)
    assert not (expected_product_dir / original_fname).exists()

    # non-admin cannot upload: create temp non-admin user
    uname = "tempu"
    upwd = "temppw"
    resp = client.post("/api/auth/register", json={"username": uname, "email": f"{uname}@xy.com", "password": upwd})
    assert resp.status_code == 200, resp.text

    # get token
    resp = client.post("/api/auth/token", data={"username": uname, "password": upwd})
    assert resp.status_code == 200, resp.text
    user_token = resp.json()["access_token"]
    user_header = {"Authorization": f"Bearer {user_token}"}

    # try uploading as non-admin
    resp = client.post(up_url, files=files, headers=user_header)
    # should be forbidden (403) or unauthorized (401)
    assert resp.status_code in (401, 403)
