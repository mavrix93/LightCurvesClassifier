import ast
import copy
import datetime
import json
import logging
import os
import shutil
import traceback
import warnings
from io import StringIO

import numpy as np
from astropy.io import fits
from django.conf import settings
from interface.models import StarsFilter

from lcc.api.input_parse import parse_query_ranges
from lcc.api.input_parse import parse_tun_query
from lcc.db_tier.connectors.file_manager import FileManager
from lcc.entities.exceptions import QueryInputError
from lcc.entities.star import Star
from lcc.stars_processing.systematic_search.stars_searcher import StarsSearcherRedis
from lcc.stars_processing.tools.params_estim import ParamsEstimator
from lcc.stars_processing.tools.stats_manager import StatsManager
from lcc.stars_processing.tools.visualization import plotProbabSpace
from lcc.utils.helpers import create_folder
from lcc.utils.helpers import get_arguments
from lcc.utils.helpers import get_combinations
from lcc.utils.output_process_modules import saveIntoFile
from lcc.utils.stars import get_stars_dict

MAX_SAMPLES = 100


def get_queries_from_df(df):
    keys = df.columns.values.tolist()
    queries = []
    for row in df.values:
        queries.append(dict(zip(keys, row)))
    return queries


def make_data_file(estim, filt_id, data_path, N=None, xmax=None, xmin=None, ymax=None, ymin=None, max_samples=100):
    filt = estim.filters[filt_id]

    searched_test_coo = filt.getSpaceCoordinates(estim.searched_test)
    others_test_coo = filt.getSpaceCoordinates(estim.others_test)
    searched_train_coo = filt.getSpaceCoordinates(estim.searched_train)
    others_train_coo = filt.getSpaceCoordinates(estim.others_train)

    if len(searched_test_coo) > max_samples:
        searched_test_coo = searched_test_coo.sample(max_samples)

    if len(others_test_coo) > max_samples:
        others_test_coo = others_test_coo.sample(max_samples)

    if len(searched_train_coo) > max_samples:
        searched_train_coo = searched_train_coo.sample(max_samples)

    if len(others_train_coo) > max_samples:
        others_train_coo = others_train_coo.sample(max_samples)

    stars_coo = [searched_test_coo, searched_train_coo,
                 others_test_coo, others_train_coo]

    searched_test_ind = searched_test_coo.index
    others_test_ind = others_test_coo.index
    searched_train_ind = searched_train_coo.index
    others_train_ind = others_train_coo.index
    stars_ind = [searched_test_ind, searched_train_ind,
                 others_test_ind, others_train_ind]
    # TODO !!!
    coo_data = [np.transpose(st_coo.values).tolist()
                for st_coo in stars_coo]

    if coo_data:
        OVERLAY = 0.2
        dim = len(coo_data[0])
        plot_ranges = []
        for ll in range(dim):
            x_max = np.max([np.max(c[ll]) for c in coo_data])
            x_min = np.min([np.min(c[ll]) for c in coo_data])
            x_overlay = (x_max - x_min) * OVERLAY
            plot_ranges.append([x_min - x_overlay, x_max + x_overlay])
        if dim == 2:
            if xmax:
                try:
                    plot_ranges[0][1] = float(xmax)
                except (ValueError, TypeError):
                    pass
            if xmin:
                try:
                    plot_ranges[0][0] = float(xmin)
                except (ValueError, TypeError):
                    pass
            if ymax:
                try:
                    plot_ranges[1][1] = float(ymax)
                except (ValueError, TypeError):
                    pass
            if ymin:
                try:
                    plot_ranges[1][0] = float(ymin)
                except (ValueError, TypeError):
                    pass

    else:
        plot_ranges = None

    try:
        N = int(N)
    except (ValueError, TypeError):
        N = None

    if not N:
        N = 300

    _probab_space = plotProbabSpace(filt, plot_ranges=plot_ranges, opt="return", N=N)
    if len(_probab_space) == 4:
        pca = _probab_space[-1]
        orig_coo_data = copy.deepcopy(coo_data)
        coo_data = [np.transpose(pca.transform(np.transpose(this_coo))).tolist()  for this_coo in coo_data]
        r = -1
    else:
        orig_coo_data = None
        r = None

    probab_space = [q.tolist() for q in _probab_space[:r]]
    probab_plot_title = "Probability plot (" + ", ".join(
        [dec.__class__.__name__ for dec in filt.deciders]) + ")"

    lcs = []
    star_labels = []
    id_labels = []

    stars_dict = get_stars_dict(estim.searched_train + estim.others_train + estim.searched_test + estim.others_test)
    for st_group in stars_ind:
        this_star_labels = []
        for st_ind in st_group:
            st = stars_dict.get(st_ind)
            if not st:
                break
            stkeys = list(st.more.keys())
            stval = list(st.more.values())

            l = st.name + "<br>"
            if len(stkeys) >= 3:
                l += "\t|\t".join(stkeys[:3]) + "<br>" + \
                     "\t|\t".join([str(x) for x in stval[:3]])

                l += "<br>" + "<br>" + \
                     "\t|\t".join(stkeys[3:]) + "<br>" + \
                     "\t|\t".join([str(x) for x in stval[3:]])

            elif len(stkeys) != 0:
                l += "\t|\t".join(stkeys) + "<br>" + \
                     "\t|\t".join([str(x) for x in stval])

            this_star_labels.append(str(l))

            id_labels.append(str(st.name))
            if st.lightCurve:
                lcs.append(
                    [st.lightCurve.time.tolist(), st.lightCurve.mag.tolist(), st.lightCurve.err.tolist()])
            else:
                lcs.append([[], [], []])
        star_labels.append(this_star_labels)

    view_data = {"probab_data": probab_space,
                 "probab_plot_title": probab_plot_title,
                 "coo_data": coo_data,
                 "space_coords" : orig_coo_data,
                 "zeroes": [[0 for _ in coo_data[i][0]] for i in range(4)],
                 "lcs": lcs,
                 "point_labels": star_labels,
                 "labels": id_labels}

    with open(data_path, 'w') as outfile:
        json.dump(view_data, outfile, default=json_numpy_default)


