from django.conf import settings

import datetime


# Log to a text file
def log(message):
    f = open(settings.BASE_DIR + "/python_log.txt", "a")
    timeStr = datetime.datetime.now().strftime("[%d/%m/%Y %H:%M:%S] > ")
    f.write(timeStr + message + "\n")
    f.close()


# Recursively get from a dictionary
def _get_if_exist(data, keys):
    if keys[0] in data:
        if len(keys) == 1:
            return data[keys[0]]
        else:
            return _get_if_exist(data[keys[0]], keys[1:])
    else:
        return None


# Recursively get from an object
def _get_attr(obj, attr):
    if isinstance(attr, str):
        attrs = attr.split(".")
    else:
        attrs = attr
    key = attrs[0]
    if hasattr(obj, key):
        if len(attrs) > 1:
            value = getattr(obj, key)
            if isinstance(value, list):
                return [_get_attr(item, attrs[1:]) for item in value]
            else:
                return _get_attr(value, attrs[1:])
        else:
            return getattr(obj, key)
    else:
        return None


# Expand all sublists within a list
def _expand_list(array):
    new_array = []
    for item in array:
        if isinstance(item, list):
            new_array += _expand_list(item)
        else:
            new_array.append(item)

    return new_array
