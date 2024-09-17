from urllib.parse import unquote


def parse_qs(qs: str) -> dict:
    pairs = parse_qsl(qs)
    return {key: val for key, val in pairs}


def parse_qsl(qs: str) -> list[tuple[str, str]]:
    r = []
    query_args = qs.split("&") if qs else []
    for name_value in query_args:
        if not name_value:
            continue
        nv = name_value.split("=", 1)
        if len(nv) != 2:
            continue
        if len(nv[1]):
            name = nv[0].replace("+", " ")
            name = unquote(name, encoding="utf-8", errors="replace")
            value = nv[1].replace("+", " ")
            value = unquote(value, encoding="utf-8", errors="replace")
            r.append((name, value))
    return r


def parse_fs(fs: str) -> dict:
    def recursive_update(d, keys, val):
        key = keys[0]
        if key.isdigit():
            key = int(key)

        if len(keys) > 1:
            tmp = [] if keys[1].isdigit() else {}
            if isinstance(d, dict) and key not in d:
                d[key] = tmp
            elif isinstance(d, list) and len(d) <= key:
                d.append(tmp)
            recursive_update(d[key], keys[1:], val)
        else:
            d[key] = val

    result = {}
    for ky, v in parse_qsl(fs):
        kys = ky.replace("]", "").split("[")
        v = (float(v) if "." in v else int(v)) if v.isdecimal() else v
        recursive_update(result, kys, v)

    return result