def create_filter(searched_stars, contamination_stars, descriptors,
                  deciders, tuned_params, static_params, job, split_ratio, user_id):

    create_folder(
        os.path.join(settings.MEDIA_ROOT, user_id, "stars_filters", str(job.id)))

    # TODO map to db, no status file
    try:
        info = {"searched_stars": ", ".join([st.name for st in searched_stars]),
                "contamination_stars": ", ".join([st.name for st in contamination_stars]),
                "descriptors": ", ".join([desc.__name__ for desc in descriptors]),
                "deciders": ", ".join([desc.__name__ for desc in deciders]),
                "tuned_params_num": len(tuned_params),
                "start": str(datetime.datetime.now())[:-5],
                "finish": ""}

        job.status = "Running"
        job.save()

        job_id = str(job.id)

        with open(os.path.join(settings.MEDIA_ROOT, user_id, "stars_filters", job_id, 'info.json'), 'w') as outfile:
            json.dump(info, outfile, default=json_numpy_default)
        
        logging.debug("Params estimator params")
        logging.debug("Searching sample: %s" % searched_stars)
        logging.debug("Contamin sample: %s" % contamination_stars)
        logging.debug("Descriptors: %s" % descriptors)
        logging.debug("Deciders: %s" % deciders)
        logging.debug("Tuned params: %s" % tuned_params)
        logging.debug("Static params: %s" % static_params)
        
        estim = ParamsEstimator(searched=searched_stars,
                                others=contamination_stars,
                                descriptors=descriptors,
                                deciders=deciders,
                                tuned_params=tuned_params,
                                static_params=static_params,
                                split_ratio=split_ratio,
                                multiproc=False)

        filt, best_stats, best_params = estim.fit()

        job.status = "Done"
        job.finish_date = datetime.datetime.utcnow()
        job.save()

        stats = estim.stats
        roc = StatsManager(stats).getROC()
        x = [_x.tolist() for _x in roc[0]]
        y = [_x.tolist() for _x in roc[1]]
        roc = [x, y]

        axis = filt.searched_coords.columns.tolist()

        if len(axis) == 2 and axis[1] == "":
            axis = [axis[0].replace(",", "<br>"), ""]

        coo_plot_labels = ["Searched test sample", "Searched train sample",
                           "Contamination test sample", "Contamination train sample"]
        coo_plot_axis = axis

        coo_plot_title = ""

        stat_table = [list(stats[0].keys())] + roundNumbers(stats)

        probab_plot_axis = axis

        filt_name = "_".join([desc.__name__ for desc in descriptors])
        saveIntoFile(
            filt, os.path.join(settings.MEDIA_ROOT, user_id, "stars_filters", job_id), filt_name + ".filter")

        saveIntoFile(
            estim, os.path.join(settings.MEDIA_ROOT, user_id, "stars_filters", job_id), "estimator")

        view_data = {
                     "probab_plot_axis": probab_plot_axis,
                     "coo_plot_labels": coo_plot_labels,
                     "coo_plot_title": coo_plot_title,
                     "coo_plot_axis": coo_plot_axis,
                     "roc_data": roc,
                     "rows": stat_table,
                     "best_id": int(estim.best_id),
                     "job_id": int(job_id),
                     "filt_path": "filt" + str(job_id)}

        with open(os.path.join(settings.MEDIA_ROOT, user_id, "stars_filters", job_id, 'data.json'), 'w') as outfile:
            json.dump(view_data, outfile, default=json_numpy_default)

        make_data_file(estim, estim.best_id, os.path.join(settings.MEDIA_ROOT, user_id, "stars_filters",
                                                          job_id, 'data_%i.json' % estim.best_id), max_samples=MAX_SAMPLES)

        job = StarsFilter.objects.get(pk=job_id)
        job.status = "Done"
        job.finish_date = datetime.datetime.now()
        job.save()

    except Exception as e:
        filename = os.path.join(settings.MEDIA_ROOT, user_id, "stars_filters", job_id, "error.txt")

        with open(filename, "w") as fi:
            traceback.print_exc(file=fi)

        job = StarsFilter.objects.get(pk=job_id)
        job.status = "Failed"
        job.finish_date = datetime.datetime.now()
        job.save()


