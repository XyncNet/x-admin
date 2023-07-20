from femto_admin import Admin
from sample_apps.minimal import models

app = Admin().start(models)
