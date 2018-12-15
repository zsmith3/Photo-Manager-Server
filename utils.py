from django.conf import settings

import datetime


def log(message):
    """ Log a message to the text file log

    Parameters
    ----------
    message : str
        The message to log
    """

    f = open(settings.BASE_DIR + "/python_log.txt", "a")
    timeStr = datetime.datetime.now().strftime("[%d/%m/%Y %H:%M:%S] > ")
    f.write(timeStr + message + "\n")
    f.close()


def _get_if_exist(data, keys):
    """ Recursively get a value from a nested dictionary

    Parameters
    ----------
    data : dict
        The (nested) dictionary
    keys : list
        The list of keys to fetch

    Returns
    -------
    any or None
        The value at data[keys[0]][keys[1]] etc. or None if a key is not found.
    """

    if keys[0] in data:
        if len(keys) == 1:
            return data[keys[0]]
        else:
            return _get_if_exist(data[keys[0]], keys[1:])
    else:
        return None


def _get_attr(obj, attrs):
    """ Recursively get a value from a nested set of objects

    Parameters
    ----------
    obj : any
        The root object
    attrs : str or list
        Either a list of attribute names or a string
        of attribute names joined by dots.

    Returns
    -------
    any or None
        The value from getattr(getattr(obj, attr[0]), attr[1]) etc. or None if an attribute is not found.
    """

    if isinstance(attrs, str):
        attrs = attrs.split(".")

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


def _expand_list(array):
    """ Recursively flatten a nested list

    Any lists found are flattened and added to output,
    any other values are just appended to output.

    Parameters
    ----------
    array : list
        The (nested) input list

    Returns
    -------
    list
        A flat list of values
    """

    new_array = []
    for item in array:
        if isinstance(item, list):
            new_array += _expand_list(item)
        else:
            new_array.append(item)

    return new_array
