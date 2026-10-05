import tempfile
import time
import unittest
import uuid
from pathlib import Path
from faucet import Faucet, Rejected, CHALLENGE, AMOUNT, DAILY_CAP


class FakeRPC:
    def __init__(self):
        self.sends = 0
        self.fail = False
        self.chain = 'signet'

    def __call__(self, method, params=None):
        if method == 'getblockchaininfo':
            return dict(chain=self.chain, signet_challenge=CHALLENGE, initialblockdownload=False, time=time.time())
        if method == 'validateaddress':
            return dict(isvalid=params['address'].startswith('tb1'), scriptPubKey=params['address'].encode().hex())
        if method == 'getbalances':
            return {'mine': {'trusted': 10}}
        if method == 'sendtoaddress':
            self.sends += 1
            assert params['fee_rate'] == 1
            if self.fail:
                raise TimeoutError()
            return 'a' * 64
        raise AssertionError(method)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'claims.sqlite'
        self.rpc = FakeRPC()
        self.f = Faucet(self.path, self.rpc, b'test')
        self.address = 'tb1qtestaddress12345'

    def tearDown(self):
        self.f.db.close()
        self.temp.cleanup()

    def claim(self, address=None, ip='192.0.2.1', key=None):
        return self.f.claim(key or str(uuid.uuid4()), address or self.address, ip)

    def test_persistent_idempotency_and_cooldown(self):
        key = str(uuid.uuid4())
        self.assertEqual(self.claim(key=key)['state'], 'sent')
        self.f.db.close()
        self.f = Faucet(self.path, self.rpc, b'test')
        self.assertEqual(self.claim(key=key)['txid'], 'a'*64)
        self.assertEqual(self.rpc.sends, 1)
        with self.assertRaises(Rejected):
            self.claim(ip='192.0.2.2')
        with self.assertRaises(Rejected):
            self.claim(address='tb1qdifferentaddress')

    def test_ambiguous_rpc_never_resends(self):
        self.rpc.fail = True
        key = str(uuid.uuid4())
        self.assertEqual(self.claim(key=key)['state'], 'pending')
        self.assertEqual(self.claim(key=key)['state'], 'pending')
        self.assertEqual(self.rpc.sends, 1)

    def test_network_and_address_rejection(self):
        self.rpc.chain = 'main'
        with self.assertRaises(Rejected):
            self.claim()
        self.rpc.chain = 'signet'
        with self.assertRaises(Rejected):
            self.claim(address='bc1qmainnetaddress')
        self.assertEqual(self.rpc.sends, 0)

    def test_global_cap_and_ipv6_prefix(self):
        self.assertEqual(self.f.identity('2001:db8::1'), self.f.identity('2001:db8::99'))
        for n in range(DAILY_CAP // AMOUNT):
            self.f.db.execute('INSERT INTO claims VALUES (?,?,?,?,?,NULL)', (str(n),str(n),str(n),int(time.time()),'pending'))
        self.f.db.commit()
        with self.assertRaises(Rejected):
            self.claim()
        self.assertEqual(self.rpc.sends, 0)


if __name__ == '__main__':
    unittest.main()
