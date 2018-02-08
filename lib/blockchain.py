# Electrum - lightweight Bitcoin client
# Copyright (C) 2012 thomasv@ecdsa.org
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
import os
import math
import threading

from . import util
from . import bitcoin
from .bitcoin import *

from lib.tes.util import tes_print_msg, tes_print_error

MAX_TARGET = 0x00000fffffffffffffffffffffffffffffffffffffffffffffffffffffffffff  # ~uint256(0) >> 20 (https://github.com/TeslacoinFoundation/Teslacoin-v.3.4/blob/master/src/main.cpp#L37)
MAX_TARGET_STAKE = 0x000000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffff  # ~uint256(0) >> 24 (https://github.com/TeslacoinFoundation/Teslacoin-v.3.4/blob/master/src/main.cpp#L38)
HARD_MAX_TARGET_STAKE = 0x00000003ffffffffffffffffffffffffffffffffffffffffffffffffffffffff  # ~uint256(0) >> 30 (https://github.com/TeslacoinFoundation/Teslacoin-v.3.4/blob/master/src/main.cpp#L39)
CUTOFF_POW_BLOCK = 465000


def serialize_header(res):
    s = int_to_hex(res.get('version'), 4) \
        + rev_hex(res.get('prev_block_hash')) \
        + rev_hex(res.get('merkle_root')) \
        + int_to_hex(int(res.get('timestamp')), 4) \
        + int_to_hex(int(res.get('bits')), 4) \
        + int_to_hex(int(res.get('nonce')), 4)
    return s


def deserialize_header(s, height):
    hex_to_int = lambda s: int('0x' + bh2u(s[::-1]), 16)
    h = {}
    h['version'] = hex_to_int(s[0:4])
    h['prev_block_hash'] = hash_encode(s[4:36])
    h['merkle_root'] = hash_encode(s[36:68])
    h['timestamp'] = hex_to_int(s[68:72])
    h['bits'] = hex_to_int(s[72:76])
    h['nonce'] = hex_to_int(s[76:80])
    h['block_height'] = height
    return h


def hash_header(header):
    if header is None:
        return '0' * 64
    if header.get('prev_block_hash') is None:
        header['prev_block_hash'] = '00'*32
    return hash_encode(TESHash(bfh(serialize_header(header))))


blockchains = {}


def read_blockchains(config):
    blockchains[0] = Blockchain(config, 0, None)
    fdir = os.path.join(util.get_headers_dir(config), 'forks')
    if not os.path.exists(fdir):
        os.mkdir(fdir)
    l = filter(lambda x: x.startswith('fork_'), os.listdir(fdir))
    l = sorted(l, key = lambda x: int(x.split('_')[1]))
    for filename in l:
        checkpoint = int(filename.split('_')[2])
        parent_id = int(filename.split('_')[1])
        b = Blockchain(config, checkpoint, parent_id)
        h = b.read_header(b.checkpoint)
        if b.parent().can_connect(h, check_height=False):
            blockchains[b.checkpoint] = b
        else:
            util.print_error("cannot connect", filename)
    return blockchains


def check_header(header):
    if type(header) is not dict:
        return False
    for b in blockchains.values():
        if b.check_header(header):
            return b
    return False


def can_connect(header):
    for b in blockchains.values():
        if getattr(b, 'set_current_header') and callable(getattr(b, 'set_current_header')):
            # Set the current header
            b.set_current_header(header)
        if b.can_connect(header):
            return b
    return False


