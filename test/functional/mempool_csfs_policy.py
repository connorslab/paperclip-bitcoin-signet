#!/usr/bin/env python3
# Copyright (c) 2026 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""A default-enabled CSFS message cap is local policy, never a block validity rule."""

import hashlib

from feature_xbt_covenants import template_hash
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
        self.base_args = ['-xbtcovtest', '-testactivationheight=blake2b@1', '-rdtsexpiry=2147483647']
        # Omit the option on the capped node to test the default, not an override.
        self.extra_args = [self.base_args + ['-maxcsfsmsgsize=-1'], self.base_args]

    def make_spend(self, message, mode='witness'):
        tx = CTransaction()
        tx.version = 2
        tx.vin = [CTxIn(COutPoint(0, 1), nSequence=0xfffffffd)]
        tx.vout = [CTxOut(99000, self.wallet.get_output_script())]
        if mode == 'template':
            message = template_hash(tx)
            script = CScript([CScriptOp(0xce), self.public, CScriptOp(0xcc)])
            witness = [sign_message(self.key, message)]
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

    def check_policy(self, raw, allowed):
        # Repeat to cover the transaction validation/signature caches.
        for _ in range(2):
            assert_equal(self.nodes[0].testmempoolaccept([raw])[0]['allowed'], True)
            result = self.nodes[1].testmempoolaccept([raw])[0]
            assert_equal(result['allowed'], allowed)
            if not allowed:
                assert_equal(result['reject-reason'], 'csfs-message-size')

    def run_test(self):
        uncapped, capped = self.nodes
        self.wallet = MiniWallet(uncapped)
        self.generate(self.wallet, 105)
        self.key = (42).to_bytes(32, 'big')
        self.public = compute_xonly_pubkey(self.key)[0]

        self.log.info('Witness and script messages: empty, boundary, and oversized')
        samples = {}
        for mode, sizes in [('witness', (0, 32, 33, 80)), ('script', (32, 33, 256))]:
            for size in sizes:
                raw = self.make_spend(b'm' * size, mode)
                samples[mode, size] = raw
                self.check_policy(raw, size <= 32)

        self.log.info('TEMPLATEHASH/CSFS remains relayable with the 32-byte cap')
        self.check_policy(self.make_spend(b'', 'template'), True)
        self.log.info('Cap applies to the actual message, not the preimage or 64-byte signature')
        self.check_policy(self.make_spend(b'p' * 80, 'hash'), True)
        self.log.info('Each executed message is capped, including an empty-signature call')
        self.check_policy(self.make_spend(b'm' * 33, 'empty-signature'), False)
        self.check_policy(self.make_spend(b'm' * 32, 'twice'), True)

        self.log.info('Restart with zero: empty messages allowed, nonempty rejected')
        self.restart_node(1, self.base_args + ['-maxcsfsmsgsize=0'])
        self.connect_nodes(0, 1)
        self.check_policy(samples['witness', 0], True)
        self.check_policy(samples['witness', 32], False)

        self.log.info('Explicit -1 disables the extra cap; 520 is accepted')
        for limit in (-1, 520):
            self.restart_node(1, self.base_args + [f'-maxcsfsmsgsize={limit}'])
            self.connect_nodes(0, 1)
            self.check_policy(samples['script', 256], True)

        # Persist an over-cap transaction while permitted, then reload under 32.
        persisted_txid = capped.sendrawtransaction(samples['script', 256])
        assert persisted_txid in capped.getrawmempool()

        self.log.info('Invalid configuration fails startup instead of silently changing policy')
        self.stop_node(1)
        for limit in ('-2', '521', 'garbage', '32.5', '999999999999999999999'):
            capped.assert_start_raises_init_error(
                extra_args=self.base_args + [f'-maxcsfsmsgsize={limit}'],
                expected_msg='Error: Invalid -maxcsfsmsgsize: use -1 to disable, or a byte limit from 0 to 520',
            )
        self.start_node(1, self.base_args + ['-maxcsfsmsgsize=32'])
        self.connect_nodes(0, 1)
        assert persisted_txid not in capped.getrawmempool()

        self.log.info('Over-cap tx cannot enter local mempool/template but is valid in a block')
        raw = samples['script', 256]
        assert_raises_rpc_error(-26, 'csfs-message-size', capped.sendrawtransaction, raw)
        txid = uncapped.sendrawtransaction(raw)
        assert txid not in capped.getrawmempool()
        assert txid not in [tx['txid'] for tx in capped.getblocktemplate({'rules': ['segwit', 'blake2b']})['transactions']]
        block = self.generate(self.wallet, 1, sync_fun=self.sync_blocks)[0]
        assert txid in capped.getblock(block)['tx']
        assert_equal(capped.getbestblockhash(), block)

        self.log.info('Reorg re-admission still enforces local policy after block validation')
        capped.invalidateblock(block)
        assert txid not in capped.getrawmempool()
        for _ in range(2):
            assert_equal(capped.testmempoolaccept([raw])[0]['reject-reason'], 'csfs-message-size')
        capped.reconsiderblock(block)
        self.sync_blocks()
        self.restart_node(1, self.base_args + ['-maxcsfsmsgsize=32'])
        assert_equal(capped.getbestblockhash(), block)
        assert_equal(capped.verifychain(), True)


if __name__ == '__main__':
    CSFSPolicyTest(__file__).main()
