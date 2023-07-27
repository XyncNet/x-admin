from enum import IntEnum

class FieldType(IntEnum):
    str = 1
    txt = 2
    int = 3
    float = 4
    bool = 5
    dict = 7
    date = 8
    time = 9
    dt = 10
    one = 11
    many = 12
    point = 13
    polygon = 14
