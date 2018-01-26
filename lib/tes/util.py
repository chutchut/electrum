#
# TeslaCoin-specific code
#

# Utility functions

from lib.tes.conf import *


def get_display_name():
    return '{}{}'.format(ELECTRUM_BASE_NAME, TESLACOIN_CODE)


def get_resource_name():
    return '{}-{}'.format(ELECTRUM_BASE_NAME.lower(), TESLACOIN_CODE.lower())
