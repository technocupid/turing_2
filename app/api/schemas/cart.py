from typing import List, Optional
from pydantic import BaseModel


class CartItemSchema(BaseModel):
    product_id: str
    title: Optional[str] = ""
    unit_price: float
    quantity: int


class CartCreateSchema(BaseModel):
    user_id: Optional[str] = ""
    items: List[CartItemSchema] = []
    updated_at: Optional[str] = ""