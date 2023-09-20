from fastapi import FastAPI


class Provider:
    name = "provider"

    async def register(self, app: FastAPI):
        setattr(app, self.name, self)