def query_dbs(all_queries, job_path, job, star_filters=[]):

    try:
        for db_name, queries in all_queries.items():
            lcs_path = os.path.join(job_path, db_name, "lcs")
            create_folder(job_path)
            create_folder(lcs_path)

            searcher = StarsSearcherRedis(star_filters, job_name="job:" + job_path.split('/')[-1], save_path=lcs_path,
                                          db_connector=db_name, save_coords=True)
            searcher.queryStars(queries)
            searcher._wait_to_done()


        shutil.make_archive(
            os.path.join(job_path, "..", str(job.id)), 'zip', job_path)

        job.status = "Done"
        job.finish_date = datetime.datetime.now()
        
    except Exception as e:
        job.status = "Failed"

        err_txt = "Error occurred:\n" + traceback.format_exc()

        with open(os.path.join(job_path, "error.txt"), "w") as f:
            f.write(err_txt)

    job.save()


def parse_conn_combs(field_names, all_fields):
    queries = {}
    for field_n, field_v in all_fields.items():
        if field_n in field_names:
            if field_v.startswith("`") and field_v.endswith("`"):
                pyth_expr = ast.literal_eval(field_v[1:-1])

                if isinstance(pyth_expr, list):
                    queries[field_n] = pyth_expr

                elif isinstance(pyth_expr, dict):
                    queries[field_n] = [pyth_expr]

            else:
                keys, params = _parse_conn_combs(field_v)
                queries[field_n] = get_combinations(keys, *params)
    return queries