class Blockchain(util.PrintError):
    """
    Manages blockchain headers and their verification
    """

    def __init__(self, config, checkpoint, parent_id):
        self.config = config
        self.catch_up = None # interface catching up
        self.checkpoint = checkpoint
        self.checkpoints = bitcoin.NetworkConstants.CHECKPOINTS
        self.parent_id = parent_id
        self.lock = threading.Lock()
        self._current_header = None  # Store the header currently being processed in memory
        with self.lock:
            self.update_size()

    def parent(self):
        return blockchains[self.parent_id]

    def get_max_child(self):
        children = list(filter(lambda y: y.parent_id==self.checkpoint, blockchains.values()))
        return max([x.checkpoint for x in children]) if children else None

    def get_checkpoint(self):
        mc = self.get_max_child()
        return mc if mc is not None else self.checkpoint

    def get_branch_size(self):
        return self.height() - self.get_checkpoint() + 1

    def get_name(self):
        return self.get_hash(self.get_checkpoint()).lstrip('00')[0:10]

    def get_current_header(self, height=None):
        if not height:
            return self._current_header
        else:
            if self._current_header and self._current_header.get('block_height') == height:
                return self._current_header
        return None

    def set_current_header(self, header):
        tes_print_msg("Setting current header: {}".format(header))
        self._current_header = header

    def check_header(self, header):
        header_hash = hash_header(header)
        height = header.get('block_height')
        return header_hash == self.get_hash(height)

    def fork(parent, header):
        checkpoint = header.get('block_height')
        self = Blockchain(parent.config, checkpoint, parent.checkpoint)
        open(self.path(), 'w+').close()
        self.save_header(header)
        return self

    def height(self):
        return self.checkpoint + self.size() - 1

    def size(self):
        with self.lock:
            return self._size

    def update_size(self):
        p = self.path()
        self._size = os.path.getsize(p)//80 if os.path.exists(p) else 0

    def verify_header(self, header, prev_hash, target):
        _hash = hash_header(header)
        tes_print_msg("Got hash {} for header: {}".format(_hash, header))
        if prev_hash != header.get('prev_block_hash'):
            raise BaseException("prev hash mismatch: %s vs %s" % (prev_hash, header.get('prev_block_hash')))
        if bitcoin.NetworkConstants.TESTNET:
            return
        bits = target_to_bits(target)
        if bits != header.get('bits'):
            raise BaseException("bits mismatch: %s vs %s" % (bits, header.get('bits')))
        # Only check pow for pow blocks
        if not self.is_proof_of_stake_header(header):
            if int('0x' + _hash, 16) > target:
                raise BaseException("insufficient proof of work: %s vs target %s" % (int('0x' + _hash, 16), target))

    def verify_chunk(self, index, data):
        num = len(data) // 80
        prev_hash = self.get_hash(index - 1)
        for i in range(num):
            raw_header = data[i * 80:(i + 1) * 80]
            header = deserialize_header(raw_header, index + i)
            # Set the current header
            self.set_current_header(header)
            # Check for pos block
            is_pos = self.is_proof_of_stake(index + i)
            target = self.get_target(index + i, is_pos)
            self.verify_header(header, prev_hash, target)
            prev_hash = hash_header(header)

    def path(self):
        d = util.get_headers_dir(self.config)
        filename = 'blockchain_headers' if self.parent_id is None else os.path.join('forks', 'fork_%d_%d'%(self.parent_id, self.checkpoint))
        return os.path.join(d, filename)

    def save_chunk(self, index, chunk):
        filename = self.path()
        d = (index - self.checkpoint) * 80
        if d < 0:
            chunk = chunk[-d:]
            d = 0
        self.write(chunk, d, index > len(self.checkpoints))
        self.swap_with_parent()

    def swap_with_parent(self):
        if self.parent_id is None:
            return
        parent_branch_size = self.parent().height() - self.checkpoint + 1
        if parent_branch_size >= self.size():
            return
        self.print_error("swap", self.checkpoint, self.parent_id)
        parent_id = self.parent_id
        checkpoint = self.checkpoint
        parent = self.parent()
        with open(self.path(), 'rb') as f:
            my_data = f.read()
        with open(parent.path(), 'rb') as f:
            f.seek((checkpoint - parent.checkpoint)*80)
            parent_data = f.read(parent_branch_size*80)
        self.write(parent_data, 0)
        parent.write(my_data, (checkpoint - parent.checkpoint)*80)
        # store file path
        for b in blockchains.values():
            b.old_path = b.path()
        # swap parameters
        self.parent_id = parent.parent_id; parent.parent_id = parent_id
        self.checkpoint = parent.checkpoint; parent.checkpoint = checkpoint
        self._size = parent._size; parent._size = parent_branch_size
        # move files
        for b in blockchains.values():
            if b in [self, parent]: continue
            if b.old_path != b.path():
                self.print_error("renaming", b.old_path, b.path())
                os.rename(b.old_path, b.path())
        # update pointers
        blockchains[self.checkpoint] = self
        blockchains[parent.checkpoint] = parent

    def write(self, data, offset, truncate=True):
        filename = self.path()
        with self.lock:
            with open(filename, 'rb+') as f:
                if truncate and offset != self._size*80:
                    f.seek(offset)
                    f.truncate()
                f.seek(offset)
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            self.update_size()

    def save_header(self, header):
        delta = header.get('block_height') - self.checkpoint
        data = bfh(serialize_header(header))
        assert delta == self.size()
        assert len(data) == 80
        self.write(data, delta*80)
        self.swap_with_parent()

    def read_header(self, height):
        assert self.parent_id != self.checkpoint
        if height < 0:
            return
        if height < self.checkpoint:
            return self.parent().read_header(height)
        if height > self.height():
            return
        delta = height - self.checkpoint
        name = self.path()
        if os.path.exists(name):
            with open(name, 'rb') as f:
                f.seek(delta * 80)
                h = f.read(80)
        if h == bytes([0])*80:
            return None
        return deserialize_header(h, height)

    def get_hash(self, height):
        if height == -1:
            return '0000000000000000000000000000000000000000000000000000000000000000'
        elif height == 0:
            return bitcoin.NetworkConstants.GENESIS
        elif height < len(self.checkpoints):
            index = height
            h, t = self.checkpoints[index]
            return h
        else:
            return hash_header(self.read_header(height))

    def is_proof_of_stake_header(self, header):
        # Assume false if header is null
        if not header:
            return False
        nonce = header.get('nonce')
        height = header.get('block_height')
        # Determine pos block by checking for nonce == 0 or height > pow cutoff
        if (nonce is not None and nonce == 0) or height > CUTOFF_POW_BLOCK:
            return True
        else:
            return False

    def is_proof_of_stake(self, index):
        # If height > the pow cutoff, block is pos
        if index > CUTOFF_POW_BLOCK:
            return True
        hdr = self.read_header(index)
        # If we cant read the header at index try getting the current header
        if not hdr and self.get_current_header(height=index):
            hdr = self.get_current_header()
        return self.is_proof_of_stake_header(hdr)

    def is_proof_of_work(self, index):
        return not self.is_proof_of_stake(index)

    def get_last_block_index(self, index, is_pos):
        pindex = index
        while pindex > 0 and (pindex - 1) > 0 and (self.is_proof_of_stake(pindex) != is_pos):
            pindex -= 1
        return pindex

    def get_target(self, index, is_pos):
        # GetNextTargetRequired() - https://github.com/TeslacoinFoundation/Teslacoin-v.3.4/blob/master/src/main.cpp#L848
        if bitcoin.NetworkConstants.TESTNET:
            return 0
        # Define max target based on block type
        max_target = MAX_TARGET
        if is_pos:
            if index + 1 > 15000:
                max_target = MAX_TARGET_STAKE
            elif index + 1 > 14060:
                max_target = HARD_MAX_TARGET_STAKE
        # Return MAX_TARGET for genesis, first and second blocks
        if index - 1 in (-1, 0, 1):
            tes_print_msg("Returning MAX_TARGET for block index: {} ({})".format(index, max_target))
            return max_target
        if index - 1 < len(self.checkpoints):
            h, t = self.checkpoints[index]
            tes_print_msg("Getting target from checkpoints, index: {} ({})".format(index, t))
            return t

        # Stake/target vars
        target_timespan = math.floor(0.16 * 24 * 60 * 60)
        stake_target_spacing = 30
        target_spacing_work_max = 12 * stake_target_spacing

        # Get block prev/prevprev indexes
        p_block_idx = self.get_last_block_index(index - 1, is_pos)
        pp_block_idx = self.get_last_block_index(p_block_idx - 1, is_pos)

        # Get the block headers determined by indexes
        # If index is the current height it will not be possible to read so use get_current_header
        if p_block_idx == index:
            p_block_hdr = self.get_current_header(height=index)
        else:
            p_block_hdr = self.read_header(p_block_idx)
        pp_block_hdr = self.read_header(pp_block_idx)

        # Define spacing and interval
        actual_spacing = p_block_hdr.get('timestamp') - pp_block_hdr.get('timestamp')
        if is_pos:
            target_spacing = stake_target_spacing
        else:
            target_spacing = min(target_spacing_work_max, stake_target_spacing * (index - p_block_idx))
        interval = math.floor(target_timespan / target_spacing)

        # Get the new target for the block
        mul_unit = ((interval - 1) * target_spacing + actual_spacing + actual_spacing)
        div_unit = ((interval + 1) * target_spacing)
        new_target = CompactNum(p_block_hdr.get('bits'), mul_unit, div_unit)
        if new_target > max_target:
            tes_print_msg("New target exceeds MAX_TARGET, returning MAX_TARGET for block index: {} ({})"
                          .format(index, max_target))
            new_target = max_target

        return int(new_target)

    def can_connect(self, header, check_height=True):
        height = header['block_height']
        tes_print_msg("Current height from header: {}, checkpoint: {}".format(height, self.height()))
        if check_height and self.height() != height - 1:
            tes_print_error("Height mismatch, return False")
            #self.print_error("cannot connect at height", height)
            return False
        if height == 0:
            height_0_hash = hash_header(header)
            if height_0_hash != bitcoin.NetworkConstants.GENESIS:
                tes_print_error("Hash at height 0 does not match genesis hash. Expected: {}, got: {}"
                                .format(bitcoin.NetworkConstants.GENESIS, height_0_hash))
            else:
                tes_print_msg("Hash at height 0 matches genesis hash")
            return height_0_hash == bitcoin.NetworkConstants.GENESIS
        try:
            prev_hash = self.get_hash(height - 1)
        except:
            return False
        if prev_hash != header.get('prev_block_hash'):
            tes_print_error("Unexpected hash for height {} from header. Expected: {}, got: {}"
                            .format(height - 1, prev_hash, header.get('prev_block_hash')))
            return False
        tes_print_msg("Confirmed hash for prev height {}: {}".format(height - 1, prev_hash))
        # Check for pos block
        is_pos = self.is_proof_of_stake_header(header)
        if is_pos:
            tes_print_msg("Proof-of-stake block found at height: {}".format(height))
        target = self.get_target(height, is_pos)
        tes_print_msg("Got target: {} ({})".format(target, target_to_bits(target)))
        try:
            self.verify_header(header, prev_hash, target)
        except BaseException as e:
            tes_print_error("Failed to verify header of block {}: {}".format(height, e))
            return False
        return True

    def connect_chunk(self, idx, hexdata):
        try:
            data = bfh(hexdata)
            self.verify_chunk(idx, data)
            #self.print_error("validated chunk %d" % idx)
            self.save_chunk(idx, data)
            return True
        except BaseException as e:
            self.print_error('verify_chunk failed', str(e))
            return False

    def get_checkpoints(self):
        # for each chunk, store the hash of the last block and the target after the chunk
        cp = []
        n = self.height()
        for index in range(n):
            h = self.get_hash(index)
            # Check for pos block
            is_pos = self.is_proof_of_stake(index)
            target = self.get_target(index, is_pos)
            cp.append((h, target))
        return cp


