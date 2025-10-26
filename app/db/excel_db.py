### FILE: app/db/excel_db.py
import pandas as pd
import uuid
from filelock import FileLock
from typing import List, Dict, Any
from app.core.config import settings

LOCK_PATH = settings.EXCEL_PATH + '.lock'

class ExcelDB:
    def __init__(self, path: str = settings.EXCEL_PATH):
        self.path = path
        self.lock = FileLock(LOCK_PATH)

    def _read(self) -> pd.DataFrame:
        with self.lock:
            try:
                df = pd.read_excel(self.path)
            except FileNotFoundError:
                df = pd.DataFrame()
        return df

    def _write(self, df: pd.DataFrame):
        with self.lock:
            df.to_excel(self.path, index=False)

    def list_items(self) -> List[Dict[str, Any]]:
        df = self._read()
        if df.empty:
            return []
        return df.fillna('').to_dict(orient='records')

    def get_item(self, item_id: str) -> Dict[str, Any] | None:
        df = self._read()
        if df.empty:
            return None
        rows = df[df['item_id'] == item_id]
        if rows.empty:
            return None
        return rows.iloc[0].to_dict()

    def create_item(self, data: Dict[str, Any]) -> Dict[str, Any]:
        df = self._read()
        if df.empty:
            df = pd.DataFrame()
        new_id = data.get('item_id') or str(uuid.uuid4())
        data['item_id'] = new_id
        df = pd.concat([df, pd.DataFrame([data])], ignore_index=True, sort=False)
        self._write(df)
        return data

    def update_item(self, item_id: str, updates: Dict[str, Any]) -> Dict[str, Any] | None:
        df = self._read()
        if df.empty:
            return None
        mask = df['item_id'] == item_id
        if not mask.any():
            return None
        for k, v in updates.items():
            df.loc[mask, k] = v
        self._write(df)
        return df[mask].iloc[0].to_dict()

    def delete_item(self, item_id: str) -> bool:
        df = self._read()
        if df.empty:
            return False
        new_df = df[df['item_id'] != item_id]
        if len(new_df) == len(df):
            return False
        self._write(new_df)
        return True

excel_db = ExcelDB()

