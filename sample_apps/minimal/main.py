from femto_admin import Admin
import models

adm = Admin(models, True)
app = adm.mount()
pass
