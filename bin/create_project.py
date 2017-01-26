import sys
import os

from lcc.data_manager.prepare_package import tree
from lcc.data_manager.prepare_package import rec


def main():
    options = sys.argv[1:]
    cur_loc = os.getcwd()
    if not options:
        path = cur_loc
        proj_name = "project"

    elif len(options) == 1:
        path = cur_loc
        proj_name = options[0]
    else:
        path = os.path.join(cur_loc, options[1])
        proj_name = options[0]

    d = tree()

    d[proj_name]["tun_params"]
    d[proj_name]["queries"]
    d[proj_name]["inp_lcs"]
    d[proj_name]["filters"]

    d[proj_name]["query_results"]

    rec(d, path)

    # Create settings file
    lines = ["import os",
             "\n",
             "project_dir = '{0}'".format(os.path.join(path, proj_name)),
             "\n",
             "# Input locations",
             "INP_LCS = os.path.join(project_dir, 'inp_lcs')",
             "TUN_PARAMS = os.path.join(project_dir, 'tun_params')",
             "QUERIES = os.path.join(project_dir, 'queries')",
             "FILTERS = os.path.join(project_dir, 'filters')",
             "RESULTS = os.path.join(project_dir, 'query_results')",
             "\n",
             "# Output locations"]

    with open(os.path.join(path, proj_name, "project_settings.py"), "w") as f:
        for line in lines:
            f.write(line + "\n")


if __name__ == '__main__':
    main()
