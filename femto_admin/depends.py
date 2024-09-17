from fastapi import HTTPException
from fastapi.params import Path
from starlette.requests import Request
from starlette.status import HTTP_401_UNAUTHORIZED
from tortoise import Tortoise


def get_model(resource: str | None = Path(...)):
    if not resource:
        return
    for app, models in Tortoise.apps.items():
        models = {key.lower(): val for key, val in models.items()}
        model = models.get(resource)
        if model:
            return model


def get_redis(request: Request):
    return request.app.redis


def get_current_admin(request: Request):
    admin = request.state.admin
    if not admin:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED)
    return admin
