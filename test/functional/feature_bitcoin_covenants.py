#!/usr/bin/env python3
# Copyright (c) 2026 The Paperclip developers
# Distributed under the MIT software license, see COPYING.
"""Experimental covenant spends under active Blake2b/RDTS, using default relay policy."""
import hashlib
import struct
from test_framework.test_framework import BitcoinTestFramework
from test_framework.wallet import MiniWallet
from test_framework.key import compute_xonly_pubkey, sign_schnorr
from test_framework.messages import CTransaction, CTxIn, CTxOut, COutPoint, CTxInWitness
from test_framework.script import CScript, CScriptOp, OP_EQUAL, taproot_construct
from test_framework.util import assert_equal


def template_hash(tx):
    tag = hashlib.sha256(b'TemplateHash').digest()
    data = struct.pack('<II', tx.version, tx.nLockTime)
    data += hashlib.sha256(b''.join(struct.pack('<I', i.nSequence) for i in tx.vin)).digest()
    data += hashlib.sha256(b''.join(o.serialize() for o in tx.vout)).digest()
    data += b'\x00' + struct.pack('<I', 0)
    return hashlib.sha256(tag + tag + data).digest()


class CovenantTest(BitcoinTestFramework):
    def set_test_params(self):
        self.num_nodes = 1
        self.setup_clean_chain = True
        self.extra_args = [['-btccovtest', '-testactivationheight=blake2b@1', '-rdtsexpiry=2147483647']]

    def run_test(self):
        node = self.nodes[0]
        wallet = MiniWallet(node)
        self.generate(wallet, 105)
        # The same INTERNALKEY script works with distinct internal keys.
        for mode, secret in ((0, 42), (1, 42), (2, 42), (2, 43)):
            key = secret.to_bytes(32, 'big')
            pubkey = compute_xonly_pubkey(key)[0]
            tx = CTransaction()
            tx.version = 2
            tx.vin = [CTxIn(COutPoint(0, 1), nSequence=0xfffffffd)]
            tx.vout = [CTxOut(99000, wallet.get_output_script())]
            expected = template_hash(tx)
            if mode == 2:
                script = CScript([CScriptOp(0xce), CScriptOp(0xcb), CScriptOp(0xcc)])
            elif mode == 1:
                script = CScript([CScriptOp(0xce), pubkey, CScriptOp(0xcc)])
            else:
                script = CScript([CScriptOp(0xce), expected, OP_EQUAL])
            tap = taproot_construct(pubkey, [('test', script)])
            funded = wallet.send_to(from_node=node, scriptPubKey=tap.scriptPubKey, amount=100000)
            self.generate(wallet, 1)
            tx.vin[0].prevout = COutPoint(int(funded['txid'], 16), funded['sent_vout'])
            control = bytes([0xc0 | tap.negflag]) + pubkey + tap.leaves['test'].merklebranch
            witness = [sign_schnorr(key, expected)] if mode else []
            tx.wit.vtxinwit = [CTxInWitness()]
            tx.wit.vtxinwit[0].scriptWitness.stack = witness + [script, control]
            assert_equal(node.testmempoolaccept([tx.serialize().hex()])[0]['allowed'], True)
            tx.vout[0].nValue -= 1
            assert_equal(node.testmempoolaccept([tx.serialize().hex()])[0]['allowed'], False)
            tx.vout[0].nValue += 1
            txid = node.sendrawtransaction(tx.serialize().hex())
            block = self.generate(wallet, 1)[0]
            assert txid in node.getblock(block)['tx']
        self.restart_node(0)
        assert_equal(node.verifychain(), True)

if __name__ == '__main__':
    CovenantTest(__file__).main()
