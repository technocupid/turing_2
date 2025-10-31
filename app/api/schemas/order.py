from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator, ConfigDict
import json


class OrderItem(BaseModel):
    product_id: str = Field(..., description="Product identifier")
    unit_price: float = Field(..., ge=0.0, description="Unit price at time of ordering")
    quantity: int = Field(..., ge=1, description="Quantity ordered")
    title: Optional[str] = Field(None, description="Optional product title snapshot")


class OrderCreate(BaseModel):
    cart_id: Optional[str] = Field(None, description="Optional cart id to build items from")
    items: Optional[List[OrderItem]] = Field(None, description="Inline list of items if not using cart_id")
    shipping_address: Optional[str] = Field(None, description="Shipping address / destination")


class PaymentRequest(BaseModel):
    type: str = Field(..., description="Payment type (e.g. 'card','test')")
    card_last4: Optional[str] = Field(None, description="Last 4 digits of card (test gateways use '4242')")


class CancelRequest(BaseModel):
    meta: Optional[Dict[str, Any]] = Field(None, description="Optional transition metadata")
    expected_version: Optional[int] = Field(None, description="Optimistic-lock expected version")


class OrderOut(BaseModel):
    id: Optional[str] = None
    user_id: Optional[str] = None
    # accept either a list or a stringified JSON (DB may store items as JSON string)
    items: Optional[Any] = None
    total_amount: Optional[float] = None
    status: Optional[str] = None
    created_at: Optional[str] = None
    paid_at: Optional[str] = None
    last_payment_tx: Optional[str] = None
    last_refund_tx: Optional[str] = None
    last_refund_success: Optional[Any] = None
    refunded_at: Optional[str] = None
    version: Optional[int] = None
    status_history: Optional[Any] = None

    @field_validator("items", mode="before")
    def _parse_items(cls, v):
        # DB may return items as JSON string; try to decode to list for response_model
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed
            except Exception:
                return v
        return v

    # allow extra fields from DB rows (backwards compatibility)
    model_config = ConfigDict(extra="allow")


class OrderResponse(BaseModel):
    ok: bool
    order: OrderOut