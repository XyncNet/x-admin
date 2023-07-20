from jinja2 import ChoiceLoader, FileSystemLoader, PackageLoader
from starlette.requests import Request
from starlette.responses import RedirectResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from tortoise_api.api import Api, Model
from tortoise_api.util import jsonify


class Admin(Api):
    def __init__(self, debug: bool = False, title: str = "Admin"):
        """
        Parameters:
            title: Admin title.
            # auth_provider: Authentication Provider
        """
        super().__init__(debug)
        self.title = title
        # self._views: List[BaseView] = []
        self.routes: [Route | Mount] = [
            Mount('/static', StaticFiles(packages=["femto_admin"]), name='public'),
            Mount('/api', routes=self.routes), # mount api routes to /api/*
            Route("/favicon.ico", lambda r: RedirectResponse('./static/placeholders/favicon.ico', status_code=301), methods=['GET']),
            Route('/{model}', self.index, methods=['GET']),
            Route('/dt/{model}', self.dt, methods=['GET']),
            Route('/', self.dash, methods=['GET']),
        ]
        self.routes[1].routes.pop(1)  # remove apt/favicon.ico route
        # globals
        templates = Jinja2Templates("templates")
        templates.env.loader = ChoiceLoader(
            [
                FileSystemLoader("templates"),
                PackageLoader("femto_admin", "templates"),
            ]
        )
        templates.env.globals["title"] = self.title
        templates.env.globals["minify"] = '' if debug else 'min.'
        self.templates = templates

    def start(self, models_module):
        app = super().start(models_module)
        self.templates.env.globals["models"] = self.models
        return app

    # INTERFACE
    async def dash(self, request: Request):
        return self.templates.TemplateResponse("dashboard.html", {
            'title': 'Home',
            'subtitle': 'Dashboard',
            'request': request,
        })

    async def index(self, request: Request):
        model: Model = self._get_model(request)
        return self.templates.TemplateResponse("table.html", {
            'title': model.__name__,
            'subtitle': model._meta.table_description,
            'request': request,
            'fields': {k: v for k, v in model._meta.fields_map.items() if not k.endswith('_id')}
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

        model: Model = self._get_model(request)
        objects: [Model] = await model.all().prefetch_related(*model._meta.fetch_fields)
        data = [render(jsonify(obj)) for obj in objects]
        return JSONResponse({'data': data})
