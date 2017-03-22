import itertools
import os
import sys
import inspect

import numpy as np
import collections
import ast


def get_arguments(insp_classes):
    """
    Get args and kwargs of the class methods

    Parameters
    ----------
    insp_classes : list
        Classes to inspect
    """
    mapped_classes = []
    for insp_class in insp_classes:
        try:
            x = inspect.getargspec(insp_class.__init__)
            params = x[0]
            if x[3]:
                default_values = list(x[3])
            else:
                default_values = []

        except TypeError as e:
            params = []
            default_values = []

        if default_values:
            n = -len(default_values)
        else:
            n = None
        mandatory_params = params[1:n]
        default_params = params[n:]
        mapped_classes.append({"name": insp_class.__name__,
                               "mandatory_params": mandatory_params,
                               "default_params": default_params,
                               "default_values": default_values})
    return mapped_classes


def clean_path(path):
    """Get name  from path as last item without dot"""
    cleaned_name = path[path.rfind("/") + 1:]

    if "." in cleaned_name:
        cleaned_name = cleaned_name[:cleaned_name.rfind(".")]

    return cleaned_name


def check_depth(a, deep_level, ifnotraise=True):
    """Check if input list has desired level of nested lists"""
    MAX_ITER = 10
    lev = 0
    while lev < MAX_ITER:
        try:
            a = a[0]
            lev += 1
        except:
            break
    if not lev == deep_level:
        if ifnotraise:
            raise Exception(
                "Wrong input nested level. Excepted %i, got %i\n %s" % (deep_level,
                                                                        lev, a))
        else:
            return False
    return True


def sub_dict_in_dict(sub_dict, dict_list, remove_keys=[]):
    """
    Parameters
    ----------
    sub_dict : dict
        Single dictionary

    dict_list : list
        List of dictionaries

    remove_keys : list
        List of keys which are removed from dictionaries

    Example
    ------
    subDictInDict({"x":1},[{"x":2,"y":5,..},{"x":1,"z":2,..}, ..} --> [{"x":1, "z":2, ..},..]

    In this example list of dictionaries which contain x = 1 is returned

    Returns
    -------
    list
        List of dictionaries which contain condition in sub_dict
    """
    assert len(sub_dict.keys()) == 1

    key = sub_dict.keys()[0]
    matched_dicts = []
    for one_dict in dict_list:
        d = one_dict.copy()

        for k in remove_keys:
            d.pop(k)

        if str(one_dict[key]) == str(sub_dict[key]):
            matched_dicts.append(d)
    return matched_dicts


def verbose(txt, verbosity, verb_level=2):
    """
    Parameters
    ----------
    txt : str
        Message which will be showed

    verb_level : int
        Level of verbosity:

        0 - All messages will be showed
        1 - Just messages witch verbosity 1 an 2 will be showed
        2 - Just messages witch verbosity 2 will be showed

    verb_level : int
        Verbosity level

    Returns
    -------
        None
    """
    if verbosity <= verb_level:
        print txt


def progressbar(it, prefix="", size=60):
    """
    Parameters
    ----------
    it : list
        List of values

    prefix : str
        Text which is displayed before progressbar

    size : int
        Number of items in progressbar

    Returns
    -------
        None
    """
    count = len(it)

    if count > 0:
        def _show(_i):
            x = int(size * _i / count)
            sys.stdout.write("%s[%s%s] %i/%i\r" %
                             (prefix, "#" * x, "." * (size - x), _i, count))
            sys.stdout.flush()

        _show(0)
        for i, item in enumerate(it):
            yield item
            _show(i + 1)
        sys.stdout.write("\n")
        sys.stdout.flush()


def create_folder(path):
    """Create folder if it not exists"""
    if not os.path.exists(path):
        os.makedirs(path)
        return True
    return False


def get_combinations(keys, *lists):
    """
    Make combinations from given lists

    Parameters
    ----------
    keys : list
        Name of consequent columns (lists)

    lists : list of lists
        Values to combine

    Example
    --------
        get_combinations( ["key1", "key2", "key3"], [1,2,3], ["m", "n", "k"], [77,88,99,55,22]

    Returns
    -------
    list
        All combinations
    """

    queries = []

    if not len(keys) == len(lists):
        raise Exception(
            "Length of header have to be the same of number of lists for combinations")

    for comb in list(itertools.product(*lists)):
        this_query = {}
        for i, key in enumerate(keys):
            this_query[key] = comb[i]
        queries.append(this_query)
    return queries


def getMeanDict(dict_list):
    if dict_list:
        new_d = []
        keys = dict_list[0].keys()
        for key in keys:
            new_d.append((key, np.mean([x[key] for x in dict_list])))
        return collections.OrderedDict(new_d)
    return {}


def convert_input_value(value):
    value = str(value).strip()
    if value == "False":
        return False
    elif value == "True":
        return True
    elif value == "None":
        return None
    elif value.startswith("`") and value.endswith("`"):
        try:
            return ast.literal_eval(value[1:-1])
        except:
            try:
                return eval(value[1:-1])
            except:
                pass

    if "." in value:
        try:
            return float(value)
        except ValueError:
            return str(value)
    try:
        return int(value)
    except ValueError:
        pass

    return value