def bits_to_target(bits):
    bitsN = (bits >> 24) & 0xff
    bitsBase = bits & 0xffffff
    if not (bitsBase >= 0x8000 and bitsBase <= 0x7fffff):
        raise BaseException("Second part of bits should be in [0x8000, 0x7fffff]")
    return bitsBase << (8 * (bitsN-3))


def target_to_bits(target):
    c = ("%064x" % int(target))[2:]
    while c[:2] == '00' and len(c) > 6:
        c = c[2:]
    bitsN, bitsBase = len(c) // 2, int('0x' + c[:6], 16)
    if bitsBase >= 0x800000:
        bitsN += 1
        bitsBase >>= 8
    return bitsN << 24 | bitsBase


class CompactNum:

    def __init__(self, bits, mul, div):
        self.bits = bits
        self.mul = mul
        self.div = div

    def __int__(self):
        return int(self.to_target())

    def __gt__(self, other):
        if isinstance(other, CompactNum):
            return self.to_target() > other.to_target()
        else:
            return self.to_target() > other

    def __lt__(self, other):
        if isinstance(other, CompactNum):
            return self.to_target() < other.to_target()
        else:
            return self.to_target() < other

    def __eq__(self, other):
        if isinstance(other, CompactNum):
            return self.to_target() == other.to_target()
        else:
            return self.to_target() == other

    def to_target(self):
        if self.div > 0:
            return (bits_to_target(self.bits) * self.mul) / self.div
        else:
            return bits_to_target(self.bits) * self.mul
