#
# TeslaCoin-specific code
#

# Config

TESLACOIN_DEBUG = True
TESLACOIN_DEBUG_IGNORE = [
    'verifier.py::run()',
    'network.py::blockchain()',
    'get_tx_height()',
]

ELECTRUM_BASE_NAME = 'Electrum'
TESLACOIN_CODE = 'TES'
TESLACOIN_NAME = 'Teslacoin'
DEFAULT_WALLET_NAME = 'default_tes_wallet'
