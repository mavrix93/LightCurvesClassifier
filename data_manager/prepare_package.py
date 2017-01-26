from collections import defaultdict
import os.path


def tree():
    return defaultdict(tree)


def rec(directory, current_path):
    if len(directory):
        for direc in directory:
            rec(directory[direc], os.path.join(current_path, direc))
    else:
        os.makedirs(current_path)


def prepare_run(directory, runs=[]):
    d = tree()

    if "make_filter" in runs:
        d["make_filter"]["filters"]
        d["make_filter"]["tunining_data"]

    if "filtering" in runs:
        d["filtering"]["lcs"]

    rec(d, directory)
