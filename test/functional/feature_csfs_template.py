#!/usr/bin/env python3
# Copyright (c) 2026 The Bitcoin developers
# Distributed under the MIT software license, see COPYING.
"""Template-only CSFS: early relay enforcement, historical blocks and activation."""
from mempool_csfs_policy import CSFSPolicyTest, compute_xonly_pubkey
from test_framework.wallet import MiniWallet
from test_framework.util import assert_equal, assert_raises_rpc_error


class TemplateTest(CSFSPolicyTest):
    def set_test_params(self):
        self.num_nodes = 2
        self.setup_clean_chain = True
        base = ['-btccovtest', '-testactivationheight=blake2b@1', '-rdtsexpiry=2147483647']
        # Node 0 emulates the old rules and supplies historical/invalid blocks.
        self.extra_args = [base + ['-testactivationheight=csfstemplate@-1'],
                           base + ['-testactivationheight=csfstemplate@140']]

    def run_test(self):
        old, new = self.nodes
        self.wallet = MiniWallet(old)
        self.generate(self.wallet, 105)
        self.key = (42).to_bytes(32, 'big')
        self.public = compute_xonly_pubkey(self.key)[0]
        for mode, size in [('witness', 0), ('witness', 31), ('witness', 32),
                           ('witness', 33), ('witness', 64), ('witness', 80), ('script', 32), ('hash', 80),
                           ('empty-signature', 32), ('twice', 32)]:
            raw = self.make_spend(b'm' * size, mode)
            assert old.testmempoolaccept([raw])[0]['allowed']
            for _ in range(2):
                verdict = new.testmempoolaccept([raw])[0]
                assert not verdict['allowed']
                assert 'current input template hash' in str(verdict)
            assert_raises_rpc_error(-26, 'current input template hash', new.sendrawtransaction, raw)
        # A valid pre-activation arbitrary-message block remains valid forever.
        txid = old.sendrawtransaction(raw)
        self.generate(self.wallet, 1)
        assert_equal(new.getbestblockhash(), old.getbestblockhash())
        assert txid not in new.getrawmempool()
        # Populate caches from historical validation; mempool must still reject.
        block = new.getbestblockhash()
        new.invalidateblock(block)
        assert not new.testmempoolaccept([raw])[0]['allowed']
        new.reconsiderblock(block)
        self.sync_blocks()
        # Value equality, not opcode provenance; empty signatures still need
        # the right message and can be used as false in composed scripts.
        for mode in ('template-empty', 'template-literal'):
            matching = self.make_spend(b'', mode)
            assert new.testmempoolaccept([matching])[0]['allowed']
            old.sendrawtransaction(matching)
            self.generate(self.wallet, 1)
        # Prepare a second arbitrary-message spend whose UTXO is confirmed.
        bad = self.make_spend(b'n' * 32)
        good = self.make_spend(b'', 'template')
        self.generate(self.wallet, 139 - old.getblockcount())
        self.disconnect_nodes(0, 1)
        old.sendrawtransaction(bad)
        invalid_hash = self.generate(self.wallet, 1, sync_fun=lambda: None)[0]
        assert_equal(old.getblockcount(), 140)
        reason = new.submitblock(old.getblock(invalid_hash, 0))
        assert reason is not None
        assert_equal(new.getblockcount(), 139)
        old.invalidateblock(invalid_hash)
        assert new.testmempoolaccept([good])[0]['allowed']
        new.sendrawtransaction(good)
        new_wallet = MiniWallet(new)
        accepted = self.generate(new_wallet, 1, sync_fun=lambda: None)[0]
        assert_equal(new.getblockcount(), 140)
        assert_equal(old.submitblock(new.getblock(accepted, 0)), None)
        # Rule remains active after restart.
        self.restart_node(1)
        assert new.verifychain(4, 0)
        assert not new.testmempoolaccept([bad])[0]['allowed']
        assert_equal(new.getblockcount(), 140)


if __name__ == '__main__':
    TemplateTest(__file__).main()
