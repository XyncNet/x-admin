from datetime import datetime
from os import path
from types import ModuleType
from fastapi import FastAPI, APIRouter
from fastapi.routing import APIRoute
from jinja2 import ChoiceLoader, FileSystemLoader, PackageLoader
from starlette.requests import Request
from starlette.responses import RedirectResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from tortoise_api.api import Api
from tortoise_api.util import jsonify
from tortoise_api_model import Model

import femto_admin


class Admin(Api):
    app: FastAPI
    def __init__(self, models_module: ModuleType, debug: bool = False, title: str = "Admin", static_dir: str = None, logo: str|bool = None, dash_func: callable = None):
        """
        Parameters:
            title: Admin title.
            # auth_provider: Authentication Provider
        """
        self.title = title
        # self._views: List[BaseView] = []
        super().__init__(models_module, debug)
        # globals
        templates = Jinja2Templates("templates")
        routes: [Route | Mount] = [
            Route('/', dash_func or self.dash),
            APIRoute('/list/{model}', self.index),
            APIRoute('/dt/{model}', self.dt),
            APIRoute('/edit/{model}/{oid}', self.edit),
            Route('/favicon.ico', lambda r: RedirectResponse('./statics/placeholders/favicon.ico', status_code=301)),
        ]
        if static_dir:
            routes.append(Mount('/'+static_dir, StaticFiles(directory=static_dir), name='my-public'))
            if logo is not None:
                templates.env.globals["logo"] = logo
        if path.exists(favicon_path := f'./{static_dir or "statics/placeholders"}/favicon.ico'):
            routes.append(Route('/favicon.ico', lambda r: RedirectResponse(favicon_path, status_code=301)))
        templates.env.loader = ChoiceLoader([FileSystemLoader("templates"), PackageLoader("femto_admin", "templates")])
        templates.env.globals["title"] = self.title
        templates.env.globals["meta"] = {'year': datetime.now().year, 'ver': femto_admin.__version__}
        templates.env.globals["minify"] = '' if debug else 'min.'
        self.templates = templates
        self.app.mount('/statics', StaticFiles(packages=["femto_admin"]), name='public'),
        self.app.include_router(APIRouter(routes=routes), tags=['admin'])
        self.templates.env.globals["models"] = self.models


    # INTERFACE
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

    async def dt(self, request: Request, model: str):
        async def render(obj: Model):
            def rel(val: dict):
                return f'<a class="m-1 py-1 px-2 badge bg-blue-lt lead" href="/edit/{val["type"]}/{val["id"]}">{val["repr"]}</a>'
            def check(val, is_id: bool):
                if isinstance(val, dict) and 'repr' in val.keys():
                    return rel(val)
                elif is_id:
                    return rel({'type': obj.__class__.__name__, 'id': val, 'repr': val})
                elif isinstance(val, list) and val and isinstance(val[0], dict) and 'repr' in val[0].keys():
                    return ' '.join(rel(v) for v in val)
                return f'{val[:100]}..' if isinstance(val, str) and len(val)>100 else val

            return [check(val, key=='id') for key, val in (await jsonify(obj)).items()]

        model: type[Model] = self.models.get(model)
        objects: [Model] = await model.all().prefetch_related(*model._meta.fetch_fields)

        data = [await render(obj) for obj in objects]
        return JSONResponse({'data': data})
