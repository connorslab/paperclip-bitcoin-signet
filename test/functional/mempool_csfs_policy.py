#!/usr/bin/env python3
# Copyright (c) 2026 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Historical CSFS behavior and transaction factory for activation tests."""

import hashlib

from feature_bitcoin_covenants import template_hash
from test_framework.key import ORDER, TaggedHash, compute_xonly_pubkey, secp256k1
from test_framework.messages import COutPoint, CTransaction, CTxIn, CTxInWitness, CTxOut
from test_framework.script import CScript, CScriptOp, OP_NOT, OP_SHA256, OP_VERIFY, taproot_construct
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import assert_equal, assert_raises_rpc_error
from test_framework.wallet import MiniWallet


def sign_message(key, message):
    # BIP340 test signer extended to arbitrary-length messages for BIP348.
    secret = int.from_bytes(key, 'big')
    public = secret * secp256k1.G
    if not public.y.is_even():
        secret = ORDER - secret
    t = (secret ^ int.from_bytes(TaggedHash('BIP0340/aux', bytes(32)), 'big')).to_bytes(32, 'big')
    nonce = int.from_bytes(TaggedHash('BIP0340/nonce', t + public.to_bytes_xonly() + message), 'big') % ORDER
    assert nonce
    point = nonce * secp256k1.G
    k = nonce if point.y.is_even() else ORDER - nonce
    e = int.from_bytes(TaggedHash('BIP0340/challenge', point.to_bytes_xonly() + public.to_bytes_xonly() + message), 'big') % ORDER
    return point.to_bytes_xonly() + ((k + e * secret) % ORDER).to_bytes(32, 'big')


class CSFSPolicyTest(BitcoinTestFramework):
    def set_test_params(self):
        self.num_nodes = 2
        self.setup_clean_chain = True
        # Historical unrestricted CSFS policy behavior. The template-only
        # deployment has separate activation and post-activation coverage.
        self.base_args = ['-btccovtest', '-testactivationheight=blake2b@1', '-rdtsexpiry=2147483647', '-testactivationheight=csfstemplate@-1']
        self.extra_args = [self.base_args, self.base_args]

    def make_spend(self, message, mode='witness'):
        tx = CTransaction()
        tx.version = 2
        tx.vin = [CTxIn(COutPoint(0, 1), nSequence=0xfffffffd)]
        tx.vout = [CTxOut(99000, self.wallet.get_output_script())]
        if mode in ('template', 'template-empty', 'template-literal'):
            message = template_hash(tx)
            script = CScript(([message] if mode == 'template-literal' else [CScriptOp(0xce)]) +
                             [self.public, CScriptOp(0xcc)] + ([OP_NOT] if mode == 'template-empty' else []))
            witness = [b'' if mode == 'template-empty' else sign_message(self.key, message)]
        elif mode == 'script':
            script = CScript([message, self.public, CScriptOp(0xcc)])
            witness = [sign_message(self.key, message)]
        elif mode == 'hash':
            script = CScript([OP_SHA256, self.public, CScriptOp(0xcc)])
            witness = [sign_message(self.key, hashlib.sha256(message).digest()), message]
        elif mode == 'empty-signature':
            script = CScript([self.public, CScriptOp(0xcc), OP_NOT])
            witness = [b'', message]
        elif mode == 'twice':
            script = CScript([self.public, CScriptOp(0xcc), OP_VERIFY, self.public, CScriptOp(0xcc)])
            witness = [sign_message(self.key, message), message] * 2
        else:
            script = CScript([self.public, CScriptOp(0xcc)])
            witness = [sign_message(self.key, message), message]
        tap = taproot_construct(self.public, [('test', script)])
        funded = self.wallet.send_to(from_node=self.nodes[0], scriptPubKey=tap.scriptPubKey, amount=100000)
        self.generate(self.wallet, 1)
        tx.vin[0].prevout = COutPoint(int(funded['txid'], 16), funded['sent_vout'])
        control = bytes([0xc0 | tap.negflag]) + self.public + tap.leaves['test'].merklebranch
        tx.wit.vtxinwit = [CTxInWitness()]
        tx.wit.vtxinwit[0].scriptWitness.stack = witness + [script, control]
        return tx.serialize().hex()

    def run_test(self):
        self.wallet = MiniWallet(self.nodes[0])
        self.generate(self.wallet, 105)
        self.key = (42).to_bytes(32, 'big')
        self.public = compute_xonly_pubkey(self.key)[0]
        for mode, sizes in [('witness', (0, 32, 33, 80)), ('script', (32, 33, 256)),
                            ('template', (0,)), ('hash', (80,)), ('empty-signature', (33,)), ('twice', (32,))]:
            for size in sizes:
                raw = self.make_spend(b'm' * size, mode)
                for node in self.nodes:
                    assert node.testmempoolaccept([raw])[0]['allowed']


if __name__ == '__main__':
    CSFSPolicyTest(__file__).main()
