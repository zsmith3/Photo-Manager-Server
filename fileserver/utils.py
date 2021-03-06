import datetime
import os

from django.conf import settings

# Logging setup
if not os.path.isdir(f"{settings.BASE_DIR}/logs/"):
    os.makedirs(f"{settings.BASE_DIR}/logs/")
log_file_no = 1
while True:
    if not os.path.isfile(f"{settings.BASE_DIR}/logs/python_log_{log_file_no:03d}.txt"):
        log_file_no -= 1
        break
    log_file_no += 1
if log_file_no == 0:
    log_file_no = 1
    open(f"{settings.BASE_DIR}/logs/python_log_{log_file_no:03d}.txt", "w").close()
with open(f"{settings.BASE_DIR}/logs/python_log_{log_file_no:03d}.txt") as log_f:
    if len(list(log_f)) >= settings.PYTHON_LOG_MAX_LINES:
        log_file_no += 1
    log_f.close()


def log(message):
    """ Log a message to the text file log

    Parameters
    ----------
    message : str
        The message to log
    """

    global log_file_no

    log_f = open(f"{settings.BASE_DIR}/logs/python_log_{log_file_no:03d}.txt", encoding="utf8")

    if len(list(log_f)) >= settings.PYTHON_LOG_MAX_LINES:
        log_file_no += 1

    log_f.close()
    log_f = open(f"{settings.BASE_DIR}/logs/python_log_{log_file_no:03d}.txt", "a", encoding="utf8")

    timeStr = datetime.datetime.now().strftime("[%d/%m/%Y %H:%M:%S] > ")
    log_f.write(timeStr + message + "\n")
    log_f.close()


def read_logs(start_time=None):
    """ Read all log messages after a certain time from the latest text file log

    Parameters
    ----------
    start_time : datetime
        The earliest timestamp from which to read logs

    Returns
    -------
    string, datetime
        The relevant logs (as a single string), and the timestamp of the most recent line
    """

    global log_file_no

    log_f = open(f"{settings.BASE_DIR}/logs/python_log_{log_file_no:03d}.txt", encoding="utf8")
    lines = list(log_f)
    log_f.close()

    if start_time is not None:
        done = False
        for i in range(len(lines)):
            try:
                if datetime.datetime.strptime(lines[i][:21], "[%d/%m/%Y %H:%M:%S]") > start_time:
                    lines = lines[i:]
                    done = True
                    break
            except Exception:
                pass
        if not done:
            lines = []

    end_time = datetime.datetime(1970, 1, 1)
    for line in lines:
        try:
            end_time = max(end_time, datetime.datetime.strptime(line[:21], "[%d/%m/%Y %H:%M:%S]"))
        except Exception:
            pass

    return "".join(lines), end_time


def get_if_exist(data, keys):
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
            return get_if_exist(data[keys[0]], keys[1:])
    else:
        return None


def get_attr(obj, attrs):
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
                return [get_attr(item, attrs[1:]) for item in value]
            else:
                return get_attr(value, attrs[1:])
        else:
            return getattr(obj, key)
    else:
        return None


def expand_list(array):
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
            new_array += expand_list(item)
        else:
            new_array.append(item)

    return new_array


def get_full_set(items, func=None):
    """ Flatten and unique/sort a list of iterables

    Sorted using unique_and_sort.

    Example Usage: Given a list of search queries,
    and a function to fetch all models matching each query,
    return a unique, sorted list of all models matching any query.

    Parameters
    ----------
    items : list
        A list of iterables, or of other items (see func)
    func : function (any -> iterable)
        A function to convert each item to an iterable

    Returns
    -------
    list
        A sorted list of unique values from within each iterable
    """

    return unique_and_sort(sum((list(item if func is None else func(item)) for item in items), []))


def unique_and_sort(full_list):
    """ Remove duplicates from a list, and sort items based on how many times they appear

    Items appearing more frequently in the original list will appear earlier in the returned list.

    Parameters
    ----------
    full_list : list
        A list of items, each with an `id` attribute

    Returns
    -------
    list
        A unique, sorted list of items
    """

    scores = {item.id: 0 for item in full_list}
    unique_list = []
    for item in full_list:
        if scores[item.id] == 0:
            unique_list.append(item)
        scores[item.id] += 1

    return sorted(unique_list, key=lambda item: -scores[item.id])
