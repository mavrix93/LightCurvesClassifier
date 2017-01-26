import sys
import os

from lcc.data_manager.prepare_package import tree
from lcc.data_manager.prepare_package import rec

if __name__ == '__main__':
    options = sys.argv[1:]
    cur_loc = os.getcwd()
    if not options:
        path = cur_loc
        proj_name = "project"

    if len(options) == 1:
        path = cur_loc
        proj_name = options[0]
    else:
        path = options[1]
        proj_name = options[0]

    d = tree()

    d[proj_name]["inputs"]["tun_params"]
    d[proj_name]["inputs"]["queries"]
    d[proj_name]["inputs"]["lcs"]
    d[proj_name]["inputs"]["filters"]

    d[proj_name]["outputs"]

    rec(d, path)
