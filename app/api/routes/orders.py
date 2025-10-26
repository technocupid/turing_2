# app/api/routes/orders.py
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Body
from datetime import datetime
import json

from app.api.deps import get_db, get_current_active_user, require_admin
from app.database import FileBackedDB
from app.models.order import Order, OrderItem
from app.models.cart import Cart, CartItem
from app.services.payment import process_payment, PaymentError

router = APIRouter(prefix="/api/orders", tags=["orders"])

db: FileBackedDB = get_db()


def _compute_total_from_items(items: List[Dict[str, Any]]) -> float:
    total = 0.0
    for it in items:
        try:
            qty = int(float(it.get("quantity", it.get("qty", 1))))
        except Exception:
            qty = 1
        try:
            price = float(it.get("unit_price", it.get("price", 0.0)))
        except Exception:
            price = 0.0
        total += price * qty
    return float(total)


@router.post("/", status_code=201)
def create_order(
    payload: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    """
    Create an order.

    Payload options:
      - { "cart_id": "<id>" }  -> uses cart saved in DB under carts table
      - { "items": [ {product_id, unit_price, quantity, title?}, ... ], "shipping_address": "..." }
      - you may also pass both; cart_id takes precedence

    Returns the created order record.
    """
    # resolve items
    items_payload = []
    if payload.get("cart_id"):
        cart_row = db.get_record("carts", "id", payload["cart_id"])
        if not cart_row:
            raise HTTPException(status_code=404, detail="Cart not found")
        # cart_row['items'] expected to be JSON string
        raw = cart_row.get("items") or "[]"
        try:
            items_payload = json.loads(raw)
        except Exception:
            items_payload = []
    elif payload.get("items"):
        items_payload = payload.get("items", [])
    else:
        raise HTTPException(status_code=400, detail="No items provided (cart_id or items required)")

    if not isinstance(items_payload, list) or len(items_payload) == 0:
        raise HTTPException(status_code=400, detail="Cart/items empty")

    # compute total
    total_amount = _compute_total_from_items(items_payload)

    # create Order model
    order = Order(
        id=None,
        user_id=current_user.get("username"),
        items=[OrderItem.from_dict(it) if isinstance(it, dict) else it for it in items_payload],
        total_amount=total_amount,
        status="placed",
        shipping_address=payload.get("shipping_address") or payload.get("address") or "",
        created_at=datetime.utcnow(),
    )

    # persist
    saved = db.create_record("orders", order.to_dict(), id_field="id")
    return {"ok": True, "order": saved}


@router.get("/", response_model=List[Dict[str, Any]])
def list_orders(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """
    List orders for the current user. Admins see all orders.
    """
    all_orders = db.list_records("orders")
    is_admin = current_user.get("is_admin", False)
    # normalize
    if isinstance(is_admin, str):
        is_admin = is_admin.strip().lower() in ("1", "true", "yes", "y", "t")
    if is_admin:
        return all_orders
    # filter by username/user_id
    username = current_user.get("username")
    out = [o for o in all_orders if str(o.get("user_id") or o.get("username") or "") == str(username)]
    return out


@router.get("/{order_id}")
def get_order(order_id: str, current_user: Dict[str, Any] = Depends(get_current_active_user)):
    row = db.get_record("orders", "id", order_id) or db.get_record("orders", "order_id", order_id)
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    # allow access if owner or admin
    username = current_user.get("username")
    is_admin = current_user.get("is_admin", False)
    if isinstance(is_admin, str):
        is_admin = is_admin.strip().lower() in ("1", "true", "yes", "y", "t")
    owner = str(row.get("user_id") or row.get("username") or "")
    if not is_admin and owner != str(username):
        raise HTTPException(status_code=403, detail="Not authorized to view this order")
    return row


@router.post("/{order_id}/pay")
def pay_order(
    order_id: str,
    payment: Dict[str, Any] = Body(...),  # e.g. {"type":"card","card_last4":"4242"}
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    """
    Charge for an order. This calls `process_payment` and updates order status to 'paid' on success.
    """
    # fetch order
    row = db.get_record("orders", "id", order_id)
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    # check ownership / admin
    username = current_user.get("username")
    is_admin = current_user.get("is_admin", False)
    if isinstance(is_admin, str):
        is_admin = is_admin.strip().lower() in ("1", "true", "yes", "y", "t")
    owner = str(row.get("user_id") or row.get("username") or "")
    if not is_admin and owner != str(username):
        raise HTTPException(status_code=403, detail="Not authorized to pay this order")

    # compute amount (trust record)
    try:
        amount = float(row.get("total_amount") or row.get("total") or 0.0)
    except Exception:
        amount = 0.0
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Order has no amount to charge")

    # call payment service
    try:
        result = process_payment(amount, payment)
    except PaymentError as e:
        raise HTTPException(status_code=502, detail=f"Payment gateway error: {e}")

    if not result.get("success"):
        # record transaction info but do not mark paid
        updates = {
            "last_payment_tx": result.get("transaction_id"),
            "last_payment_msg": result.get("message") or "failure",
            "last_payment_success": False,
            "status": "payment_failed",
        }
        db.update_record("orders", "id", order_id, updates)
        raise HTTPException(status_code=402, detail="Payment failed: " + (result.get("message") or "unknown"))

    # success -> mark paid
    updates = {
        "last_payment_tx": result.get("transaction_id"),
        "last_payment_msg": result.get("message") or "ok",
        "last_payment_success": True,
        "status": "paid",
        "paid_at": datetime.utcnow().isoformat(sep=" "),
    }
    db.update_record("orders", "id", order_id, updates)
    return {"ok": True, "transaction": result}


@router.put("/{order_id}/status", dependencies=[Depends(require_admin)])
def set_order_status(order_id: str, payload: Dict[str, Any] = Body(...)):
    """
    Admin-only: change order.status. Payload: { "status": "shipped" }
    """
    new_status = payload.get("status")
    if not new_status:
        raise HTTPException(status_code=400, detail="status required")
    updated = db.update_record("orders", "id", order_id, {"status": new_status})
    if not updated:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"ok": True, "order": updated}
