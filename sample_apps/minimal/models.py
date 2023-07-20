from tortoise import fields
from tortoise_api_model import Model

class User(Model):
    id: int = fields.IntField(pk=True)
    name: str = fields.CharField(255, unique=True, null=False)
    posts: fields.ReverseRelation["Post"]

class Post(Model):
    id: int = fields.IntField(pk=True)
    text: str = fields.CharField(4095)
    user: User = fields.ForeignKeyField('models.User', related_name='posts')
    _name = 'text'
