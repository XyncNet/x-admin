import uuid
import redis.asyncio as redis
from fastapi import Depends, Form
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.status import HTTP_303_SEE_OTHER, HTTP_401_UNAUTHORIZED, HTTP_307_TEMPORARY_REDIRECT
from starlette.templating import Jinja2Templates
from tortoise import signals

# from tortoise_api.oauth import cc
from tortoise_api_model import User

from femto_admin import constants
from femto_admin.depends import get_current_admin, get_redis

access_token = "access_token"
login_title = "Login to your account"
login_logo_url: str

# admin.app.post("/login")(self.login) # api /token
# admin.app.add_middleware(BaseHTTPMiddleware, dispatch=self.authenticate) # admin_dep
# admin.app.get("/register")(self.init_view) # api /token
# signals.pre_save(self.admin_model)(self.pre_save_admin) # in model




async def login(request: Request, redis: redis.Redis = Depends(get_redis)):
    form = await request.form()
    username = form.get("username")
    password = form.get("password")
    remember_me = form.get("remember_me")
    admin = await admin_model.get_or_none(username=username)
    if not admin or not admin.verify(password):
        return self.templates.TemplateResponse(
            "providers/login/login.html",
            status_code=HTTP_401_UNAUTHORIZED,
            context={"request": request, "error": "login_failed"},
        )
    response = RedirectResponse(url='/admin', status_code=HTTP_303_SEE_OTHER)
    if remember_me == "on":
        expire = 3600 * 24 * 30
        response.set_cookie("remember_me", "on")
    else:
        expire = 3600
        response.delete_cookie("remember_me")
    token = uuid.uuid4().hex
    response.set_cookie(
        self.access_token,
        token,
        expires=expire,
        path='/admin',
        httponly=True,
    )
    await redis.set(constants.LOGIN_USER.format(token=token), admin.pk, ex=expire)
    return response


# async def logout(request: Request):
#     response = redirect_login(request)
#     response.delete_cookie(self.access_token, path='/admin')
#     token = request.cookies.get(self.access_token)
#     await request.app.redis.delete(constants.LOGIN_USER.format(token=token))
#     return response


# async def authenticate(
#         request: Request,
# ):
#     path = request.scope["path"]
#     redis: Redis = request.app.redis
#     token = request.cookies.get('token')
#     admin = None
#     if token:
#         token_key = constants.LOGIN_USER.format(token=token)
#         admin_id = await redis.get(token_key)
#         admin = await create_user.get_or_none(pk=admin_id)
#     request.state.admin = admin
#
#     if path != '/login':
#         if admin:
#             response = await call_next(request)
#             return response
#         return RedirectResponse(url='/login', status_code=HTTP_303_SEE_OTHER)
#     if admin:
#         return RedirectResponse(url='/admin', status_code=HTTP_307_TEMPORARY_REDIRECT)
#     response = await call_next(request)
#     return response


# async def create_user(self, username: str, email: str, password: str, **kwargs):
#     return await self.admin_model.create(username=username, email=email, password=password, **kwargs)
#
#
# async def init(
#         request: Request,
# ):
#     exists = await self.admin_model.all().limit(1).exists()
#     if exists:
#         return self.redirect_login(request)
#     form = await request.form()
#     password = form.get("password")
#     confirm_password = form.get("confirm_password")
#     username = form.get("username")
#     email = form.get("email")
#     if password != confirm_password:
#         return self.templates.TemplateResponse(
#             "init.html",
#             context={"request": request, "error": "confirm_password_different"},
#         )
#
#     await self.create_user(username, email, password)
#     return self.redirect_login(request)


# async def password(
#         request: Request,
#         old_password: str = Form(...),
#         new_password: str = Form(...),
#         re_new_password: str = Form(...),
#         admin: User = Depends(get_current_admin),
# ):
#     error = None
#     if not cc.verify(old_password, admin.password):
#         error = "old_password_error"
#     elif new_password != re_new_password:
#         error = "new_password_different"
#     if error:
#         return request.app.templates.TemplateResponse("password.html", context={"request": request, "error": error})
#     admin.password = new_password
#     await admin.save(update_fields=["password"])
#     return await logout(request)
