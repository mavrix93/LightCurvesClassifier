from collections import defaultdict
import os.path


def tree():
    return defaultdict(tree)


def rec(directory, current_path):
    if len(directory):
        for direc in directory:
            rec(directory[direc], os.path.join(current_path, direc))
    else:
        if not os.path.exists(current_path):
            os.makedirs(current_path)


def prepare_run(directory, run_name):
    d = tree()
    rec(d, os.path.join(directory, run_name))
