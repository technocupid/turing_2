### FILE: app/admin.py
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from app.auth import require_admin
from app.db.excel_db import excel_db

router = APIRouter(prefix='/admin', tags=['admin'])
templates = Jinja2Templates(directory='templates')

@router.get('/', dependencies=[Depends(require_admin)])
async def admin_dashboard(request: Request):
    items = excel_db.list_items()
    return templates.TemplateResponse('admin.html', {'request': request, 'items': items})
