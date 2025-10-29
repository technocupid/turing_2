# app/models/order.py
from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

from app.core.state_machine import StateMachine


@dataclass
class OrderItem:
    product_id: str
    title: Optional[str] = None
    unit_price: float = 0.0
    quantity: int = 1

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "OrderItem":
        return cls(
            product_id=str(d.get("product_id") or d.get("id") or d.get("sku") or ""),
            title=d.get("title") or d.get("name") or None,
            unit_price=float(d.get("unit_price") or d.get("price") or 0.0),
            quantity=int(float(d.get("quantity") or 1))
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "title": self.title or "",
            "unit_price": float(self.unit_price),
            "quantity": int(self.quantity)
        }


@dataclass
class Order:
    """
    Order domain model. The `items` field is a list of OrderItem objects.
    """
    id: Optional[str] = None
    user_id: Optional[str] = None
    items: List[OrderItem] = field(default_factory=list)
    total_amount: float = 0.0
    status: str = "placed"  # placed, paid, shipped, delivered, cancelled, refunded, returned
    shipping_address: Optional[str] = None
    created_at: Optional[datetime] = None
    status_history: List[Dict[str, Any]] = field(default_factory=list)
    # optimistic concurrency control
    version: int = 0

    # allowed transitions map
    ALLOWED_TRANSITIONS = {
        "placed": ["paid", "cancelled"],
        "paid": ["shipped", "cancelled", "refunded"],
        "shipped": ["delivered", "returned"],
        "delivered": [],
        "cancelled": [],
        "refunded": [],
        "returned": [],
    }

    def _make_state_machine(self) -> StateMachine:
        return StateMachine(state=self.status, allowed_transitions=self.ALLOWED_TRANSITIONS,
                            version=self.version, history=list(self.status_history))

    def transition_to(self, new_status: str, actor: Optional[str] = None, meta: Optional[Dict[str, Any]] = None,
                      expected_version: Optional[int] = None) -> None:
        """
        Transition to a new status using the StateMachine. Raises InvalidTransition or OptimisticLockError.
        On success updates self.status, self.status_history and increments self.version.
        """
        sm = self._make_state_machine()
        result = sm.apply(new_status, actor=actor, meta=meta, expected_version=expected_version)
        # update model from state machine result
        self.status = result["state"]
        self.status_history = result["history"]
        self.version = int(result["version"])

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Order":
        if d is None:
            raise ValueError("Cannot construct Order from None")
        id_val = d.get("id") or d.get("order_id") or None
        user_id = d.get("user_id") or d.get("username") or None
        # items might be stored as a serialized JSON string, or as a Python list-of-dicts
        raw_items = d.get("items") or d.get("order_items") or []
        items_list = []
        if isinstance(raw_items, str):
            # attempt to parse JSON
            try:
                parsed = json.loads(raw_items)
                if isinstance(parsed, list):
                    raw_items = parsed
                else:
                    raw_items = []
            except Exception:
                raw_items = []
        # now convert each
        for it in raw_items:
            if isinstance(it, OrderItem):
                items_list.append(it)
            elif isinstance(it, dict):
                items_list.append(OrderItem.from_dict(it))
            else:
                # unknown format: ignore or attempt string parse - skip here
                continue

        total_raw = d.get("total_amount") or d.get("total") or 0.0
        try:
            total_amount = float(total_raw)
        except Exception:
            total_amount = 0.0

        status = d.get("status") or "placed"
        shipping_address = d.get("shipping_address") or d.get("address") or None

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

        status_history_raw = d.get("status_history") or "[]"
        if isinstance(status_history_raw, str):
            try:
                status_history = json.loads(status_history_raw) or []
            except Exception:
                status_history = []
        else:
            status_history = status_history_raw or []

        version = int(d.get("version") or d.get("ver") or 0)

        return cls(
            id=id_val,
            user_id=user_id,
            items=items_list,
            total_amount=total_amount,
            status=status,
            shipping_address=shipping_address,
            created_at=created_at,
            status_history=status_history,
            version=version
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the order into dict suitable for CSV writing. `items` and history are serialized as JSON strings.
        """
        out = asdict(self)
        # items -> list of dicts
        out["items"] = [it.to_dict() for it in self.items]
        # serialize items into JSON string for flattening into CSV cell
        out["items"] = json.dumps(out["items"], ensure_ascii=False)
        # serialize status_history as JSON string
        out["status_history"] = json.dumps(self.status_history or [], ensure_ascii=False)
        out["total_amount"] = float(self.total_amount)
        out["version"] = int(self.version or 0)
        if self.created_at and isinstance(self.created_at, datetime):
            out["created_at"] = self.created_at.isoformat(sep=" ")
        else:
            out["created_at"] = ""
        return out
