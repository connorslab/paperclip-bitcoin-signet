#!/usr/bin/env python3
# Copyright (c) 2026 The Paperclip developers
# Distributed under the MIT software license, see COPYING.
"""Signed Blake2b custom signet, invalid signer rejection and restart."""
import importlib.util
from pathlib import Path
from test_framework.test_framework import BitcoinTestFramework
from test_framework.key import ECKey
from test_framework.script import CScript, OP_CHECKSIG
from test_framework.wallet import MiniWallet
from test_framework.util import assert_equal

class SignetTest(BitcoinTestFramework):
    def set_test_params(self):
        self.chain = 'signet'
        self.num_nodes = 1
        self.setup_clean_chain = True
        self.secret = (91).to_bytes(32, 'big')
        key = ECKey()
        key.set(self.secret, compressed=True)
        challenge = CScript([key.get_pubkey().get_bytes(), OP_CHECKSIG]).hex()
        self.extra_args = [['-xbtcovtest', '-signetchallenge=' + challenge, '-prune=550', '-minimumchainwork=0']]

    def run_test(self):
        path = Path(self.config['environment']['SRCDIR']) / 'contrib/signet/xbt_miner.py'
        spec = importlib.util.spec_from_file_location('xbt_miner', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        node = self.nodes[0]
        wallet = MiniWallet(node)
        for height in range(1, 4):
            template = node.getblocktemplate({'rules': ['signet', 'segwit', 'blake2b']})
            block = module.signed_block(template, wallet.get_output_script(), self.secret)
            assert block.m_header_v2
            assert_equal(node.submitblock(block.serialize().hex()), None)
            assert_equal(node.getblockcount(), height)
        self.restart_node(0)
        assert_equal(node.getblockcount(), 3)
        assert_equal(node.verifychain(), True)

if __name__ == '__main__':
    SignetTest(__file__).main()
