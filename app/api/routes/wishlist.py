from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from app.database import db
from app.api.deps import oauth2_scheme

router = APIRouter(prefix="/api", tags=["wishlist"])

def _current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    """
    Minimal resolver: treat the oauth2 token as the user id.
    Replace with real get_current_user if you have one.
    """
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth token")
    return token

@router.get("/wishlist", response_model=List[Dict])
def list_wishlist(user_id: str = Depends(_current_user_id)):
    items = db.list_records("wishlists")
    user_items = [i for i in items if str(i.get("user_id")) == str(user_id)]
    return user_items

@router.post("/wishlist", status_code=201)
def add_to_wishlist(payload: Dict, user_id: str = Depends(_current_user_id)):
    product_id = payload.get("product_id")
    if not product_id:
        raise HTTPException(status_code=400, detail="product_id required")
    product = db.get_record("products", "id", product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    record = {"user_id": user_id, "product_id": product_id}
    saved = db.create_record("wishlists", record)
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