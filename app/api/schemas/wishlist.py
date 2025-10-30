# --- Pydantic schemas for wishlist endpoints ---
from typing import Optional
from pydantic import BaseModel, Field


class WishlistCreate(BaseModel):
    product_id: str = Field(..., description="ID of the product to add to the wishlist")

class WishlistItemOut(BaseModel):
    id: str
    user_id: str
    product_id: str
    added_at: Optional[str] = None

    class Config:
        orm_mode = True

class CartItemOut(BaseModel):
    id: str
    user_id: str
    product_id: str
    quantity: int
    added_at: Optional[str] = None

    class Config:
        orm_mode = True
