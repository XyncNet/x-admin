from fastapi import FastAPI


class Provider:
    name = "provider"

    def register(self, app: FastAPI):
        setattr(app, self.name, self)
