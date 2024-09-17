import datetime
from enum import StrEnum
from functools import partial
from types import ModuleType
from typing import Annotated, Type, List
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Form, Cookie
from fastapi.routing import APIRoute
from fastapi.security import OAuth2PasswordRequestForm
from jinja2 import ChoiceLoader, FileSystemLoader, PackageLoader
from pydantic import BaseModel
from pydantic.fields import FieldInfo

# from redis.asyncio import Redis
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.routing import Route
from starlette.staticfiles import StaticFiles
from starlette import status
from starlette.templating import Jinja2Templates, _TemplateResponse
from starlette.types import Lifespan
from tortoise_api.api import Api
from tortoise_api.loader import _repr
from tortoise_api.oauth import OAuth, AuthException
from tortoise_api_model import Model
from tortoise_api_model.pydantic import UserReg, PydList

from femto_admin.utils.fmap import ffrom_pyd
from femto_admin.utils.parse import parse_fs


class Dir(StrEnum):
    asc = "asc"
    desc = "desc"


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
    templates: Jinja2Templates
    debug: bool = False

    def __init__(
        self,
        models_module: ModuleType,
        debug: bool = False,
        title: str = "Admin",
        exc_models: {str} = None,
        lifespan: Lifespan = None,
        oauth: OAuth = None,
    ):
        """
        Parameters:
            title: Admin title.
            # auth_provider: Authentication Provider
        """
        # Api init
        super().__init__(models_module, debug, title, exc_models, lifespan, oauth)

        self.set_templates()

    def set_templates(self):
        templates = Jinja2Templates("templates")
        templates.env.loader = ChoiceLoader([FileSystemLoader("templates"), PackageLoader("femto_admin", "templates")])
        templates.env.globals["title"] = self.title
        templates.env.globals["meta"] = {"year": datetime.datetime.now().year}  # "ver": femto_admin.__version__
        templates.env.globals["minify"] = "" if self.debug else "min."
        templates.env.globals["models"] = self.models
        self.templates = templates

    def mount(self, static_dir: str = None, logo: str | bool = None, dash_func: callable = None):
        (self.app.mount("/statics", StaticFiles(packages=["femto_admin"]), name="public"),)
        if static_dir:
            assert static_dir != "statics", "Use any name for statics dir, but not `statics`"
            (self.app.mount("/" + static_dir, StaticFiles(directory=static_dir), name="my-public"),)
            if logo is not None:
                self.templates.env.globals["logo"] = logo
        favicon_path = f'./{static_dir or "statics/placeholders"}/favicon.ico'
        self.app.add_route(
            "/favicon.ico", lambda r: RedirectResponse(favicon_path, status_code=301), include_in_schema=False
        )

        routes: [Route] = [
            APIRoute("/", dash_func or self.dash, name="Dashboard"),
            # auth routes:
            APIRoute("/logout", self.logout),
            APIRoute("/password", self.password_view),
            # APIRoute('/password', auth_dep.password, methods=['POST'], dependencies=[my]),
        ]
        self.app.include_router(
            APIRouter(routes=routes),
            tags=["admin"],
            dependencies=[Depends(self.auth_middleware)],
            include_in_schema=False,
        )
        self.app.get("/login", include_in_schema=False)(self.login_view)
        self.app.post("/login", include_in_schema=False)(self.login)
        self.app.get("/reg", include_in_schema=False)(self.init_view)
        self.app.post("/reg", include_in_schema=False)(self.reg)
        # self.app.on_event('startup')(self.startup)
        super().gen_routes()
        self.gen_routes()
        return self.app

    # async def startup(self):
    #     self.app.redis = await Redis()
    #
    @staticmethod
    async def auth_middleware(request: Request):
        # path: str = request.scope["path"]
        # request.app.redis = await Redis()
        # redis: Redis = request.app.redis
        # todo: check only private paths
        # todo: check token validity, not only existance
        if not request.cookies.get("token"):
            raise HTTPException(
                status_code=status.HTTP_303_SEE_OTHER,
                headers={"Location": "/login", "set-cookie": "token=; expires=Thu, 01 Jan 1970 00:00:00 GMT"},
                detail="Not authenticated bruh",
            )

    def gen_routes(self):
        ar = APIRouter(dependencies=[Depends(self.auth_middleware)])
        for name, model in self.models.items():
            ar.add_api_route(
                "/" + name,
                partial(
                    self.index,
                ),
                name=name + " list",
            )
            (
                ar.add_api_route(
                    "/dt/" + name, self.dt, name=name + " datatables format", methods=["POST"], response_model=[]
                ),
            )
            (ar.add_api_route(f'/{name}/{"{oid}"}', self.edit, name="Edit view"),)
        self.app.include_router(ar, include_in_schema=False)

    async def login_view(
        self,
        request: Request,
        reason: Annotated[str | None, Cookie()] = None,
        username: Annotated[str | None, Cookie()] = None,
        password: Annotated[str | None, Cookie()] = None,
        remember_me: Annotated[str | None, Cookie()] = None,
    ) -> _TemplateResponse:
        response = self.templates.TemplateResponse(
            "providers/login/login.html",
            context={
                "request": request,
                "reason": reason,
                "username": username,
                "password": password,
            },
        )
        response.delete_cookie("reason")
        response.delete_cookie("username")
        response.delete_cookie("password")
        return response

    async def password_view(self, request: Request):
        return self.templates.TemplateResponse("providers/login/password.html", context={"request": request})

    async def init_view(self, request: Request):
        return self.templates.TemplateResponse("init.html", context={"request": request})

    async def login(
        self,
        username: Annotated[str, Form()],
        password: Annotated[str, Form()],
        remember_me: Annotated[str, Form()] = "",
    ):
        response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie("remember_me", remember_me)
        try:
            user_cred = await self.oauth.authenticate_user(username, password)
        except AuthException as e:
            response.set_cookie("reason", e.detail.name)
            response.set_cookie("username", username)
            response.set_cookie("password", password)
            return response
        if user_cred:
            # todo get permissions (scopes) from user.role in `scope`:str (separated by spaces)
            jwt = await self.oauth.login_for_access_token(
                OAuth2PasswordRequestForm(username=username, password=password, scope=" ".join(user_cred[0].scopes))
            )
            response.url = "/"
            response.headers["location"] = "/"
            response.set_cookie(
                "token",
                jwt.access_token,
                expires=self.oauth.EXPIRES,
                path="/",
                # httponly=True,
            )
            # await redis.set(constants.LOGIN_USER.format(token=token), admin.pk, ex=expire)
            return response
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    @staticmethod
    async def logout():
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie("token", path="/")
        # await self.redis.delete(constants.LOGIN_USER.format(token=token))
        return response

    async def reg(self, request: Request):
        obj = await request.form()
        if user := await self.oauth.reg_user(UserReg.model_validate(obj)):
            # todo get permissions (scopes) from user.role in `scope`:str (separated by spaces)
            scopes = ["my", "read"]
            jwt = await self.oauth.login_for_access_token(
                OAuth2PasswordRequestForm(username=user.username, password=obj["password"], scope=" ".join(scopes))
            )
            response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
            response.set_cookie(
                "token",
                jwt["access_token"],
                expires=self.oauth.EXPIRES,
                path="/",
                httponly=True,
            )
            # await redis.set(constants.LOGIN_USER.format(token=token), admin.pk, ex=expire)
            return response

    # INTERFACE
    async def dash(self, request: Request):
        return self.templates.TemplateResponse(
            "dashboard.html",
            {
                # 'model': 'Home',
                "subtitle": "Dashboard",
                "request": request,
            },
        )

    async def index(self, request: Request):
        model_name: str = request.scope["path"][1:]
        model: Type[Model] = self.models[model_name]
        pyd = model.pydIn()
        ff = ffrom_pyd(pyd)
        cols = [{"data": k} for k in model.pydListItem().model_fields]
        return self.templates.TemplateResponse(
            "index.html",
            {
                "model": pyd,
                "name": model_name,
                "fields": ff,
                "cols": cols,
                "subtitle": model._meta.table_description or model_name,
                "is_index_page": True,
                "request": request,
            },
        )

    async def edit(self, request: Request):
        mod_name = request.scope["path"][1:].split("/")[0]
        model: Type[Model] = self.models.get(mod_name)
        pyd = model.pydIn()
        ff = ffrom_pyd(pyd)
        oid = request.path_params["oid"]
        # await model.load_rel_options()
        obj: Model = await model.get(id=oid).prefetch_related(*model._meta.fetch_fields)
        bfms = {
            getattr(obj, k).remote_model: [ros.pk for ros in getattr(obj, k)] for k in model._meta.backward_fk_fields
        }
        # [await bfm.load_rel_options() for bfm in bfms]
        return self.templates.TemplateResponse(
            "edit.html",
            {
                "model": pyd,
                "name": mod_name,
                "fields": ff,
                "subtitle": model._meta.table_description,
                "request": request,
                "obj": obj,
                "bfms": bfms,  # todo: remove
            },
        )

    async def dt(self, request: Request):  # length: int = 100, start: int = 0
        model: Type[Model] = self.models.get(request.scope["path"][4:])
        meta = model._meta
        form = await request.body()
        form = parse_fs(form.decode())
        col_names = list(model.field_input_map().keys())
        sorts = [
            ("-" if srt["dir"] == "desc" else "")
            + (
                f"{col_name}__{meta.fields_map[col_name].related_model._name}"
                if (col_name := col_names[srt["column"]]) in meta.fk_fields
                else col_name
            )
            for srt in form["order"]
        ]
        data = await model.pagePyd(sorts, form["length"], form["start"], form["search"].get("value"))

        def render(obj: PydList):
            def rel(val: dict):
                return f'<a class="m-1 py-1 px-2 badge bg-blue-lt lead" href="/{val["type"]}/{val["id"]}">{val["repr"]}</a>'

            def check(val: list[BaseModel], key: str, fi: FieldInfo):
                if val is None:
                    return val
                if key == "id":
                    return rel({"type": model.__name__, "id": val, "repr": val})
                if key in meta.fetch_fields:
                    rm = meta.fields_map[key].related_model
                    if key in meta.fk_fields | meta.o2o_fields | meta.backward_o2o_fields:
                        val = {
                            "type": rm.__name__,
                            "id": val.id,
                            "repr": _repr(val.model_dump(mode="json"), getattr(rm, "_name")),
                        }
                        return rel(val)
                    elif key in meta.m2m_fields | meta.backward_fk_fields:
                        r = [
                            rel(
                                {  # todo: rm DRY
                                    "type": rm.__name__,
                                    "id": v.id,
                                    "repr": _repr(v.model_dump(mode="json"), getattr(rm, "_name")),
                                }
                            )
                            for v in val
                        ]
                        return " ".join(r)
                    else:
                        raise Exception("What type is fetch field?")
                return f"{val[:120]}.." if isinstance(val, str) and len(val) > 120 else val

            return {key: check(obj.__getattribute__(key), key, fi) for key, fi in obj.model_fields.items()}

        rows = [render(obj) for obj in data.data]
        return {"draw": int(form["draw"]), "recordsTotal": data.total, "recordsFiltered": data.filtered, "data": rows}
