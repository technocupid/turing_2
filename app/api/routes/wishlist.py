from typing import List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime
from app.database import db
from app.api.deps import oauth2_scheme
from app.api.schemas.wishlist import WishlistCreate, WishlistItemOut, CartItemOut

router = APIRouter(prefix="/api", tags=["wishlist"])

def _current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    """
    Minimal resolver: treat the oauth2 token as the user id.
    Replace with real get_current_user if you have one.
    """
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth token")
    return token

@router.get("/wishlist", response_model=List[WishlistItemOut])
def list_wishlist(user_id: str = Depends(_current_user_id)):
    items = db.list_records("wishlists")
    user_items = [i for i in items if str(i.get("user_id")) == str(user_id)]
    return user_items

@router.post("/wishlist", status_code=201, response_model=WishlistItemOut)
def add_to_wishlist(payload: WishlistCreate, user_id: str = Depends(_current_user_id)):
    product_id = payload.product_id
    product = db.get_record("products", "id", product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    record = {"user_id": user_id, "product_id": product_id, "added_at": datetime.utcnow().isoformat(sep=" ")}
    saved = db.create_record("wishlists", record, id_field="id")
    return saved

@router.delete("/wishlist/{item_id}", status_code=204)
def remove_wishlist_item(item_id: str, user_id: str = Depends(_current_user_id)):
    rec = db.get_record("wishlists", "id", item_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Wishlist item not found")
    if str(rec.get("user_id")) != str(user_id):
        raise HTTPException(status_code=403, detail="Not allowed")
    ok = db.delete_record("wishlists", "id", item_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete")
    return {}

# --- new endpoint: move wishlist item to cart ---
@router.post("/wishlist/{item_id}/move-to-cart", status_code=201, response_model=CartItemOut)
def move_wishlist_item_to_cart(item_id: str, user_id: str = Depends(_current_user_id)):
    """
    Move a wishlist item into the user's cart.
    - Validates ownership of wishlist item
    - Validates product exists
    - Creates a cart item (quantity=1) and deletes the wishlist entry
    Returns the created cart item.
    """
    # fetch wishlist item
    wish = db.get_record("wishlists", "id", item_id)
    if not wish:
        raise HTTPException(status_code=404, detail="Wishlist item not found")
    if str(wish.get("user_id")) != str(user_id):
        raise HTTPException(status_code=403, detail="Not allowed")

    product_id = wish.get("product_id")
    # validate product exists
    prod = db.get_record("products", "id", product_id) or db.get_record("products", "product_id", product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")

    cart_item = {
        "user_id": user_id,
        "product_id": product_id,
        "quantity": 1,
        "added_at": datetime.utcnow().isoformat(sep=" "),
    }
    created = db.create_record("carts", cart_item, id_field="id")

    # remove wishlist entry
    deleted = db.delete_record("wishlists", "id", item_id)
    if not deleted:
        # Attempt to rollback cart creation would be ideal; for now surface error
        raise HTTPException(status_code=500, detail="Failed to remove wishlist item after adding to cart")

    return created