# app/api/routes/products.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from app.api.deps import get_db, get_current_active_user, require_admin
from app.schemas.product import ProductCreate, ProductOut, ProductUpdate
from app.database import FileBackedDB
from datetime import datetime

router = APIRouter(prefix="/api/products", tags=["products"])

db: FileBackedDB = get_db()


def _row_to_product_out(row: dict) -> ProductOut:
    # Ensure fields expected by ProductOut exist and have reasonable defaults
    return ProductOut(
        id=row.get("id") or row.get("product_id"),
        title=row.get("title") or "",
        description=row.get("description") or "",
        category=row.get("category") or "general",
        price=float(row.get("price") or 0.0),
        stock=int(float(row.get("stock") or 0)),
        image_filename=row.get("image_filename") or row.get("image") or None,
        created_by=row.get("created_by") or None,
        created_at=row.get("created_at") or None,
    )


@router.get("/", response_model=List[ProductOut])
def list_products(q: Optional[str] = Query(None, description="search query (title)"), limit: int = 100, offset: int = 0):
    """
    List products. Supports optional title substring search via `q`.
    """
    all_rows = db.list_records("products")
    results = []
    for r in all_rows:
        title = str(r.get("title") or "")
        if q:
            if q.lower() not in title.lower():
                continue
        results.append(_row_to_product_out(r))
    # apply offset/limit
    return results[offset : offset + limit]


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: str):
    row = db.get_record("products", "id", product_id) or db.get_record("products", "product_id", product_id)
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    return _row_to_product_out(row)


@router.post("/", response_model=ProductOut, dependencies=[Depends(require_admin)])
def create_product(payload: ProductCreate, current_user: dict = Depends(get_current_active_user)):
    """
    Create a new product (admin only). `created_by` is set to current_user['username'].
    """
    data = payload.model_dump()
    data["created_by"] = current_user.get("username")
    data["created_at"] = datetime.utcnow().isoformat(sep=" ")
    saved = db.create_record("products", data, id_field="id")
    return _row_to_product_out(saved)


@router.put("/{product_id}", response_model=ProductOut, dependencies=[Depends(require_admin)])
def update_product(product_id: str, payload: ProductUpdate):
    # find product
    row = db.get_record("products", "id", product_id) or db.get_record("products", "product_id", product_id)
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    updates = payload.model_dump(exclude_unset=True)
    updated = db.update_record("products", "id", product_id, updates)
    if not updated:
        # maybe update by product_id key
        updated = db.update_record("products", "product_id", product_id, updates)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update")
    return _row_to_product_out(updated)


@router.delete("/{product_id}", dependencies=[Depends(require_admin)])
def delete_product(product_id: str):
    # try by id then product_id
    ok = db.delete_record("products", "id", product_id)
    if not ok:
        ok = db.delete_record("products", "product_id", product_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"ok": True}
