#
# TeslaCoin-specific code
#

# Utility functions

import os
import inspect

from electrum.tes.conf import *


def get_display_name():
    return '{}{}'.format(ELECTRUM_BASE_NAME, TESLACOIN_CODE)


def get_resource_name():
    return '{}-{}'.format(ELECTRUM_BASE_NAME.lower(), TESLACOIN_CODE.lower())


def get_base_path(path):
    # Use the right path separator for the platform
    path_split = path.split(os.sep)
    got_base = False
    base_path = []
    for path_el in path_split:
        if path_el == 'electrum':
            got_base = True
        if got_base:
            base_path.append(path_el)
    if base_path:
        return str(os.sep).join(base_path)
    else:
        # Return orig path as fallback
        return path


def get_caller():
    return '{}::{}()'.format(get_base_path(inspect.stack()[2][1]), inspect.stack()[2][3])


def is_ignored_caller(caller):
    for exc in TESLACOIN_DEBUG_IGNORE:
        if exc in caller:
            return True
    return False


def tes_print_msg(*args):
    caller = get_caller()
    if TESLACOIN_DEBUG and not is_ignored_caller(caller):
        from lib.util import print_msg
        print_msg('[TESDEBUG::MSG] [{}]:'.format(caller), *args)


def tes_print_error(*args):
    caller = get_caller()
    if TESLACOIN_DEBUG and not is_ignored_caller(caller):
        from lib.util import is_verbose, set_verbosity, print_error
        if not is_verbose:
            set_verbosity(True)
        print_error('[TESDEBUG::ERR] [{}]:'.format(caller), *args)
