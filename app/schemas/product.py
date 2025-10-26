# app/schemas/product.py
from pydantic import BaseModel, Field
from typing import Optional


class ProductCreate(BaseModel):
    title: str = Field(..., min_length=1)
    description: Optional[str] = ""
    category: Optional[str] = "general"
    price: float = Field(0.0, ge=0)
    stock: int = Field(0, ge=0)
    image_filename: Optional[str] = None


class ProductUpdate(BaseModel):
    title: Optional[str]
    description: Optional[str]
    category: Optional[str]
    price: Optional[float] = Field(None, ge=0)
    stock: Optional[int] = Field(None, ge=0)
    image_filename: Optional[str]


class ProductOut(BaseModel):
    id: Optional[str]
    title: str
    description: Optional[str]
    category: Optional[str]
    price: float
    stock: int
    image_filename: Optional[str]
    created_by: Optional[str]
    created_at: Optional[str]
