# tests/conftest.py
import os
import sys
import shutil
import tempfile
from datetime import datetime
import uuid

import pytest
from fastapi.testclient import TestClient
from passlib.context import CryptContext

# ensure project root is importable when tests run in some CI environments
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.main import app  # now safe to import
from app.database import db as file_db

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


@pytest.fixture(autouse=True)
def temp_data_dir():
    """
    Create a temporary data directory and point the file-backed db to it.
    Cleans up after the test.
    """
    td = tempfile.mkdtemp(prefix="test_data_")
    original_dir = file_db.data_dir
    file_db.data_dir = td
    try:
        yield td
    finally:
        # restore and cleanup
        file_db.data_dir = original_dir
        try:
            shutil.rmtree(td)
        except Exception:
            pass


@pytest.fixture
def client():
    return TestClient(app)


def create_admin_in_db(username="admin", password="adminpass", email="admin@example.com"):
    """
    Utility to create an admin user in the file-backed DB.
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


@pytest.fixture
def seeded_admin():
    return create_admin_in_db()
@pytest.fixture
def temp_user():
    """
    Create a temporary non-admin user for a test and remove it after the test.
    Yields a dict: {"username","password","email"}
    """
    # unique username to avoid collisions
    username = f"tuser_{uuid.uuid4().hex[:8]}"
    password = "testpass123"  # or generate random if desired
    email = f"{username}@example.test"

    hashed = pwd_ctx.hash(password)
    row = {
        "username": username,
        "email": email,
        "hashed_password": hashed,
        "is_admin": False,
        "full_name": "Temp Test User",
        "created_at": datetime.utcnow().isoformat(sep=" "),
    }
    created = file_db.create_record("users", row, id_field="id")

    try:
        yield {"username": username, "password": password, "email": email, "row": created}
    finally:
        # teardown: delete user by username
        try:
            file_db.delete_record("users", "username", username)
        except Exception:
            pass