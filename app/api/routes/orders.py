# app/api/routes/orders.py
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Body
from datetime import datetime
import json

from app.api.deps import get_db, get_current_active_user, require_admin
from app.database import FileBackedDB
from app.models.order import Order, OrderItem
from app.core.state_machine import InvalidTransition, OptimisticLockError
from app.services.payment import PaymentError, process_payment, process_refund
from app.schemas.order import OrderCreate, OrderResponse, PaymentRequest, CancelRequest

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


@router.post("/", status_code=201, response_model=OrderResponse)
def create_order(
    payload: OrderCreate = Body(...),
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
    if payload.cart_id:
        cart = db.get_record("carts", "id", payload.cart_id)
        if not cart:
            raise HTTPException(status_code=404, detail="Cart not found")
        # cart.from_dict -> normalize items shape if necessary
        items_payload = cart.get("items") or []
    elif payload.items:
        # pydantic already validated item shapes
        items_payload = [it.dict() for it in payload.items]
    else:
        raise HTTPException(status_code=400, detail="Must pass cart_id or items")

    if not isinstance(items_payload, list) or len(items_payload) == 0:
        raise HTTPException(status_code=400, detail="Order must contain at least one item")

    # compute total
    total_amount = _compute_total_from_items(items_payload)

    # create Order model
    order = Order(
        id=None,
        user_id=current_user.get("username"),
        items=[OrderItem.from_dict(it) if isinstance(it, dict) else it for it in items_payload],
        total_amount=total_amount,
        status="placed",
        shipping_address=payload.shipping_address or "",
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
    payment: PaymentRequest = Body(...),  # validated payment payload
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
        result = process_payment(amount, payment.dict())
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


# --- cancellation + refund endpoint ---
@router.post("/{order_id}/cancel")
def cancel_order(
    order_id: str,
    payload: Optional[CancelRequest] = Body(None),  # typed cancel request
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    """
    Cancel an order. Owner or admin may cancel.
    - If order is paid, attempts to issue a refund via process_refund.
    - On successful refund (or if not paid), transitions order to 'cancelled' and persists.
    """
    row = db.get_record("orders", "id", order_id) or db.get_record("orders", "order_id", order_id)
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")

    # authorization: owner (by username) or admin
    username = current_user.get("username")
    is_admin = current_user.get("is_admin", False)
    if isinstance(is_admin, str):
        is_admin = is_admin.strip().lower() in ("1", "true", "yes", "y", "t")
    owner = str(row.get("user_id") or row.get("username") or "")
    if not is_admin and owner != str(username):
        raise HTTPException(status_code=403, detail="Not allowed to cancel this order")

    status_now = str(row.get("status") or "").lower()
    if status_now == "cancelled":
        raise HTTPException(status_code=400, detail="Order already cancelled")

    # If paid, attempt refund first
    try:
        amount = float(row.get("total_amount") or row.get("total") or 0.0)
    except Exception:
        amount = 0.0

    refund_result = None
    if status_now == "paid" and amount > 0:
        try:
            refund_result = process_refund(amount, {"transaction_id": row.get("last_payment_tx")})
        except PaymentError as e:
            raise HTTPException(status_code=502, detail=f"Refund gateway error: {e}")

        if not refund_result.get("success"):
            # persist failed refund attempt and surface error
            db.update_record(
                "orders",
                "id",
                order_id,
                {
                    "last_refund_tx": refund_result.get("transaction_id"),
                    "last_refund_msg": refund_result.get("message") or "failure",
                    "last_refund_success": False,
                    "status": "refund_failed",
                },
            )
            raise HTTPException(status_code=502, detail="Refund failed: " + (refund_result.get("message") or "unknown"))

    # Now perform state transition via Order domain if possible (keeps history/version)
    try:
        order = Order.from_dict(row)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to load order")

    try:
        order.transition_to(
            "cancelled",
            actor=str(current_user.get("username") or current_user.get("id") or ""),
            meta=payload.meta if payload else None,
            expected_version=payload.expected_version if payload else None,
        )
    except InvalidTransition as it:
        raise HTTPException(status_code=400, detail=str(it))
    except OptimisticLockError as ol:
        raise HTTPException(status_code=409, detail=str(ol))

    updates = {
        "status": order.status,
        "status_history": json.dumps(order.status_history or [], ensure_ascii=False),
        "version": int(order.version),
    }

    if refund_result:
        updates.update(
            {
                "last_refund_tx": refund_result.get("transaction_id"),
                "last_refund_msg": refund_result.get("message") or "ok",
                "last_refund_success": True,
                "refunded_at": datetime.utcnow().isoformat(sep=" "),
            }
        )

    updated = db.update_record("orders", "id", order_id, updates)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to persist order update")

    return {"ok": True, "order": updated}


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


@router.post("/{order_id}/transition")
def transition_order_status(
    order_id: str,
    payload: Dict[str, Any] = Body(...),  # { "status": "shipped", "expected_version": 0 (optional) }
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    """
    Transition an order to another state using the Order state machine.
    Body: { "status": "<target>", "expected_version": <int, optional> }
    Only the order owner or an admin may perform transitions.
    Returns the updated order record.
    """
    new_status = (payload.get("status") or "").strip()
    if not new_status:
        raise HTTPException(status_code=400, detail="status required")

    row = db.get_record("orders", "id", order_id)
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")

    # authorization: owner (by username) or admin
    username = current_user.get("username")
    is_admin = current_user.get("is_admin", False)
    if isinstance(is_admin, str):
        is_admin = is_admin.strip().lower() in ("1", "true", "yes", "y", "t")
    owner = str(row.get("user_id") or row.get("username") or "")
    if not is_admin and owner != str(username):
        raise HTTPException(status_code=403, detail="Not allowed to transition this order")

    # reconstruct domain Order and attempt transition
    try:
        order = Order.from_dict(row)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to load order")

    try:
        order.transition_to(
            new_status,
            actor=str(current_user.get("username") or current_user.get("id") or ""),
            meta=payload.get("meta"),
            expected_version=payload.get("expected_version"),
        )
    except InvalidTransition as it:
        raise HTTPException(status_code=400, detail=str(it))
    except OptimisticLockError as ol:
        raise HTTPException(status_code=409, detail=str(ol))

    # persist changes (update key fields)
    updates = {
        "status": order.status,
        "status_history": json.dumps(order.status_history or [], ensure_ascii=False),
        "version": int(order.version),
    }
    updated = db.update_record("orders", "id", order_id, updates)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to persist order update")

    return {"ok": True, "order": updated}
