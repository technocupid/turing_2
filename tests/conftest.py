# tests/conftest.py
import os
import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from passlib.context import CryptContext

# ensure project root is importable
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# create a dedicated temp data dir at import time so all imports (app/database/app.main)
# pick up the test DATA_DIR before they are imported by tests
_tmp_data_dir = tempfile.mkdtemp(prefix="test_data_")
from app import config as app_config  # keep after tmpdir creation
_orig_settings_data_dir = app_config.settings.DATA_DIR
app_config.settings.DATA_DIR = Path(_tmp_data_dir)

# import database module after overriding settings so it initializes against tmp dir
from app import database as app_database
# ensure module-level DATA_DIR aligns
app_database.DATA_DIR = Path(_tmp_data_dir)
app_database.DATA_DIR.mkdir(parents=True, exist_ok=True)

# now import the FastAPI app
from app.main import app  # noqa: E402

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


@pytest.fixture(autouse=True)
def temp_data_dir():
    """
    Ensures tests run against an isolated temp data directory.
    Restores original settings and removes temp dir after test session.
    """
    try:
        yield Path(_tmp_data_dir)
    finally:
        # restore original setting
        app_config.settings.DATA_DIR = _orig_settings_data_dir
        # cleanup tmp dir
        try:
            shutil.rmtree(_tmp_data_dir)
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
    row = app_database.db.create_record(
        "users",
        {"username": username, "email": email, "password_hash": hashed, "is_admin": True},
        id_field="id",
    )
    return row


@pytest.fixture
def seeded_admin():
    return create_admin_in_db()


@pytest.fixture
def temp_user():
    """
    Create a temporary non-admin user and yield its details.
    Returns {"row": <user_row>, "password": <plain_password>, "username": ..., "email": ...}
    """
    password = "testpass"
    hashed = pwd_ctx.hash(password)
    user = app_database.db.create_record(
        "users",
        {"username": f"user_{os.urandom(4).hex()}", "email": f"user_{os.urandom(4).hex()}@example.test", "password_hash": hashed, "is_admin": False},
        id_field="id",
    )
    yield {"row": user, "password": password, "username": user.get("username"), "email": user.get("email")}