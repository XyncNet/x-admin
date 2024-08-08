from tortoise import fields
from tortoise_api_model.model import User as ApiUser, TsModel


class User(ApiUser):
    posts: fields.ReverseRelation["Post"]


class Post(TsModel):
    id: int = fields.IntField(pk=True)
    text: str = fields.CharField(4095)
    published: bool = fields.BooleanField()
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField('models.User', related_name='posts')
    _name = {'text'}
