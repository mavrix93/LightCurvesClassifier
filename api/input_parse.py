from lcc.entities.exceptions import QueryInputError


def parse_tun_query(raw_params):
    #  [{'VarioShapeDescr:alphabet_size': 7, 'VarioShapeDescr:days_per_bin': 9, 'HistShapeDescr:alphabet_size': 16, 'HistShapeDescr:bins': 47}, {'Var
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
        this_comb[obj_name][col] = value
    return this_comb
