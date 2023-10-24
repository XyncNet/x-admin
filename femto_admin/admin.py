from datetime import datetime
from functools import partial
from os import path
from types import ModuleType
from typing import Annotated

from fastapi import FastAPI, APIRouter, Depends, Security, HTTPException, Form, Body, Cookie
from fastapi.encoders import jsonable_encoder
from fastapi.responses import ORJSONResponse
from fastapi.routing import APIRoute
from fastapi.security import OAuth2PasswordRequestForm
from jinja2 import ChoiceLoader, FileSystemLoader, PackageLoader
from redis.asyncio import Redis
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette import status
from starlette.templating import Jinja2Templates, _TemplateResponse
from tortoise.contrib.pydantic import pydantic_model_creator
from tortoise_api.api import Api
from tortoise_api.oauth import get_current_active_user, my, read, UserCred, reg_user, login_for_access_token, EXPIRES, \
    authenticate_user
from tortoise_api_model import Model, User

import femto_admin
from femto_admin import auth_dep


class Admin(Api):
    app: FastAPI

    def __init__(
            self,
            models_module: ModuleType,
            debug: bool = False,
            title: str = "Admin",
            static_dir: str = None,
            logo: str | bool = None,
    ):
        """
        Parameters:
            title: Admin title.
            # auth_provider: Authentication Provider
        """
        # Api init
        super().__init__(models_module, debug, title)
        # Authenticable model (maybe overriden)
        user_model = self.models['User']

        templates = Jinja2Templates("templates")

        if static_dir:
            self.app.mount('/' + static_dir, StaticFiles(directory=static_dir), name='my-public'),
            if logo is not None:
                templates.env.globals["logo"] = logo
        if path.exists(favicon_path := f'./{static_dir or "statics/placeholders"}/favicon.ico'):
            self.app.add_route('/favicon.ico', lambda r: RedirectResponse(favicon_path, status_code=301))

        templates.env.loader = ChoiceLoader([FileSystemLoader("templates"), PackageLoader("femto_admin", "templates")])
        templates.env.globals["title"] = title
        templates.env.globals["meta"] = {'year': datetime.now().year, 'ver': femto_admin.__version__}
        templates.env.globals["minify"] = '' if debug else 'min.'
        templates.env.globals["models"] = self.models
        self.templates = templates

    def get_app(self, dash_func: callable = None):
        self.app.mount('/statics', StaticFiles(packages=["femto_admin"]), name='public'),
        routes: [Route] = [
            APIRoute('/', dash_func or self.dash, name="Dashboard"),
            # auth routes:
            APIRoute('/logout', auth_dep.logout),
            APIRoute('/password', self.password_view, dependencies=[my]),
            APIRoute('/password', auth_dep.password, methods=['POST'], dependencies=[my]),
        ]
        self.app.include_router(
            APIRouter(routes=routes),
            tags=['admin'],
            dependencies=[Depends(self.auth_middleware)],
            # include_in_schema=False,
        )
        self.app.get("/login")(self.login_view)
        self.app.post("/login")(self.login)
        self.app.get("/reg")(self.init_view)
        self.app.post("/reg")(self.reg)
        self.app.on_event('startup')(self.startup)
        self.set_routes()
        return self.app

    async def startup(self):
        self.app.redis = await Redis()

    @staticmethod
    async def auth_middleware(request: Request):
        path: str = request.scope["path"]
        redis: Redis = request.app.redis
        if not (token := request.cookies.get('token')):
            raise HTTPException(
                status_code=status.HTTP_303_SEE_OTHER,
                headers={'Location': "/login"},
                detail="Not authenticated bruh"
            )
        # return RedirectResponse(url='/login', status_code=status.HTTP_303_SEE_OTHER)

    def set_routes(self):
        ar = APIRouter(tags=['admin'], dependencies=[Depends(self.auth_middleware)])
        for name, model in self.models.items():
            pyd_model = pydantic_model_creator(model)
            ar.add_api_route('/dt/' + name, self.dt, name=name + ' datatables format', tags=['api'],
                             response_model=[]),
            ar.add_api_route(f'/{name}/{"{oid}"}', self.edit, name='Edit view'),
            ar.add_api_route('/' + name, partial(self.index, ), name=name + ' list')
        self.app.include_router(ar)

    async def login_view(
            self,
            reason: Annotated[str|None, Cookie()] = None,
            username: Annotated[str|None, Cookie()] = None,
            password: Annotated[str|None, Cookie()] = None
    ) -> _TemplateResponse:
        response = self.templates.TemplateResponse("providers/login/login.html", context={
            # "request": request,
            "reason": reason,
            "username": username,
            "password": password,
        })
        response.delete_cookie('reason')
        response.delete_cookie('username')
        response.delete_cookie('password')
        return response

    async def password_view(self, request: Request):
        return self.templates.TemplateResponse("providers/login/password.html", context={"request": request})

    async def init_view(self, request: Request):
        return self.templates.TemplateResponse("init.html", context={"request": request})

    @staticmethod
    async def login(username: Annotated[str, Form()], password: Annotated[str, Form()]):
        user_cred = await authenticate_user(username, password)
        if isinstance(user_cred, dict) and (error := user_cred.get('error')):
            response = RedirectResponse(url='/login', status_code=status.HTTP_303_SEE_OTHER)
            response.set_cookie('reason', error)
            response.set_cookie('username', username)
            response.set_cookie('password', password)
            return response
        if user_cred:
            # todo get permissions (scopes) from user.role in `scope`:str (separated by spaces)
            scopes = ["my", "read"]
            jwt = await login_for_access_token(
                OAuth2PasswordRequestForm(username=username, password=password, scope=' '.join(scopes)))
            response = RedirectResponse(url='/', status_code=status.HTTP_303_SEE_OTHER)
            response.set_cookie(
                'token',
                jwt['access_token'],
                expires=EXPIRES,
                path='/',
                httponly=True,
            )
            # await redis.set(constants.LOGIN_USER.format(token=token), admin.pk, ex=expire)
            return response
        return RedirectResponse(url='/login', status_code=status.HTTP_303_SEE_OTHER)

    @staticmethod
    async def reg(request: Request):
        obj = await request.form()
        if user := await reg_user(UserCred.model_validate(obj)):
            # todo get permissions (scopes) from user.role in `scope`:str (separated by spaces)
            scopes = ["my", "read"]
            jwt = await login_for_access_token(
                OAuth2PasswordRequestForm(username=user.username, password=obj['password'], scope=' '.join(scopes)))
            response = RedirectResponse(url='/', status_code=status.HTTP_303_SEE_OTHER)
            response.set_cookie(
                'token',
                jwt['access_token'],
                expires=EXPIRES,
                path='/',
                httponly=True,
            )
            # await redis.set(constants.LOGIN_USER.format(token=token), admin.pk, ex=expire)
            return response

    # INTERFACE
    async def dash(self, request: Request):
        return self.templates.TemplateResponse("dashboard.html", {
            # 'model': 'Home',
            'subtitle': 'Dashboard',
            'request': request,
        })

    async def index(self, request: Request):
        model: type[Model] = self.models.get(request.scope['path'][1:])
        await model.load_rel_options()
        return self.templates.TemplateResponse("index.html", {
            'model': model,
            'subtitle': model._meta.table_description,
            'request': request,
        })

    async def edit(self, request: Request, model: str):
        model: type[Model] = self.models.get(model)
        oid = request.path_params['oid']
        await model.load_rel_options()
        obj: Model = await model.get(id=oid).prefetch_related(*model._meta.fetch_fields)
        bfms = [getattr(obj, k).remote_model for k in model._meta.backward_fk_fields]
        [await bfm.load_rel_options() for bfm in bfms]
        return self.templates.TemplateResponse("edit.html", {
            'model': model,
            'subtitle': model._meta.table_description,
            'request': request,
            'obj': obj,
            'bfms': bfms,
        })

    async def dt(self, request: Request, limit: int = 50, page: int = 1):
        async def render(obj: Model):
            def rel(val: dict):
                return f'<a class="m-1 py-1 px-2 badge bg-blue-lt lead" href="/admin/{val["type"]}/{val["id"]}">{val["repr"]}</a>'

            def check(val, is_id: bool):
                if isinstance(val, dict) and 'repr' in val.keys():
                    return rel(val)
                elif is_id:
                    return rel({'type': obj.__class__.__name__, 'id': val, 'repr': val})
                elif isinstance(val, list) and val and isinstance(val[0], dict) and 'repr' in val[0].keys():
                    return ' '.join(rel(v) for v in val)
                return f'{val[:100]}..' if isinstance(val, str) and len(val) > 100 else val

            return [check(val, key == 'id') for key, val in (await jsonable_encoder(obj)).items()]

        model: type[Model] = self.models.get(request.scope['path'][4:])
        objects: [Model] = await model.all().prefetch_related(*model._meta.fetch_fields).limit(limit).offset(
            limit * (page - 1))

        data = [await render(obj) for obj in objects]
        return ORJSONResponse({'data': data})
