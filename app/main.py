### FILE: app/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routers import items, auth as auth_router
from app import admin
from app.core.config import settings
from app.routers import admin_auth

app = FastAPI(title='Decor Store API')

# Mount static files
app.mount('/static', StaticFiles(directory='static'), name='static')

# include routers
app.include_router(auth_router.router)
app.include_router(items.router)
app.include_router(admin.router)
app.include_router(admin_auth.router)

@app.get('/')
async def root():
    return {'status': 'ok', 'service': 'Decor Store API'}