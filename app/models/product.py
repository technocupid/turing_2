# app/models/product.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class Product:
    """
    Simple product model. CSV-backed store will usually store everything as strings,
    so these helpers convert to proper types.
    """
    id: Optional[str] = None
    title: str = ""
    description: Optional[str] = ""
    category: Optional[str] = "general"
    price: float = 0.0
    stock: int = 0
    image_filename: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Product":
        if d is None:
            raise ValueError("Cannot construct Product from None")
        # normalize
        id_val = d.get("id") or d.get("product_id") or None
        title = d.get("title") or ""
        description = d.get("description") or ""
        category = d.get("category") or "general"
        price_raw = d.get("price", 0)
        stock_raw = d.get("stock", 0)
        image_filename = d.get("image_filename") or d.get("image") or None
        created_by = d.get("created_by") or None

        # cast numeric fields safely
        try:
            price = float(price_raw) if price_raw not in (None, "") else 0.0
        except Exception:
            price = 0.0

        try:
            stock = int(float(stock_raw)) if stock_raw not in (None, "") else 0
        except Exception:
            stock = 0

        created_at_raw = d.get("created_at") or d.get("created")
        created_at = None
        if created_at_raw:
            if isinstance(created_at_raw, datetime):
                created_at = created_at_raw
            else:
                try:
                    created_at = datetime.fromisoformat(str(created_at_raw))
                except Exception:
                    try:
                        created_at = datetime.strptime(str(created_at_raw), "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        created_at = None

        return cls(
            id=id_val,
            title=str(title),
            description=str(description),
            category=str(category),
            price=price,
            stock=stock,
            image_filename=image_filename,
            created_by=created_by,
            created_at=created_at
        )

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        if self.created_at and isinstance(self.created_at, datetime):
            out["created_at"] = self.created_at.isoformat(sep=" ")
        else:
            out["created_at"] = ""
        # price/stock ensure serializable primitives
        out["price"] = float(self.price) if self.price is not None else 0.0
        out["stock"] = int(self.stock) if self.stock is not None else 0
        return out
