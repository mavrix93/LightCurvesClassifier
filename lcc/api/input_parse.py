import numpy as np

from lcc.entities.exceptions import QueryInputError
from lcc.utils.helpers import convert_input_value
import ast
import warnings


def parse_query_ranges(raw_params, split_by=":", enum_by=";"):
    """
    Parse range strings

    Parameters
    ----------
    raw_params : list
        List of strings which are composed of 0, 1 or 2 of `split_by` symbols.

    split_by : str
        Symbol which divides parameters ranges into from-to-step parts

    Returns
    -------
    list
        List of lists of whole range of combinations for particular parameters
    """
    all_combs = []
    for params in raw_params:
        par_ranges = [par.strip() for par in params.split(split_by)]

        if len(par_ranges) == 1:
            this_combs = [convert_input_value(t) for t in params.split(enum_by)]

        elif len(par_ranges) == 2:
            try:
                par_ranges = [int(x) for x in par_ranges]
            except:
                raise ValueError("Ranges of type from:to have to be integers")

            this_combs = range(*par_ranges)

        elif len(par_ranges) == 3:
            try:
                par_ranges = [float(x) for x in par_ranges]
            except:
                raise ValueError(
                    "Ranges of type from:to:steps have to be floats")
            this_combs = np.linspace(*par_ranges).tolist()

        else:
            raise Exception(
                "Particular parameters must not contain more then two seperation symbols (%s)!" % split_by)
        all_combs.append(this_combs)
    return all_combs


def parse_tun_query(raw_params):
    """
    Parse query of merged identifiers with their parameters

    Parameters
    ----------
    raw_params : list
        List of dictionaries of: 'name:params' : value.
        For example [{'VarioShapeDescr:alphabet_size': 7, ...}, ..]

    Returns
    -------
    list
        List of nested dictionaries. Keys are names of objects and their values
        are parameters (as keys for their values)
    """
    params = []
    for par in raw_params:
        params.append(_parse_tun_query(par))
    return params


def _parse_tun_query(one_param):
    this_comb = {}
    for key, value in one_param.iteritems():
        x = key.split(":")
        if len(x) != 2:
            raise QueryInputError(
                "Cannot parse tuning params header: %s. It has to be composed with 'descriptor name':'param name'" % key)
        obj_name, col = x

        descr = this_comb.get(obj_name)

        if not descr:
            this_comb[obj_name] = {}

        if isinstance(value, str):
            if value == "True":
                value = True
            elif value == "False":
                value = False
            elif value == "None":
                value = None
            elif value.strip().startswith("`") and value.strip().endswith("`"):
                try:
                    value = ast.literal_eval(value.strip()[1:-1])
                except Exception as e:
                    print value
                    warnings.warn(str(e))
                    try:
                        value = value.strip()[1:-1]
                    except:
                        pass

        this_comb[obj_name][col] = value
    return this_comb
