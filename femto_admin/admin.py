from datetime import datetime
from enum import StrEnum
from functools import partial
from types import ModuleType
from typing import Annotated, Type, List, Dict, Literal

from fastapi import FastAPI, APIRouter, Depends, Security, HTTPException, Form, Cookie, Query, Body, Path
from fastapi.routing import APIRoute
from fastapi.security import OAuth2PasswordRequestForm
from jinja2 import ChoiceLoader, FileSystemLoader, PackageLoader
from pydantic import BaseModel
from redis.asyncio import Redis
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette import status
from starlette.templating import Jinja2Templates, _TemplateResponse
from tortoise.contrib.pydantic import pydantic_model_creator, PydanticModel
from tortoise.fields import ReverseRelation
from tortoise_api.api import Api
from tortoise_api.oauth import get_current_active_user, my, read, reg_user, login_for_access_token, EXPIRES, \
    authenticate_user, AuthFailReason, UserSchema
from tortoise_api_model import Model, User, PydList

import femto_admin
from femto_admin import auth_dep
from femto_admin.utils.parse import parse_fs


class Dir(StrEnum):
    asc = 'asc'
    desc = 'desc'


class Order(BaseModel):
    column: int
    dir: Dir = Dir.asc.value


class Dtp(BaseModel):
    draw: int
    # columns: List[Column]
    order: List[Order]
    start: int
    length: int
    # search: Search


class Admin(Api):
    app: FastAPI

    def __init__(
            self,
            models_module: ModuleType,
            debug: bool = False,
            title: str = "Admin",
            static_dir: str = None,
            logo: str | bool = None,
            exc_models: [str] = [],
    ):
        """
        Parameters:
            title: Admin title.
            # auth_provider: Authentication Provider
        """
        # Api init
        super().__init__(models_module, debug, title, exc_models)
        # Authenticable model (maybe overriden)
        user_model = self.models['User']

        templates = Jinja2Templates("templates")

        if static_dir:
            self.app.mount('/' + static_dir, StaticFiles(directory=static_dir), name='my-public'),
            if logo is not None:
                templates.env.globals["logo"] = logo
        favicon_path = f'./{static_dir or "statics/placeholders"}/favicon.ico'
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
            # APIRoute('/logout', auth_dep.logout),
            APIRoute('/password', self.password_view, dependencies=[my]),
            # APIRoute('/password', auth_dep.password, methods=['POST'], dependencies=[my]),
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
            ar.add_api_route('/dt/' + name, self.dt, name=name + ' datatables format', tags=['api'], methods=['POST'], response_model=[]),
            ar.add_api_route(f'/{name}/{"{oid}"}', self.edit, name='Edit view'),
            ar.add_api_route('/' + name, partial(self.index, ), name=name + ' list')
        self.app.include_router(ar)

    async def login_view(
            self,
            request: Request,
            reason: Annotated[str|None, Cookie()] = None,
            username: Annotated[str|None, Cookie()] = None,
            password: Annotated[str|None, Cookie()] = None
    ) -> _TemplateResponse:
        response = self.templates.TemplateResponse("providers/login/login.html", context={
            "request": request,
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
        if isinstance(user_cred, AuthFailReason):
            response = RedirectResponse(url='/login', status_code=status.HTTP_303_SEE_OTHER)
            response.set_cookie('reason', user_cred.name)
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
                jwt.access_token,
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
        if user := await reg_user(UserSchema.model_validate(obj)):
            # todo get permissions (scopes) from user.role in `scope`:str (separated by spaces)
            scopes = ["my", "read"]
            jwt = await login_for_access_token(
                OAuth2PasswordRequestForm(username=user.username, password=obj['password'], scope=' '.join(scopes))
            )
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
        model: Type[Model] = self.models.get(request.scope['path'][1:])
        await model.load_rel_options()
        return self.templates.TemplateResponse("index.html", {
            'model': model,
            'subtitle': model._meta.table_description,
            'request': request,
        })

    async def edit(self, request: Request):
        mod_name = request.scope['path'][1:].split('/')[0]
        model: Type[Model] = self.models.get(mod_name)
        oid = request.path_params['oid']
        await model.load_rel_options()
        obj: Model = await model.get(id=oid).prefetch_related(*model._meta.fetch_fields)
        bfms = {getattr(obj, k).remote_model: [ros.pk for ros in getattr(obj, k)] for k in model._meta.backward_fk_fields}
        [await bfm.load_rel_options() for bfm in bfms]
        return self.templates.TemplateResponse("edit.html", {
            'model': model,
            'subtitle': model._meta.table_description,
            'request': request,
            'obj': obj,
            'bfms': bfms,
        })

    async def dt(self, request: Request): # length: int = 100, start: int = 0
        model: Type[Model] = self.models.get(request.scope['path'][4:])
        meta = model._meta
        form = await request.body()
        form = parse_fs(form.decode())
        col_names = list(model.field_input_map().keys())
        order = [('-' if ord['dir']=='desc' else '')+(col_name+'__'+meta.fields_map[col_name].related_model._name if (col_name:=col_names[ord['column']]) in meta.fk_fields else col_name) for ord in form['order']]

        def render(obj: Model):
            def rel(val: dict):
                return f'<a class="m-1 py-1 px-2 badge bg-blue-lt lead" href="/{val["type"]}/{val["id"]}">{val["repr"]}</a>'

            def check(val, key: str):
                if key=='id':
                    return rel({'type': model.__name__, 'id': val, 'repr': val})
                if isinstance(val, Model):
                    val = {'type': val.__class__.__name__, 'id': val.id, 'repr': val.repr()}
                    return rel(val)
                elif isinstance(val, ReverseRelation):
                    r = [rel({'type': v.__class__.__name__, 'id': v.id, 'repr': v.repr()}) for v in val.related_objects]
                    return ' '.join(r)
                return f'{val[:120]}..' if isinstance(val, str) and len(val) > 120 else val

            return {key: check(obj.__getattribute__(key), key) for key in obj._meta.fields_map if not key.endswith('_id')}

        objs: [Model] = await model.pageQuery(form['length'], form['start'], order, True)
        data = [render(obj) for obj in objs]
        total = len(data)+form['start'] if form['length']-len(data) else await model.all().count()
        return {'draw': int(form['draw']), 'recordsTotal': total, 'recordsFiltered': total, 'data': data}
