# X-Admin
###### Simplest fastest minimal ASGI CRUD Admin panel for Tortoise ORM models
It's generating fully native async auto  zero config one line app 
#### Requirements
- Python >= 3.11

### INSTALL
```bash
pip install x-admin
```

### Run your app
- Describe your db models with Tortoise ORM in `models.py` module
```python
from tortoise import fields
from tortoise_api import Model

class User(Model):
    id: int = fields.IntField(pk=True)
    name: str = fields.CharField(255, unique=True, null=False)
    posts: fields.ReverseRelation["Post"]

class Post(Model):
    id: int = fields.IntField(pk=True)
    text: str = fields.CharField(4095)
    user: User = fields.ForeignKeyField('models.User', related_name='posts')
    _name = 'text' # `_name` sets the attr for displaying related Post instace inside User (default='name')
```
- Write run script `main.py`: pass your models module in Api app:
```python
from x_admin import Admin
import models

app = Admin().start(models)
```
- Set `DB_URL` env variable in `.env` file
- Run it:
```bash
uvicorn main:app
```
Or you can just fork Completed minimal runnable example from [sample apps](https://github.com/mixartemev/x-admin/blob/master/sample_apps/minimal/).

#### And voila:
You have menu with all your models at root app route: http://127.0.0.1:8000


---
Made with ❤ on top of the [Starlette](https://www.starlette.io/), [TortoiseORM](https://tortoise.github.io/), [X-API](https://pypi.org/project/tortoise-api/).
