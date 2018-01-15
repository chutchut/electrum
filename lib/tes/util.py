#
# TeslaCoin-specific code
#

# Utility functions

from lib.tes.conf import *


def get_display_name():
    return '{}{}'.format(ELECTRUM_BASE_NAME, TESLACOIN_SUFFIX)


def get_resource_name():
    return '{}-{}'.format(ELECTRUM_BASE_NAME.lower(), TESLACOIN_SUFFIX.lower())
