from fastapi import APIRouter, Request, Form, Response
from fastapi.templating import Jinja2Templates
from app.auth import authenticate_user, create_access_token
from datetime import timedelta
from app.core.config import settings

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/admin/login")
async def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@router.post("/admin/login")
async def login_post(response: Response, username: str = Form(...), password: str = Form(...)):
    user = authenticate_user(username, password)
    if not user:
        # return login page with error
        return templates.TemplateResponse("login.html", {"request": {}, "error": "Invalid credentials"})
    token = create_access_token(data={"sub": user["username"]}, expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    # set cookie (HttpOnly)
    response = templates.TemplateResponse("admin.html", {"request": {}, "items": []})
    response.set_cookie(key="access_token", value=token, httponly=True, max_age=60*60*24)
    # redirect to /admin would be better, but TemplateResponse can't redirect and set cookie in same response easily.
    # you can return a RedirectResponse instead if you prefer:
    # from fastapi.responses import RedirectResponse
    # redirect = RedirectResponse(url="/admin", status_code=303)
    # redirect.set_cookie(...)
    # return redirect
    return response