from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, constr, conint, field_validator


class ReviewCreate(BaseModel):
    rating: conint(ge=1, le=5) = Field(..., description="Rating between 1 and 5")
    body: str = ""

    @field_validator("body", mode="before")
    @classmethod
    def default_body(cls, v):
        # convert None to empty string; leave other values (including "") unchanged
        return "" if v is None else v


class ResponseCreate(BaseModel):
    body: constr(strip_whitespace=True, min_length=1) = Field(..., description="Non-empty response body")


class ReviewOut(BaseModel):
    id: str
    product_id: str
    user_id: str
    rating: int
    body: str
    created_at: str
    response_body: Optional[str] = None
    response_author_id: Optional[str] = None
    response_created_at: Optional[str] = None
    response_updated_at: Optional[str] = None

    model_config = ConfigDict(extra="allow")