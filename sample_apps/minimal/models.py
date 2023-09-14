from tortoise import fields
from tortoise_api_model import Model
from tortoise_api_model.model import User as BaseUser, TsModel


class User(BaseUser):
    posts: fields.ReverseRelation["Post"]

class Post(TsModel):
    id: int = fields.IntField(pk=True)
    text: str = fields.CharField(4095)
    published: bool = fields.BooleanField()
    user: User = fields.ForeignKeyField('models.User', related_name='posts')
    _name = 'text'
