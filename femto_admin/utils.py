from tortoise import Model
from tortoise.fields.data import IntEnumFieldInstance, CharEnumField
from tortoise.fields.relational import BackwardFKRelation, ForeignKeyFieldInstance, ManyToManyFieldInstance, \
    OneToOneFieldInstance, BackwardOneToOneRelation
from tortoise.fields import Field, CharField, IntField, SmallIntField, BigIntField, DecimalField as DecField, \
    FloatField as FlotField, TextField, BooleanField as BoolField, DatetimeField, DateField as DatField, \
    TimeField as TimField, JSONField as JsonField, ForeignKeyRelation, OneToOneRelation, \
    ManyToManyRelation, ForeignKeyNullableRelation, OneToOneNullableRelation
from tortoise_api_model import PointField, PolygonField

from femto_admin.consts import FieldType


def _fields(obj: type[Model]) -> dict:
    fields = {}
    types: {Field: FieldType} = {
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
        OneToOneFieldInstance: FieldType.one,
        ManyToManyFieldInstance: FieldType.many,
        ForeignKeyRelation: FieldType.many,
        OneToOneRelation: FieldType.one,
        BackwardOneToOneRelation: FieldType.one,
        ManyToManyRelation: FieldType.many,
        ForeignKeyNullableRelation: FieldType.many,
        BackwardFKRelation: FieldType.many,
        OneToOneNullableRelation: FieldType.one,
        PointField: FieldType.point,
        PolygonField: FieldType.polygon,
    }
    templates: {FieldType: str} = {
        FieldType.str: 'input',
        FieldType.int: 'input',
        FieldType.float: 'input',
        FieldType.txt: 'textarea',
        FieldType.bool: 'switch',
        FieldType.one: 'select',
        FieldType.many: 'select',
        FieldType.point: 'point',
        FieldType.polygon: 'polygon',
    }
    for key, field in obj._meta.fields_map.items():
        kwa = {'type': types[type(field)], 'required': not field.null}
        if isinstance(field, IntEnumFieldInstance):
            kwa.update({'enum': field.enum_type})
        elif isinstance(field, BackwardFKRelation):
            kwa.update({'back': True, 'required': False})
        if field.generated or ('auto_now' in field.__dict__ and (field.auto_now or field.auto_now_add)):
            kwa.update({'auto': True})
        fields[key] = {**kwa, 'template': templates[kwa['type']]}
    return fields

    # def get_fields(model: type[Model], is_display: bool = True):
    #     ret = []
    #     pk_column = model._meta.db_pk_column
    #     for field in self.fields or model._meta.fields:
    #         if isinstance(field, str):
    #             if field == pk_column:
    #                 continue
    #             field = self._get_display_input_field(field)
    #         if isinstance(field, ComputeField) and not is_display:
    #             continue
    #         elif isinstance(field, Field):
    #             if field.name == pk_column:
    #                 continue
    #             if (is_display and isinstance(field.display, displays.InputOnly)) or (
    #                 not is_display and isinstance(field.input, inputs.DisplayOnly)
    #             ):
    #                 continue
    #         if (
    #             field.name in model._meta.fetch_fields
    #             and field.name not in model._meta.fk_fields | model._meta.m2m_fields
    #         ):
    #             continue
    #         ret.append(field)
    #     ret.insert(0, self._get_display_input_field(pk_column))
    #     return ret