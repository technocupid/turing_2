# app/database.py
"""
Simple file-backed DB layer using CSV (preferred) or Excel (xlsx) as storage.
Provides basic CRUD primitives per table name. Uses file locking to avoid
simultaneous writes corrupting files.

Usage:
    from app.database import db
    db.list_records("users")
    db.get_record("products", "sku", "ABC123")
    db.create_record("users", {"username": "bob", "email": "b@x.com"})
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
import uuid
from filelock import FileLock
from app.config import settings

DATA_DIR = Path(settings.DATA_DIR)
if not DATA_DIR.exists():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


class FileBackedDB:
    """
    Manages CSV / Excel files inside DATA_DIR.
    Table name corresponds to a file name in settings (or you may pass full filename).
    """

    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = Path(data_dir)

    def _file_path(self, table: str) -> Path:
        """
        Resolve table -> file path. If table looks like a filename (has .csv/.xlsx),
        use it directly (relative to data_dir). Otherwise try config mapping,
        else fallback to table + .csv
        """
        # allow passing explicit filenames
        if table.endswith(".csv") or table.endswith(".xlsx"):
            p = self.data_dir / Path(table)
            return p

        # map well-known tables from settings
        mapping = {
            "users": settings.USERS_FILE,
            "products": settings.PRODUCTS_FILE,
            "orders": settings.ORDERS_FILE,
            "carts": settings.CARTS_FILE,
        }
        filename = mapping.get(table, f"{table}.csv")
        return Path(self.data_dir) / Path(filename)

    def _lock_for(self, path: Path) -> FileLock:
        return FileLock(str(path) + ".lock")

    def _read_df(self, table: str) -> pd.DataFrame:
        path = self._file_path(table)
        if not path.exists():
            # return empty df
            return pd.DataFrame()
        # CSV preferred
        if path.suffix.lower() == ".csv":
            return pd.read_csv(path, dtype=str).fillna("")
        if path.suffix.lower() in (".xls", ".xlsx"):
            return pd.read_excel(path, dtype=str).fillna("")
        # unknown extension: try csv then excel
        try:
            return pd.read_csv(path, dtype=str).fillna("")
        except Exception:
            return pd.read_excel(path, dtype=str).fillna("")
    def _write_df_nolock(self, path: Path, df: pd.DataFrame) -> None:
        """
        Write DataFrame to `path` WITHOUT acquiring file lock.
        Use this only when the caller already holds the lock.
        """
        path = self._file_path(str(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".csv" or path.suffix == "":
            df.to_csv(path, index=False)
        elif path.suffix.lower() in (".xls", ".xlsx"):
            df.to_excel(path, index=False)
        else:
            df.to_csv(path, index=False)
    def _write_df(self, table: str, df: pd.DataFrame) -> None:
        path = self._file_path(table)
        path.parent.mkdir(parents=True, exist_ok=True)
        lock = self._lock_for(path)
        with lock:
            # preserve index=False for nicer files
            # if path.suffix.lower() == ".csv" or path.suffix == "":
            #     df.to_csv(path, index=False)
            # elif path.suffix.lower() in (".xls", ".xlsx"):
            #     df.to_excel(path, index=False)
            # else:
            #     # try CSV by default
            #     df.to_csv(path, index=False)
            self._write_df_nolock(path, df)

    # --- high-level CRUD primitives ---

    def list_records(self, table: str) -> List[Dict[str, Any]]:
        df = self._read_df(table)
        if df.empty:
            return []
        # convert to Python types; keep strings as-is
        return df.where(pd.notnull(df), None).to_dict(orient="records")

    def get_record(self, table: str, key: str, value: Any) -> Optional[Dict[str, Any]]:
        df = self._read_df(table)
        if df.empty:
            return None
        # treat everything as string for comparison simplicity
        mask = df[key].astype(str) == str(value)
        if not mask.any():
            return None
        row = df[mask].iloc[0].to_dict()
        return {k: (None if pd.isna(v) else v) for k, v in row.items()}

    def create_record(self, table: str, data: Dict[str, Any], id_field: str = "id") -> Dict[str, Any]:
        """
        Create a new record. If id_field not present in `data`, one will be generated (uuid4 hex).
        Returns the saved record (with id).
        """
        df = self._read_df(table)
        if df.empty:
            df = pd.DataFrame(columns=list(data.keys()) + ([id_field] if id_field not in data else []))
        # ensure id exists
        if id_field not in data or not data.get(id_field):
            data[id_field] = uuid.uuid4().hex
        # normalize types to string where needed
        new_row = {k: ("" if v is None else v) for k, v in data.items()}
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True, sort=False)
        self._write_df(table, df)
        return data

    def update_record(self, table: str, key: str, value: Any, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update rows where df[key] == value with fields in updates. Returns the updated first row dict or None.
        """
        path = self._file_path(table)
        lock = self._lock_for(path)
        with lock:
            df = self._read_df(table)
            if df.empty:
                return None
            mask = df[key].astype(str) == str(value)
            if not mask.any():
                return None
            for k, v in updates.items():
                print(k,v)
                df.loc[mask, k] = v
            self._write_df_nolock(table, df)
            row = df[mask].iloc[0].to_dict()
            return {k: (None if pd.isna(v) else v) for k, v in row.items()}

    def delete_record(self, table: str, key: str, value: Any) -> bool:
        """
        Delete all records where df[key] == value. Returns True if any rows were removed.
        """
        path = self._file_path(table)
        lock = self._lock_for(path)
        with lock:
            df = self._read_df(table)
            if df.empty:
                return False
            orig_len = len(df)
            df = df[df[key].astype(str) != str(value)]
            if len(df) == orig_len:
                return False
            self._write_df_nolock(table, df)
            return True


# module-level singleton for convenience
db = FileBackedDB()
