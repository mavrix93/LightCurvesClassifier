#!/usr/bin/python3
import logging
import sys
import os
import importlib.util

logging.basicConfig(level=logging.INFO)


def main(path=None):
    if len(sys.argv) > 1:
        option = sys.argv[1]
        sys.argv = sys.argv[:1] + sys.argv[2:]

        if option == "create_project":
            logging.info("Creating the project...")
            from lcc.bin.create_project import main
            return main()
        try:
            path = path or os.getcwd()
            spec = importlib.util.spec_from_file_location("module.name",
                                                          os.path.join(path, 'project_settings.py'))
            project_settings = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(project_settings)
            logging.info("Settings file was loaded...")
        except IOError:
            raise IOError("""There are not 'project_settings.py' in the current directory.
                        Create project first by 'lcc create_project'""")

        if option == "make_filter":
            from lcc.bin.make_filter import main
            return main(project_settings)

        elif option == "filter_stars":
            from lcc.bin.filter_stars import main
            return main(project_settings)

        elif option == "prepare_query":
            logging.info("Creating query file...")
            from lcc.bin.prepare_query import main
            return main(project_settings)
        else:
            sys.stderr.write("""Invalid option. Parameter of lcc have
                        to be 'make_filter', 'filter_stars' or 'prepare_query'""")

    else:
        print("""Light Curves Classifier: Use one of the following commands: create_project, make_filter,
        filter_stars, prepare_query""")


if __name__ == '__main__':
    main()
