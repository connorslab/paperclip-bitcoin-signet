#!/usr/bin/env python3
# Copyright (c) 2026 The Paperclip developers
# Distributed under the MIT software license, see COPYING.
"""Signed Blake2b custom signet, invalid signer rejection and restart."""
import importlib.util
import copy
from pathlib import Path
from test_framework.test_framework import BitcoinTestFramework
from test_framework.key import ECKey
from test_framework.script import CScript, OP_CHECKSIG
from test_framework.wallet import MiniWallet
from test_framework.util import assert_equal

class SignetTest(BitcoinTestFramework):
    def set_test_params(self):
        self.chain = 'signet'
        self.num_nodes = 2
        self.setup_clean_chain = True
        self.secret = (91).to_bytes(32, 'big')
        key = ECKey()
        key.set(self.secret, compressed=True)
        challenge = CScript([key.get_pubkey().get_bytes(), OP_CHECKSIG]).hex()
        common = ['-signetchallenge=' + challenge, '-minimumchainwork=0']
        # Existing configurations and the renamed option must use the same network.
        self.extra_args = [common + ['-btccovtest'], common + ['-xbtcovtest']]

    def run_test(self):
        path = Path(self.config['environment']['SRCDIR']) / 'contrib/signet/bitcoin_miner.py'
        spec = importlib.util.spec_from_file_location('bitcoin_miner', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        node = self.nodes[0]
        self.stop_node(0)
        node.assert_start_raises_init_error(
            extra_args=self.extra_args[0] + ['-xbtcovtest=0'],
            expected_msg='Error: Conflicting covenant activation options',
        )
        self.start_node(0)
        self.connect_nodes(0, 1)
        wallet = MiniWallet(node)
        for height in range(1, 4):
            template = node.getblocktemplate({'rules': ['signet', 'segwit', 'blake2b']})
            block = module.signed_block(template, wallet.get_output_script(), self.secret)
            assert block.m_header_v2
            bad = copy.deepcopy(block)
            script = bytearray(bad.vtx[0].vout[-1].scriptPubKey)
            script[-3] ^= 1
            bad.vtx[0].vout[-1].scriptPubKey = bytes(script)
            bad.vtx[0].rehash()
            bad.hashMerkleRoot = bad.calc_merkle_root()
            bad.solve()
            assert_equal(node.submitblock(bad.serialize().hex()), 'bad-signet-blksig')
            assert_equal(node.submitblock(block.serialize().hex()), None)
            assert_equal(node.getblockcount(), height)
        self.sync_blocks()
        assert_equal(self.nodes[1].getblockcount(), 3)
        self.restart_node(0)
        assert_equal(node.getblockcount(), 3)
        assert_equal(node.verifychain(), True)

if __name__ == '__main__':
    SignetTest(__file__).main()
