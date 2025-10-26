# app/models/cart.py
from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class CartItem:
    product_id: str
    title: Optional[str] = None
    unit_price: float = 0.0
    quantity: int = 1
    added_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CartItem":
        if d is None:
            raise ValueError("Cannot construct CartItem from None")
        product_id = str(d.get("product_id") or d.get("id") or "")
        title = d.get("title") or d.get("name") or None
        try:
            unit_price = float(d.get("unit_price") or d.get("price") or 0.0)
        except Exception:
            unit_price = 0.0
        try:
            quantity = int(float(d.get("quantity") or d.get("qty") or 1))
        except Exception:
            quantity = 1

        added_at = d.get("added_at")
        # don't attempt heavy parsing here; leave consumers to interpret strings if present
        return cls(product_id=product_id, title=title, unit_price=unit_price, quantity=quantity, added_at=added_at)

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        # normalize primitives
        out["unit_price"] = float(self.unit_price)
        out["quantity"] = int(self.quantity)
        return out

    def line_total(self) -> float:
        return float(self.unit_price) * int(self.quantity)


@dataclass
class Cart:
    """
    Simple cart model. This can be saved to CSV/Excel as a single row with 'items' serialized
    as JSON (list of CartItem dicts). The 'id' field can be used for session id or cart id.
    """
    id: Optional[str] = None
    user_id: Optional[str] = None  # optional link to user
    items: List[CartItem] = field(default_factory=list)
    updated_at: Optional[str] = None  # store as string when serializing (ISO) or leave blank

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Cart":
        if d is None:
            raise ValueError("Cannot construct Cart from None")
        id_val = d.get("id") or d.get("cart_id") or None
        user_id = d.get("user_id") or d.get("username") or None
        raw_items = d.get("items") or []
        items_list = []
        if isinstance(raw_items, str):
            # attempt to parse JSON string
            import json
            try:
                parsed = json.loads(raw_items)
                if isinstance(parsed, list):
                    raw_items = parsed
                else:
                    raw_items = []
            except Exception:
                raw_items = []
        for it in raw_items:
            if isinstance(it, CartItem):
                items_list.append(it)
            elif isinstance(it, dict):
                items_list.append(CartItem.from_dict(it))
        updated_at = d.get("updated_at") or d.get("updated")
        return cls(id=id_val, user_id=user_id, items=items_list, updated_at=updated_at)

    def to_dict(self) -> Dict[str, Any]:
        import json
        out = {
            "id": self.id or "",
            "user_id": self.user_id or "",
            "items": json.dumps([it.to_dict() for it in self.items], ensure_ascii=False),
            "updated_at": self.updated_at or ""
        }
        return out

    # business helpers
    def add_item(self, product_id: str, title: str, unit_price: float, quantity: int = 1) -> None:
        # if product exists in cart, increment quantity
        for it in self.items:
            if it.product_id == product_id:
                it.quantity = int(it.quantity) + int(quantity)
                return
        self.items.append(CartItem(product_id=product_id, title=title, unit_price=float(unit_price), quantity=int(quantity)))

    def remove_item(self, product_id: str, quantity: Optional[int] = None) -> bool:
        """
        Remove a quantity of item from cart. If quantity is None, remove the item entirely.
        Returns True if an item was changed/removed.
        """
        for idx, it in enumerate(self.items):
            if it.product_id == product_id:
                if quantity is None or int(quantity) >= it.quantity:
                    # remove item
                    self.items.pop(idx)
                else:
                    it.quantity = int(it.quantity) - int(quantity)
                return True
        return False

    def clear(self) -> None:
        self.items = []

    def total(self) -> float:
        return float(sum(it.line_total() for it in self.items))

    def count_items(self) -> int:
        return int(sum(it.quantity for it in self.items))
