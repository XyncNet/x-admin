from datetime import datetime
from os import path
from types import ModuleType
from fastapi import FastAPI, APIRouter, Depends
from fastapi.responses import ORJSONResponse
from fastapi.routing import APIRoute
from jinja2 import ChoiceLoader, FileSystemLoader, PackageLoader
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from tortoise_api.api import Api
from tortoise_api.oauth import get_current_active_user
from tortoise_api.util import jsonify
from tortoise_api_model import Model

import femto_admin


class Admin(Api):
    app: FastAPI

    def __init__(
        self,
        models_module: ModuleType,
        debug: bool = False,
        title: str = "Admin",
        static_dir: str = None,
        logo: str | bool = None,
        dash_func: callable = None,
    ):
        """
        Parameters:
            title: Admin title.
            # auth_provider: Authentication Provider
        """
        # globals
        templates = Jinja2Templates("templates")
        routes: [Route | Mount] = [
            APIRoute('/', dash_func or self.dash, name="Dashboard"),
            APIRoute('/{model}/{oid}', self.edit, name='Edit view'),
            APIRoute('/{model}', self.index, name='List view'),
        ]

        super().__init__(models_module, debug, title)
        self.app.add_route('/login', self.login)
        self.app.mount('/statics', StaticFiles(packages=["femto_admin"]), name='public'),
        self.app.include_router(APIRouter(routes=routes), prefix='/admin', tags=['admin'], include_in_schema=False)
        if static_dir:
            self.app.mount('/' + static_dir, StaticFiles(directory=static_dir), name='my-public'),
            if logo is not None:
                templates.env.globals["logo"] = logo
        if path.exists(favicon_path := f'./{static_dir or "statics/placeholders"}/favicon.ico'):
            self.app.add_route('/favicon.ico', lambda r: RedirectResponse(favicon_path, status_code=301))

        self.app.add_api_route('/dt/{model}', self.dt, name='Datatables format', tags=['api']) # , dependencies=[Depends(get_current_active_user)]

        # self._views: List[BaseView] = []

        templates.env.loader = ChoiceLoader([FileSystemLoader("templates"), PackageLoader("femto_admin", "templates")])
        templates.env.globals["title"] = title
        templates.env.globals["meta"] = {'year': datetime.now().year, 'ver': femto_admin.__version__}
        templates.env.globals["minify"] = '' if debug else 'min.'
        self.templates = templates
        self.templates.env.globals["models"] = self.models

    # INTERFACE
    async def login(self, request: Request):
        return self.templates.TemplateResponse("dashboard.html", {
            # 'model': 'Home',
            'subtitle': 'Dashboard',
            'request': request,
        })

    async def dash(self, request: Request):
        return self.templates.TemplateResponse("dashboard.html", {
            # 'model': 'Home',
            'subtitle': 'Dashboard',
            'request': request,
        })

    async def index(self, request: Request, model: str):
        model: type[Model] = self.models.get(model)
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

    async def dt(self, model: str, limit: int = 50, page: int = 1):
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

            return [check(val, key == 'id') for key, val in (await jsonify(obj)).items()]

        model: type[Model] = self.models.get(model)
        objects: [Model] = await model.all().prefetch_related(*model._meta.fetch_fields).limit(limit).offset(limit*(page-1))

        data = [await render(obj) for obj in objects]
        return ORJSONResponse({'data': data})
