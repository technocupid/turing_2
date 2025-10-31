from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends
from app.api.deps import get_db
from app.models.cart import Cart, CartItem
from app.database import FileBackedDB
from app.api.schemas.cart import CartCreateSchema, CartItemSchema

router = APIRouter(prefix="/api/cart", tags=["cart"])


@router.post("", response_model=Dict[str, Any])
def create_cart(payload: CartCreateSchema, db: FileBackedDB = Depends(get_db)):
    """
    Create a cart record. Payload shape accepted by app.models.cart.Cart.from_dict.
    Returns the stored row (including generated 'id').
    """
    cart = Cart.from_dict(payload.model_dump())
    row = db.create_record("carts", cart.to_dict(), id_field="id")
    return row


@router.get("/{cart_id}", response_model=Dict[str, Any])
def get_cart(cart_id: str, db: FileBackedDB = Depends(get_db)):
    """
    Retrieve a cart by id. Returns 404 if not found.
    """
    row = db.get_record("carts", "id", cart_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found")
    return row


@router.post("/{cart_id}/items", response_model=Dict[str, Any])
def add_item_to_cart(cart_id: str, item: CartItemSchema, db: FileBackedDB = Depends(get_db)):
    """
    Append an item to an existing cart. This tries to update the existing cart row in-place.
    If the DB implementation provides update_record, it will be used. Otherwise we attempt
    to replace the existing row by deleting (if supported) and creating a new row with the same id.
    Returns the updated cart row (guaranteed to include the appended item).
    """
    row = db.get_record("carts", "id", cart_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found")

    # Build Cart object from stored row (handles stringified items)
    cart = Cart.from_dict(row)
    cart.items.append(CartItem.from_dict(item.model_dump()))
    new_row = cart.to_dict()
    # ensure id preserved
    new_row["id"] = cart_id

    # Prefer update_record when available
    if hasattr(db, "update_record"):
        try:
            try:
                db.update_record("carts", cart_id, new_row, id_field="id")
            except TypeError:
                db.update_record("carts", cart_id, new_row)
        except Exception:
            pass

    # If update didn't persist (or update_record not available), try delete+create or create with id
    updated = db.get_record("carts", "id", cart_id)
    if not updated or updated.get("items") == row.get("items"):
        if hasattr(db, "delete_record"):
            try:
                db.delete_record("carts", cart_id)
            except Exception:
                pass
        try:
            db.create_record("carts", new_row, id_field="id")
        except Exception:
            db.create_record("carts", {"id": cart_id, **new_row}, id_field="id")

    return new_row