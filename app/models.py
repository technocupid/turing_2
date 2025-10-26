from pydantic import BaseModel, Field
from typing import Optional


class ItemCreate(BaseModel):
    title: str
    description: Optional[str] = ''
    category: Optional[str] = 'general'
    price: float = Field(0.0, ge=0)
    stock: int = Field(0, ge=0)
    image_filename: Optional[str] = ''


class ItemUpdate(BaseModel):
    title: Optional[str]
    description: Optional[str]
    category: Optional[str]
    price: Optional[float]
    stock: Optional[int]
    image_filename: Optional[str]


class User(BaseModel):
    username: str
    is_admin: bool = False