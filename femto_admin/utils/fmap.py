import datetime
from enum import IntEnum
from types import UnionType, GenericAlias
from typing import get_args

from tortoise.contrib.pydantic import PydanticModel


class FieldType(IntEnum):
    input = 1
    checkbox = 2
    select = 3
    textarea = 4
    collection = 5
    list = 6
    json = 7


type2inputs: {type: dict} = {
    str: {'input': FieldType.input.name},
    int: {'input': FieldType.input.name, 'type': 'number'},
    # decimal: {'input': FieldType.input.name, 'type': 'number', 'step': '0.01'},
    float: {'input': FieldType.input.name, 'type': 'number', 'step': '0.001'},
    # TextField: {'input': FieldType.textarea.name, 'rows': '2'},
    bool: {'input': FieldType.checkbox.name},
    datetime.datetime: {'input': FieldType.input.name, 'type': 'datetime-local'},
    datetime.date: {'input': FieldType.input.name, 'type': 'date'},
    datetime.time: {'input': FieldType.input.name, 'type': 'time'},
    IntEnum: {'input': FieldType.select.name},
    # ForeignKeyFieldInstance: {'input': FieldType.select.name},
    list: {'input': FieldType.select.name, 'multiple': True},
    dict: {'input': FieldType.json.name},
    set: {'input': FieldType.select.name, 'multiple': True},
}


def ffrom_pyd(pyd: type[PydanticModel]) -> dict:
    def typ2inp(typ, key: str = None, req: bool = True) -> dict:
        if key.endswith('_id') and typ is int:
            inp = {'input': FieldType.select.name, 'options': {}, 'source_field': key.replace('_id', '').capitalize()}
        elif not (inp := type2inputs.get(typ)):
            if isinstance(typ, UnionType) or (hasattr(typ, '_name') and typ._name == 'Optional'):
                typ, req = get_args(typ)
            if not (inp := type2inputs.get(typ)):
                if issubclass(typ, IntEnum):
                    inp = type2inputs[IntEnum]
                    inp.update({'options': {t.value: t.name for t in typ}})
                elif type(typ) is GenericAlias:
                    inp = type2inputs.get(typ.__origin__)
                    if typ.__origin__ == list:
                        inp.update({'options': {}})  # todo fill options for multiple
        inp.update({'req': bool(req)})
        return inp

    return {key: {**typ2inp(f.annotation, key), 'name': f.title, 'validators': f.metadata} for key, f in pyd.model_fields.items()}
