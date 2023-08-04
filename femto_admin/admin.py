from datetime import datetime
from os.path import exists

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
    def __init__(self, debug: bool = False, title: str = "Admin", static_dir: str = None, logo: str|bool = None, dash_func: callable = None):
        """
        Parameters:
            title: Admin title.
            # auth_provider: Authentication Provider
        """
        super().__init__(debug)
        self.title = title
        # self._views: List[BaseView] = []
        self.routes: [Route | Mount] = [
            Route('/', dash_func or self.dash),
            Mount('/api', routes=self.routes), # mount api routes to /api/*
            Mount('/statics', StaticFiles(packages=["femto_admin"]), name='public'),
            Route('/favicon.ico', lambda r: RedirectResponse('./statics/placeholders/favicon.ico', status_code=301), methods=['GET']),
            Route('/{model}', self.index),
            Route('/dt/{model}', self.dt),
            Route('/{model}/{oid}', self.edit),
        ]
        self.routes[1].routes.pop(1)  # remove apt/favicon.ico route
        # globals
        templates = Jinja2Templates("templates")
        if static_dir:
            self.routes.insert(2, Mount('/'+static_dir, StaticFiles(directory=static_dir), name='my-public'))
            if logo is not None:
                templates.env.globals["logo"] = logo
            if exists(f'./{static_dir}/favicon.ico'):
                self.routes.pop(4)
                self.routes.insert(4, Route('/favicon.ico', lambda r: RedirectResponse(f'./{static_dir}/favicon.ico', status_code=301), methods=['GET']),)
        templates.env.loader = ChoiceLoader(
            [
                FileSystemLoader("templates"),
                PackageLoader("femto_admin", "templates"),
            ]
        )
        templates.env.globals["title"] = self.title
        templates.env.globals["meta"] = {'year': datetime.now().year, 'ver': femto_admin.__version__}
        templates.env.globals["minify"] = '' if debug else 'min.'
        self.templates = templates

    def start(self, models_module):
        app = super().start(models_module)
        self.templates.env.globals["models"] = self.models
        return app

    # INTERFACE
    async def dash(self, request: Request):
        return self.templates.TemplateResponse("dashboard.html", {
            # 'model': 'Home',
            'subtitle': 'Dashboard',
            'request': request,
        })

    async def index(self, request: Request):
        model: type[Model] = self._get_model(request)
        await model.load_rel_options()
        return self.templates.TemplateResponse("index.html", {
            'model': model,
            'subtitle': model._meta.table_description,
            'request': request,
        })

    async def edit(self, request: Request):
        model: type[Model] = self._get_model(request)
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

    async def dt(self, request: Request):
        def render(dct: dict):
            def rel(val: dict):
                return f'<a class="m-1 py-1 px-2 badge bg-blue-lt lead" href="/{val["type"]}/{val["id"]}">{val["repr"]}</a>'
            def check(val):
                if isinstance(val, dict) and 'repr' in val.keys():
                    return rel(val)
                elif isinstance(val, list) and val and isinstance(val[0], dict) and 'repr' in val[0].keys():
                    return ' '.join(rel(v) for v in val)
                return val

            return [check(val) for key, val in dct.items()]

        model: type[Model] = self._get_model(request)
        objects: [Model] = await model.all().prefetch_related(*model._meta.fetch_fields)
        data = [render(jsonify(obj)) for obj in objects]
        return JSONResponse({'data': data})
