from femto_admin import Admin
import models

app = Admin(models, True).get_app()
