from tortoise.fields import Field, CharField, IntField, SmallIntField, BigIntField, DecimalField, FloatField,\
    TextField, BooleanField, DatetimeField, DateField, TimeField, JSONField, ForeignKeyRelation, OneToOneRelation, \
    ManyToManyRelation, ForeignKeyNullableRelation, OneToOneNullableRelation
from tortoise.fields.data import IntEnumFieldInstance, CharEnumFieldInstance
from tortoise.fields.relational import BackwardFKRelation, ForeignKeyFieldInstance, ManyToManyFieldInstance, \
    OneToOneFieldInstance, BackwardOneToOneRelation, RelationalField
from tortoise_api_model import PointField, PolygonField, RangeField, Model

from femto_admin.consts import FieldType

async def get_options(field: RelationalField):
    first = [('', 'Empty')] if field.null or isinstance(field, BackwardFKRelation) else []
    res = first + [(x.pk, x.repr()) for x in await field.related_model.all()]
    return res

async def _fields(obj: type[Model]) -> dict:
    def type2input(ft: type[Field]):
        dry = {
            'base_field': hasattr(ft, 'base_field') and {**type2input(ft.base_field)},
            'step': hasattr(ft, 'step') and ft.step,
            'labels': hasattr(ft, 'labels') and ft.labels
        }
        type2inputs: {Field: dict} = {
            CharField: {'input': FieldType.input.name},
            IntField: {'input': FieldType.input.name, 'type': 'number'},
            SmallIntField: {'input': FieldType.input.name, 'type': 'number'},
            BigIntField: {'input': FieldType.input.name, 'type': 'number'},
            DecimalField: {'input': FieldType.input.name, 'type': 'number', 'step': '0.01'},
            FloatField: {'input': FieldType.input.name, 'type': 'number', 'step': '0.001'},
            TextField: {'input': FieldType.textarea.name, 'rows': '2'},
            BooleanField: {'input': FieldType.checkbox.name},
            DatetimeField: {'input': FieldType.input.name, 'type': 'datetime'},
            DateField: {'input': FieldType.input.name, 'type': 'date'},
            TimeField: {'input': FieldType.input.name, 'type': 'time'},
            JSONField: {'input': FieldType.input.name},
            IntEnumFieldInstance: {'input': FieldType.select.name},
            CharEnumFieldInstance: {'input': FieldType.select.name},
            ForeignKeyFieldInstance: {'input': FieldType.select.name},
            OneToOneFieldInstance: {'input': FieldType.select.name},
            ManyToManyFieldInstance: {'input': FieldType.select.name, 'multiple': True},
            ForeignKeyRelation: {'input': FieldType.select.name, 'multiple': True},
            OneToOneRelation: {'input': FieldType.select.name},
            BackwardOneToOneRelation: {'input': FieldType.select.name},
            ManyToManyRelation: {'input': FieldType.select.name, 'multiple': True},
            ForeignKeyNullableRelation: {'input': FieldType.select.name, 'multiple': True},
            BackwardFKRelation: {'input': FieldType.select.name, 'multiple': False},
            OneToOneNullableRelation: {'input': FieldType.select.name},
            PointField: {'input': FieldType.collection.name, **dry},
            PolygonField: {'input': FieldType.list.name, **dry},
            RangeField: {'input': FieldType.collection.name, **dry},
        }
        return type2inputs[ft]

    async def field2input(field: Field):
        attrs: dict = {'required': not field.null}
        if isinstance(field, CharEnumFieldInstance):
            attrs.update({'options': ((en.name, en.value) for en in field.enum_type)})
        elif isinstance(field, IntEnumFieldInstance):
            attrs.update({'options': ((en.value, en.name.replace('_', ' ').title()) for en in field.enum_type)})
        elif isinstance(field, RelationalField):
            attrs.update({'options': await get_options(field), 'source_field': field.source_field})
        elif field.generated or ('auto_now' in field.__dict__ and (field.auto_now or field.auto_now_add)):
            attrs.update({'auto': True})
        return {**type2input(type(field)), **attrs}

    return {key: await field2input(field) for key, field in obj._meta.fields_map.items() if not key.endswith('_id')}

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
