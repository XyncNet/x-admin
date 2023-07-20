from tortoise import Model
from tortoise.fields.data import IntEnumFieldInstance, CharEnumField
from tortoise.fields.relational import BackwardFKRelation, ForeignKeyFieldInstance, ManyToManyFieldInstance
from tortoise.fields import Field, CharField, IntField, SmallIntField, BigIntField, DecimalField as DecField, \
    FloatField as FlotField, TextField, BooleanField as BoolField, DatetimeField, DateField as DatField, \
    TimeField as TimField, JSONField as JsonField, OneToOneField, ForeignKeyRelation, OneToOneRelation, \
    ManyToManyRelation, ForeignKeyNullableRelation, OneToOneNullableRelation

from femto_admin.consts import FieldType


def _fields(obj: Model) -> dict:
    fields = {}
    field_types: {Field: FieldType} = {
        CharField: FieldType.str,
        IntField: FieldType.int,
        SmallIntField: FieldType.int,
        BigIntField: FieldType.int,
        DecField: FieldType.float,
        FlotField: FieldType.float,
        TextField: FieldType.txt,
        BoolField: FieldType.bool,
        DatetimeField: FieldType.int,
        DatField: FieldType.int,
        TimField: FieldType.int,
        JsonField: FieldType.int,
        IntEnumFieldInstance: FieldType.int,
        CharEnumField: FieldType.int,
        ForeignKeyFieldInstance: FieldType.one,
        OneToOneField: FieldType.one,
        ManyToManyFieldInstance: FieldType.many,
        ForeignKeyRelation: FieldType.many,
        OneToOneRelation: FieldType.one,
        ManyToManyRelation: FieldType.many,
        ForeignKeyNullableRelation: FieldType.many,
        BackwardFKRelation: FieldType.many,
        OneToOneNullableRelation: FieldType.one,
    }
    for key, field in obj._meta.fields_map.items():
        kwa = {'type': field_types[type(field)], 'required': not field.null}
        if isinstance(field, IntEnumFieldInstance):
            kwa.update({'enum': field.enum_type})
        elif isinstance(field, BackwardFKRelation):
            kwa.update({'back': True, 'required': False})
        if field.generated: # 'auto_now' in field.__dict__ and (field.auto_now or field.auto_now_add):
            kwa.update({'auto': True})
        fields[key] = kwa

    return fields