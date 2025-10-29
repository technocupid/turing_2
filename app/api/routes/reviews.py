from typing import List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Body

from app.database import db
from app.api.deps import oauth2_scheme

router = APIRouter(prefix="/api/products", tags=["reviews"])


def _current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth token")
    return token


@router.post("/{product_id}/reviews", status_code=201)
def create_review(product_id: str, payload: Dict[str, Any] = Body(...), user_id: str = Depends(_current_user_id)):
    """
    Create a review for a product.
    Body: { "rating": int (1-5), "body": "optional text" }
    """
    try:
        rating = int(payload.get("rating"))
    except Exception:
        raise HTTPException(status_code=400, detail="rating must be an integer 1-5")
    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="rating must be between 1 and 5")

    # ensure product exists
    prod = db.get_record("products", "id", product_id) or db.get_record("products", "product_id", product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")

    review = {
        "product_id": product_id,
        "user_id": user_id,
        "rating": rating,
        "body": payload.get("body", "") or "",
        "created_at": datetime.utcnow().isoformat(sep=" "),
    }
    saved = db.create_record("reviews", review, id_field="id")
    return saved


@router.get("/{product_id}/reviews", response_model=List[Dict])
def list_reviews(product_id: str):
    rows = db.list_records("reviews")
    out = [r for r in rows if str(r.get("product_id")) == str(product_id)]
    return out


@router.get("/{product_id}/reviews/summary", response_model=Dict)
def reviews_summary(product_id: str):
    rows = db.list_records("reviews")
    prod_rows = [r for r in rows if str(r.get("product_id")) == str(product_id)]
    if not prod_rows:
        return {"count": 0, "average": 0.0}
    count = len(prod_rows)
    try:
        avg = sum(float(r.get("rating", 0)) for r in prod_rows) / count
    except Exception:
        avg = 0.0
    return {"count": count, "average": round(avg, 2)}


@router.delete("/{product_id}/reviews/{review_id}", status_code=204)
def delete_review(product_id: str, review_id: str, user_id: str = Depends(_current_user_id)):
    rec = db.get_record("reviews", "id", review_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Review not found")
    if str(rec.get("product_id")) != str(product_id):
        raise HTTPException(status_code=400, detail="Review does not belong to product")
    if str(rec.get("user_id")) != str(user_id):
        # attempt to delete by non-owner
        raise HTTPException(status_code=403, detail="Not allowed")
    ok = db.delete_record("reviews", "id", review_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete")
    return {}

# --- Review response (admin-only) endpoints ---
@router.post("/{product_id}/reviews/{review_id}/response", status_code=201)
def create_review_response(product_id: str, review_id: str, payload: Dict[str, Any] = Body(...), admin_user: Dict[str, Any] = Depends(require_admin)):
    """
    Create a single admin response to a review. Only one response per review allowed.
    Body: { "body": "response text" }
    """
    rec = db.get_record("reviews", "id", review_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Review not found")
    if str(rec.get("product_id")) != str(product_id):
        raise HTTPException(status_code=400, detail="Review does not belong to product")

    # disallow if response already exists
    if rec.get("response_body"):
        raise HTTPException(status_code=400, detail="Response already exists for this review")

    response_body = (payload.get("body") or "").strip()
    if not response_body:
        raise HTTPException(status_code=400, detail="Response body required")

    # attach response fields onto review record and persist (replace record)
    rec["response_body"] = response_body
    rec["response_author_id"] = admin_user.get("id")
    rec["response_created_at"] = datetime.utcnow().isoformat(sep=" ")
    # persist update by deleting and recreating with same id
    if not db.delete_record("reviews", "id", review_id):
        raise HTTPException(status_code=500, detail="Failed to update review")
    saved = db.create_record("reviews", rec, id_field="id")
    return saved

@router.put("/{product_id}/reviews/{review_id}/response", status_code=200)
def edit_review_response(product_id: str, review_id: str, payload: Dict[str, Any] = Body(...), admin_user: Dict[str, Any] = Depends(require_admin)):
    """
    Edit existing admin response to a review.
    Body: { "body": "new response text" }
    """
    rec = db.get_record("reviews", "id", review_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Review not found")
    if str(rec.get("product_id")) != str(product_id):
        raise HTTPException(status_code=400, detail="Review does not belong to product")

    if not rec.get("response_body"):
        raise HTTPException(status_code=404, detail="Response not found")

    response_body = (payload.get("body") or "").strip()
    if not response_body:
        raise HTTPException(status_code=400, detail="Response body required")

    rec["response_body"] = response_body
    rec["response_author_id"] = admin_user.get("id")
    rec["response_updated_at"] = datetime.utcnow().isoformat(sep=" ")

    if not db.delete_record("reviews", "id", review_id):
        raise HTTPException(status_code=500, detail="Failed to update review")
    saved = db.create_record("reviews", rec, id_field="id")
    return saved

@router.delete("/{product_id}/reviews/{review_id}/response", status_code=204)
def delete_review_response(product_id: str, review_id: str, admin_user: Dict[str, Any] = Depends(require_admin)):
    """
    Delete admin response attached to a review.
    """
    rec = db.get_record("reviews", "id", review_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Review not found")
    if str(rec.get("product_id")) != str(product_id):
        raise HTTPException(status_code=400, detail="Review does not belong to product")

    if not rec.get("response_body"):
        raise HTTPException(status_code=404, detail="Response not found")

    # remove response fields and persist
    rec.pop("response_body", None)
    rec.pop("response_author_id", None)
    rec.pop("response_created_at", None)
    rec.pop("response_updated_at", None)

    if not db.delete_record("reviews", "id", review_id):
        raise HTTPException(status_code=500, detail="Failed to update review")
    saved = db.create_record("reviews", rec, id_field="id")
    if not saved:
        raise HTTPException(status_code=500, detail="Failed to persist review")
    return {}