def _parse_conn_combs(raw_query, keys_sep="\n", values_sep=":"):
    parts = raw_query.split(keys_sep)
    params = []
    keys = []
    for part in parts:
        part = part.strip()
        if part.startswith("`") and part.endswith("`"):
            this_comb = ast.literal_eval(part[1:-1])

            if isinstance(this_comb, dict):
                keys += list(this_comb.keys())
                params += [[v] for v in this_comb.values()]

            else:
                warnings.warn("Query not parsed! %s" % part)

        else:
            ind = part.find(values_sep)
            keys.append(part[:ind])
            this_comb = parse_query_ranges([part[ind + 1:]])[0]
            params.append(this_comb)

    return keys, params


def makeDesc(descriptors, _params):
    ready_descriptors = []
    for i, des in enumerate(descriptors):
        try:
            params = _params.get(des.__name__, {})

            ready_descriptors.append(des(**params))

        except TypeError:
            raise QueryInputError("Not enough parameters to construct constructor {0}\nGot: {1}".format(
                des.__name__, params))

    return ready_descriptors


def roundNumbers(stats):
    x = []
    for row in stats:
        z = []
        for y in row.values():
            try:
                y = round(y, 3)
            except TypeError:
                pass
            z.append(y)
        x.append(z)
    return x


def parse_combinations(keys, raw_dict, split_by=":"):
    _header, _params = _parse_combinations(keys, raw_dict, split_by)
    all_params = parse_query_ranges(_params)

    static_params = {}
    params = []
    header = []
    for p, head in zip(all_params, _header):
        if len(p) == 1:
            static_params[head] = p[0]
        else:
            params.append(p)
            header.append(head)

    combinations = get_combinations(header, *params)
    return parse_tun_query(combinations), parse_tun_query([static_params])[0]


def parse_comp_stars(files_dict):
    params = {}
    for key in files_dict.keys():
        key = key.strip()
        if key.startswith("templ_file"):
            parts = key.split(":")
            if len(parts) == 3:
                stars = parse_stars(files_dict.getlist(key))
                _, name, param_name = parts

                if name not in params:
                    params[name] = {}

                params[name][param_name] = stars

    return params


def getFields(ident_obj):
    args = get_arguments(list(ident_obj.values()))
    fields = []
    for arg in args:
        text_inputs = []
        name = arg.get("name")
        mand = arg["mandatory_params"]
        defa = arg["default_params"]

        text_inputs += zip(mand, ["" for _ in mand])
        text_inputs += zip(defa,
                           ["`" + str(v) + "`" for v in arg["default_values"]])
        fields.append([name, text_inputs])
    return fields


def parse_combinations_from_file(fi, delim=";"):
    if fi:
        data = []
        for i, chunk in enumerate(fi.read().strip().split("\n")):
            if chunk.startswith("#"):
                header = chunk[1:].split(delim)
                # TODO: Various delimiters
            else:
                row = {}
                for head, dat in zip(header, chunk.split(delim)):
                    row[head] = dat

                data.append(row)
        return data


def _parse_combinations(keys, raw_dict, split_by=":"):
    """

    Parameters
    ----------
    keys : list
        Names of objects to tune

    raw_dict : dict
        Dictionary of keys to parse. For example: {'descriptor:AbbeValueDesc:bins' : 10, ..}


    split_by : str
        Symbol which divides keys

    Returns
    -------

    """
    header = []
    params = []
    for k, val in raw_dict.items():
        parts = k.split(split_by)
        if len(parts) == 3:
            _, name, param_name = parts

            if name.strip() in keys:
                params.append(val)
                header.append(name + split_by + param_name)
    return header, params


def parse_stars(fi):
    stars = []
    for st_fi in fi:
        if st_fi.__dict__.get("_name", "").endswith(".dat"):
            fi_io = StringIO(st_fi.read())
            lc = FileManager._loadLcFromDat(fi_io)
            st = Star(name=st_fi.__dict__["_name"].split(".")[0])
            st.putLightCurve(lc)
            stars.append(st)

        else:
            stars.append(FileManager._createStarFromFITS(fits.open(st_fi)))
    return stars


def load_test_stars(path):
    return FileManager({"path": path}).getStars()


def json_numpy_default(x):

    if isinstance(x, np.int):
        return int(x)

    elif isinstance(x, np.float):
        return float(x)

    raise TypeError("Unserializable object {} of type {}".format(x, type(x)))
