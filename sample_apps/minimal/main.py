from femto_admin import Admin
import models

app = Admin(True).start(models)
