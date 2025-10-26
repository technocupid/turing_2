# app/models/user.py
from __future__ import annotations
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class User:
    """
    Domain model for a user.
    The FileBackedDB stores values as strings; these helpers normalize/convert types.
    """
    username: str
    email: str
    hashed_password: str
    is_admin: bool = False
    full_name: Optional[str] = None
    created_at: Optional[datetime] = None
    id: Optional[str] = None  # optional unique id (uuid) if you use one

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "User":
        if d is None:
            raise ValueError("Cannot construct User from None")
        # defensive lookups: file-backed rows may have different keys
        username = d.get("username") or d.get("user") or ""
        email = d.get("email") or ""
        hashed_password = d.get("hashed_password") or d.get("password") or ""
        is_admin_raw = d.get("is_admin", d.get("admin", False))
        # is_admin might be stored as 'True'/'False' strings in CSV; normalize
        is_admin = False
        if isinstance(is_admin_raw, bool):
            is_admin = is_admin_raw
        elif isinstance(is_admin_raw, (int, float)):
            is_admin = bool(is_admin_raw)
        elif isinstance(is_admin_raw, str):
            is_admin = is_admin_raw.strip().lower() in ("1", "true", "yes", "y", "t")
        full_name = d.get("full_name") or d.get("name") or None

        created_at_raw = d.get("created_at") or d.get("created")
        created_at = None
        if created_at_raw:
            if isinstance(created_at_raw, datetime):
                created_at = created_at_raw
            else:
                # try a few common formats
                try:
                    created_at = datetime.fromisoformat(str(created_at_raw))
                except Exception:
                    try:
                        # pandas Timestamp prints like '2023-01-01 00:00:00'
                        created_at = datetime.strptime(str(created_at_raw), "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        # last resort: leave None
                        created_at = None

        id_val = d.get("id") or d.get("user_id") or None

        return cls(
            username=str(username),
            email=str(email),
            hashed_password=str(hashed_password),
            is_admin=is_admin,
            full_name=full_name if full_name else None,
            created_at=created_at,
            id=id_val
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to plain dict suitable for writing back to CSV/Excel.
        Note: hashed_password is included (necessary for persistence) — strip in APIs.
        """
        out = asdict(self)
        # created_at -> ISO string if present
        if self.created_at and isinstance(self.created_at, datetime):
            out["created_at"] = self.created_at.isoformat(sep=" ")
        else:
            out["created_at"] = ""
        # Ensure boolean is serialized as 'True'/'False' (or keep python bool which pandas will cast)
        out["is_admin"] = bool(self.is_admin)
        return out

    def mask_secret(self) -> Dict[str, Any]:
        """
        Return a representation safe to expose on API responses (no hashed_password).
        """
        d = self.to_dict()
        d.pop("hashed_password", None)
        return d
