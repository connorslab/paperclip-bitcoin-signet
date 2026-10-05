import copy
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from explorer import Collector, CHALLENGE, RPC, api


def tx(txid, inputs=None, value='50'):
    return {'txid': txid, 'vin': inputs or [{'coinbase': '0101'}],
            'vout': [{'n': 0, 'value': Decimal(value), 'scriptPubKey': {'hex': '51', 'type': 'nonstandard'}}],
            'version': 2, 'locktime': 0, 'size': 100, 'vsize': 90, 'weight': 360}


class FakeRPC:
    def __init__(self):
        self.blocks = []
        self.pending = {}
        self.add('a' * 64, [tx('1' * 64)])
        self.add('b' * 64, [tx('2' * 64), tx('3' * 64, [{'txid': '1' * 64, 'vout': 0}], '49.99999')])

    def add(self, blockhash, transactions):
        self.blocks.append({'hash': blockhash, 'time': 100 + len(self.blocks), 'size': 1000,
                            'weight': 4000, 'bits': '207fffff', 'merkleroot': '0' * 64,
                            'previousblockhash': self.blocks[-1]['hash'] if self.blocks else None, 'tx': transactions})

    def __call__(self, method, *args):
        if method == 'getblockchaininfo':
            return {'chain': 'signet', 'signet_challenge': CHALLENGE, 'blocks': len(self.blocks)-1}
        if method == 'getblockhash':
            return self.blocks[args[0]]['hash']
        if method == 'getblock':
            return copy.deepcopy(next(b for b in self.blocks if b['hash'] == args[0]))
        if method == 'getrawmempool':
            return {k: {'ancestorcount': 1, 'time': 123, 'vsize': 90, 'fees': {'base': Decimal('0.00002')}} for k in self.pending}
        if method == 'getrawtransaction':
            return self.pending[args[0]]
        raise AssertionError(method)


class ExplorerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rpc = FakeRPC()
        self.path = Path(self.tmp.name) / 'index.sqlite'
        self.collector = Collector(self.path, self.rpc)

    def tearDown(self):
        self.collector.db.close()
        self.tmp.cleanup()

    def test_accounting_pagination_and_persistence(self):
        self.collector.sync()
        db = self.collector.db
        code, result = api(db, '/api/tx/' + '3'*64, {})
        self.assertEqual((code, result['fee'], result['confirmations']), (200, 1000, 1))
        self.assertEqual(result['inputs'][0]['value'], 5_000_000_000)
        self.assertEqual(api(db, '/api/block/1', {})[1]['fees'], 1000)
        self.assertEqual(len(api(db, '/api/blocks', {'before': ['1']})[1]), 1)
        self.collector.db.close()
        self.collector = Collector(self.path, self.rpc)
        self.collector.sync()
        self.assertEqual(api(self.collector.db, '/api/status', {})[1]['transactions'], 3)

    def test_reorg_removes_orphan_transactions(self):
        self.collector.sync()
        self.rpc.blocks.pop()
        self.rpc.add('c'*64, [tx('4'*64)])
        self.collector.sync()
        self.assertEqual(api(self.collector.db, '/api/tx/' + '3'*64, {})[0], 404)
        self.assertEqual(api(self.collector.db, '/api/block/1', {})[1]['hash'], 'c'*64)

    def test_mempool_confirmation_and_eviction(self):
        self.rpc.pending['5'*64] = tx('5'*64, [{'txid': '3'*64, 'vout': 0}], '49.99997')
        self.collector.sync()
        self.assertEqual(api(self.collector.db, '/api/tx/'+'5'*64, {})[1]['fee'], 2000)
        self.rpc.add('d'*64, [tx('6'*64), self.rpc.pending.pop('5'*64)])
        self.collector.sync()
        self.assertEqual(api(self.collector.db, '/api/tx/'+'5'*64, {})[1]['height'], 2)
        self.assertEqual(api(self.collector.db, '/api/mempool', {})[1], [])

    def test_no_rpc_proxy_or_unbounded_queries(self):
        self.collector.sync()
        for path in ['/api/wallet', '/api/getblockchaininfo', '/../../etc/passwd']:
            self.assertEqual(api(self.collector.db, path, {})[0], 404)
        for path, query in [('/api/block/nope', {}), ('/api/tx/'+"' OR 1=1--", {}),
                            ('/api/block/0', {'offset':['9999999999999999999999999']})]:
            with self.assertRaises(ValueError):
                api(self.collector.db, path, query)
        with self.assertRaises(ValueError):
            RPC('/does-not-exist', 'http://127.0.0.1/')("sendtoaddress", 'anything')


if __name__ == '__main__':
    unittest.main()
