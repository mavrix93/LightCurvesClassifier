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


def prepare_run(directory, run_name):
    d = tree()
    d[run_name]["lcs"]

    rec(d, directory)
