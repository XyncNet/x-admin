import uuid
from typing import Type

import redis.asyncio as redis
from fastapi import Depends, Form, FastAPI, Cookie
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.status import HTTP_303_SEE_OTHER, HTTP_401_UNAUTHORIZED
from tortoise import signals

from tortoise_api.oauth import cc
from tortoise_api_model import User

from femto_admin.depends import get_current_admin, get_redis
from femto_admin.providers import Provider


class UsernamePasswordProvider(Provider):
    name = "login_provider"

    access_token = "access_token"

    def __init__(
        self,
        admin_model: Type[User],
        login_title="Login to your account",
        login_logo_url: str = None,
    ):
        self.admin_model = admin_model
        self.login_title = login_title
        self.login_logo_url = login_logo_url

    async def login_view(
        self,
        request: Request,
    ):
        return request.app.templates.TemplateResponse(
            "providers/login/login.html",
            context={
                "request": request,
                "login_logo_url": self.login_logo_url,
                "login_title": self.login_title,
            },
        )

    async def register(self, app: FastAPI):
        await super().register(app)
        app.get("/login")(self.login_view)
        app.post("/login")(self.login)
        app.get("/logout")(self.logout)
        app.add_middleware(BaseHTTPMiddleware, dispatch=self.authenticate)
        app.get("/init")(self.init_view)
        app.post("/init")(self.init)
        app.get("/password")(self.password_view)
        app.post("/password")(self.password)
        signals.pre_save(self.admin_model)(self.pre_save_admin)

    async def pre_save_admin(self, _, instance: User, using_db, update_fields):
        if instance.pk:
            db_obj = await instance.get(pk=instance.pk)
            if db_obj.password != instance.password:
                instance.password = cc.hash(instance.password)
        else:
            instance.password = cc.hash(instance.password)

    async def login(self, request: Request, redis: redis.Redis = Depends(get_redis)):
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
        remember_me = form.get("remember_me")
        admin = await self.admin_model.get_or_none(username=username)
        if not admin or not cc.verify(password, admin.password):
            return request.app.templates.TemplateResponse(
                "providers/login/login.html",
                status_code=HTTP_401_UNAUTHORIZED,
                context={"request": request, "error": "login_failed"},
            )
        response = RedirectResponse(url=request.app.admin_path, status_code=HTTP_303_SEE_OTHER)
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
            path=request.app.admin_path,
            httponly=True,
        )
        await redis.set(constants.LOGIN_USER.format(token=token), admin.pk, ex=expire)
        return response

    async def logout(self, request: Request):
        response = self.redirect_login(request)
        response.delete_cookie(self.access_token, path=request.app.admin_path)
        token = request.cookies.get(self.access_token)
        await request.app.redis.delete(constants.LOGIN_USER.format(token=token))
        return response

    async def authenticate(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ):
        redis: Redis = request.app.redis
        token = request.cookies.get(self.access_token)
        path = request.scope["path"]
        admin = None
        if token:
            token_key = constants.LOGIN_USER.format(token=token)
            admin_id = await redis.get(token_key)
            admin = await self.admin_model.get_or_none(pk=admin_id)
        request.state.admin = admin

        if path == '/login' and admin:
            return RedirectResponse(url=request.app.admin_path, status_code=HTTP_303_SEE_OTHER)

        response = await call_next(request)
        return response

    async def create_user(self, username: str, password: str, **kwargs):
        return await self.admin_model.create(username=username, password=password, **kwargs)

    async def init_view(self, request: Request):
        exists = await self.admin_model.all().limit(1).exists()
        if exists:
            return self.redirect_login(request)
        return request.app.templates.TemplateResponse("init.html", context={"request": request})

    async def init(
        self,
        request: Request,
    ):
        exists = await self.admin_model.all().limit(1).exists()
        if exists:
            return self.redirect_login(request)
        form = await request.form()
        password = form.get("password")
        confirm_password = form.get("confirm_password")
        username = form.get("username")
        if password != confirm_password:
            return request.app.templates.TemplateResponse(
                "init.html",
                context={"request": request, "error": "confirm_password_different"},
            )

        await self.create_user(username, password)
        return self.redirect_login(request)

    @staticmethod
    def redirect_login(request: Request):
        return RedirectResponse(url='/login', status_code=HTTP_303_SEE_OTHER)

    @staticmethod
    async def password_view(request: Request):
        return request.app.templates.TemplateResponse(
            "providers/login/password.html",
            context={"request": request},
        )

    async def password(
        self,
        request: Request,
        old_password: str = Form(...),
        new_password: str = Form(...),
        re_new_password: str = Form(...),
        admin: User = Depends(get_current_admin),
    ):
        error = None
        if not cc.verify(old_password, admin.password):
            error = "old_password_error"
        elif new_password != re_new_password:
            error = "new_password_different"
        if error:
            return request.app.templates.TemplateResponse("password.html", context={"request": request, "error": error})
        admin.password = new_password
        await admin.save(update_fields=["password"])
        return await self.logout(request)
