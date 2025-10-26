
### FILE: app/routers/items.py
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import FileResponse
import os
from app.db.excel_db import excel_db
from app.models import ItemCreate, ItemUpdate
from app.core.config import settings
from app.auth import get_current_user, require_admin

router = APIRouter(prefix='/items', tags=['items'])

@router.get('/')
async def list_items():
    return excel_db.list_items()

@router.get('/{item_id}')
async def get_item(item_id: str):
    item = excel_db.get_item(item_id)
    if not item:
        raise HTTPException(404, 'Item not found')
    return item

@router.post('/', dependencies=[Depends(require_admin)])
async def create_item(item: ItemCreate):
    data = item.dict()
    data['created_by'] = 'admin'
    created = excel_db.create_item(data)
    return created

@router.put('/{item_id}', dependencies=[Depends(require_admin)])
async def update_item(item_id: str, update: ItemUpdate):
    updated = excel_db.update_item(item_id, update.dict(exclude_unset=True))
    if not updated:
        raise HTTPException(404, 'Item not found')
    return updated

@router.delete('/{item_id}', dependencies=[Depends(require_admin)])
async def delete_item(item_id: str):
    success = excel_db.delete_item(item_id)
    if not success:
        raise HTTPException(404, 'Item not found')
    return {'ok': True}

@router.post('/upload-image', dependencies=[Depends(require_admin)])
async def upload_image(file: UploadFile = File(...), title: str = Form(None)):
    os.makedirs(settings.IMAGE_DIR, exist_ok=True)
    # sanitize filename in real app
    filename = f"{int(__import__('time').time())}_{file.filename}"
    path = os.path.join(settings.IMAGE_DIR, filename)
    async with open(path, 'wb') as f:
        content = await file.read()
        f.write(content)
    # Return filename for inclusion in Excel record
    return {"filename": filename}

@router.get('/image/{filename}')
async def get_image(filename: str):
    path = os.path.join(settings.IMAGE_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, 'Image not found')
    return FileResponse(path)
