#
# TeslaCoin-specific code
#

# Generate checkpoints

import json
import imp
imp.load_module('lib', *imp.find_module('..'))
from lib.blockchain import bits_to_target

checkpoints = [
    #  Height, bits, block hash
    (300000, 0x1d01d837, "0000000176cccf5d52740533848d18f1d352ef03b4351e323c20e8753949de26"),
    (400000, 0x1d031cca, "000000000b1b765a99a71be00b61dec7872cf36c68ffe7e1d7d8651a8a02b503"),
    (500000, 0x1e00ffff, "dc87d54248adc00a19ce51669862a2442971744d57e49ddf50b94b6e409e1302"),
    (506110, 0x1e00fc61, "4b6641ba347ac5224f2d8b25f565e964bb2f4d3a70c532b0f0ab8ca3457db02b"),
    (700000, 0x1e00ffff, "2fda95b0418ef4cd096f40aac77089ea5db6b3b3b47a090097154e7192573d2c"),
    (750000, 0x1e00ffff, "c395084cda1c908ffe78879d19019f971f774263c45c67dbc92a7956fbe371a1"),
    (850000, 0x1e00fef5, "81ca25c5ea155cafdac584f3660b539e72cb811c3a5a588949d1bd45e69c0b36"),
    (950000, 0x1e00b708, "cd0f4431b6b5d521118008a6c132d088e79a35e1c41140570875eeb066727beb"),
    (1050000, 0x1d789f1a, "a6e00d59fbdf818ea27f0e9a6e1629179a6c0a6a5849d419c32e43bcd58565d9"),
    (1150000, 0x1e00ffff, "b8ecff73cf7c164b5911f798e03b0bfdab0584f78bc5b1f7fe779c134f676044"),
    (1250000, 0x1e00ffff, "81e292f9d8236218a602b74611a792304b7150f41df3e2d37d7accffde5800ce"),
    (1350000, 0x1e00ffff, "3439c8ba9e3e303b8a2c0caf3c7a4e9bf7167ec8c9e789b8dc453002b56c3f92"),
    (1450000, 0x1d23dc40, "a2251f7ee125cb0bbf405e7b30e81bfdb7c7b8f2b7eec0144e8cb42d2799991d"),
    (1550000, 0x1d232d22, "27a9d6578919a61bb959e43d8934f87dd42d5654845f49449a3b7128ddb47aaa"),
    (1650000, 0x1e00ffff, "16264c6d21c24647dc6db7803d87b9f2e16d2e2c51d2a37c2b5684c4f84a8cfe"),
]


def generate_checkpoint(cp_data):
    return [cp_data[2], bits_to_target(int(cp_data[1])), cp_data[0]]


if __name__ == '__main__':
    checkpoints_list = []
    for cp in checkpoints:
        bits_int = int(cp[1])
        print('Generating checkpoint for block ({}) at height {} with bits value: {}'.format(cp[0], cp[2], int(cp[1])))
        checkpoint = generate_checkpoint(cp)
        checkpoints_list.append(checkpoint)
    print(json.dumps(checkpoints_list, indent=4))
