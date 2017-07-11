#!/usr/bin/env python3

# Single entry point / dispatcher for simplified running of
#
## pfcon
#

import  argparse
import  os

str_desc = """

 NAME

    docker-entrypoint.py

 SYNOPSIS

    docker-entrypoint.py  [optional cmd args for pfcon]


 DESCRIPTION

    'docker-entrypoint.py' is the main entrypoint for running pfcon.

"""

def pfcon_do(args, unknown):

    str_otherArgs   = ' '.join(unknown)

    str_CMD = "/usr/local/bin/pfcon %s" % (str_otherArgs)
    return str_CMD


parser  = argparse.ArgumentParser(description = str_desc)

# Pattern of minimum required pfurl args
parser.add_argument(
    '--verb',
    action  = 'store',
    dest    = 'verb',
    default = 'POST',
    help    = 'REST verb.'
)
parser.add_argument(
    '--jsonwrapper',
    action  = 'store',
    dest    = 'jsonwrapper',
    default = '',
    help    = 'wrap msg in optional field'
)
parser.add_argument(
    '--raw',
    help    = 'if specified, do not wrap return data from remote call in json field',
    dest    = 'b_raw',
    action  = 'store_true',
    default = False
)


args, unknown   = parser.parse_known_args()

if __name__ == '__main__':
    try:
        fname   = 'pfcon_do(args, unknown)'
        str_cmd = eval(fname)
        os.system(str_cmd)
    except:
        print("Misunderstood container app... exiting.")
