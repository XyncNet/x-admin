import datetime
from enum import IntEnum
from types import UnionType
from typing import get_args

from tortoise.contrib.pydantic import PydanticModel


class FieldType(IntEnum):
    input = 1
    checkbox = 2
    select = 3
    textarea = 4
    collection = 5
    list = 6


type2inputs: {type: dict} = {
    str: {'input': FieldType.input.name},
    int: {'input': FieldType.input.name, 'type': 'number'},
    # decimal: {'input': FieldType.input.name, 'type': 'number', 'step': '0.01'},
    float: {'input': FieldType.input.name, 'type': 'number', 'step': '0.001'},
    # TextField: {'input': FieldType.textarea.name, 'rows': '2'},
    bool: {'input': FieldType.checkbox.name},
    datetime.datetime: {'input': FieldType.input.name, 'type': 'datetime'},
    # DateField: {'input': FieldType.input.name, 'type': 'date'},
    # TimeField: {'input': FieldType.input.name, 'type': 'time'},
    IntEnum: {'input': FieldType.select.name},
    # ForeignKeyFieldInstance: {'input': FieldType.select.name},
    list: {'input': FieldType.select.name, 'multiple': True},
    set: {'input': FieldType.select.name, 'multiple': True},
}


def ffrom_pyd(pyd: type[PydanticModel]) -> dict:
    def typ2inp(typ, req: bool = True) -> dict:
        if not (inp := type2inputs.get(typ)):
            if isinstance(typ, UnionType) or (hasattr(typ, '_name') and typ._name == 'Optional'):
                typ, req = get_args(typ)
            if not (inp := type2inputs.get(typ)):
                if issubclass(typ, IntEnum):
                    inp = type2inputs[IntEnum]
                    inp.update({'options': {t.value: t.name for t in typ}})
        inp.update({'req': bool(req)})
        return inp

    return {key: {**typ2inp(f.annotation), 'name': f.title, 'validators': f.metadata} for key, f in pyd.model_fields.items()}
