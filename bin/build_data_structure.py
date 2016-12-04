#!/usr/bin/env python
# encoding: utf-8

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _tools.prepare_package import create_data_structure
from entities.exceptions import QueryInputError


def main():
    """
    The script builds data folders tree. If it is executed with 'y' option
    also example scripts are executed in order to create example outputs
    in data folders (e.g. data/inputs/examples, data/tuning_logs/examples...).
    """
    
    err = QueryInputError("You need to specify whether example scripts should be executed by 'n' or 'y'.")
    
    args = sys.argv
    print args
    if len(args) == 2:
        if args[1] == "y":
            run_examples = True
        elif args[1] == "n":
            run_examples = False
        else:
            raise err
            
        create_data_structure( run_examples )
        print "\n***********\nData structure with examples was created"
    else:
        raise err


if __name__ == "__main__":        
    sys.exit(main())