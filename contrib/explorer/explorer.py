#!/usr/bin/env python3
"""Small signet explorer: private RPC collector, separate read-only HTTP process."""
import argparse
import base64
from contextlib import closing
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from pathlib import Path
import re
import sqlite3
import threading
import time
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

CHALLENGE = '2102396d38e3ff703be31a2d97317835f4e9645b5ae5ea2d2d1ba406afa7ab185b5fac'
HEX = re.compile(r'^[0-9a-f]{64}$')
SCHEMA = '''
CREATE TABLE IF NOT EXISTS blocks(height INTEGER PRIMARY KEY, hash TEXT UNIQUE NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS txs(txid TEXT PRIMARY KEY, height INTEGER, position INTEGER, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS tx_height ON txs(height, position);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
'''


def sats(value):
    return int(Decimal(str(value)) * 100_000_000)


class RPC:
    def __init__(self, cookie, url):
        self.cookie, self.url = Path(cookie), url

    def __call__(self, method, *params):
        # This allowlist is defense in depth; no HTTP request reaches this object.
        if method not in {'getblockchaininfo', 'getblockhash', 'getblock', 'getrawmempool', 'getrawtransaction'}:
            raise ValueError('Non-public RPC method refused')
        token = base64.b64encode(self.cookie.read_bytes().strip()).decode()
        body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode()
        req = Request(self.url, body, {'Authorization': 'Basic ' + token, 'Content-Type': 'application/json'})
        with urlopen(req, timeout=10) as response:
            raw = response.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024:
            raise ValueError('RPC response too large')
        value = json.loads(raw, parse_float=Decimal)
        if value.get('error'):
            raise RuntimeError('RPC request failed')
        return value['result']


def transaction(db, tx, height, timestamp, blockhash=None):
    outputs = [{'n': o['n'], 'value': sats(o['value']), 'address': o['scriptPubKey'].get('address'),
                'type': o['scriptPubKey'].get('type'), 'asm': o['scriptPubKey'].get('asm', ''),
                'script': o['scriptPubKey']['hex']} for o in tx['vout']]
    inputs, total_in, known, coinbase = [], 0, True, False
    for i in tx['vin']:
        if 'coinbase' in i:
            coinbase = True
            inputs.append({'coinbase': True, 'script': i['coinbase']})
            continue
        prev = db.execute('SELECT data FROM txs WHERE txid=?', (i['txid'],)).fetchone()
        output = next((o for o in json.loads(prev[0])['outputs'] if o['n'] == i['vout']), None) if prev else None
        if output:
            total_in += output['value']
        else:
            known = False
        inputs.append({'txid': i['txid'], 'vout': i['vout'], 'value': output['value'] if output else None,
                       'address': output.get('address') if output else None, 'sequence': i.get('sequence'),
                       'script': i.get('scriptSig', {}).get('hex', ''), 'witness': i.get('txinwitness', [])})
    total = sum(o['value'] for o in outputs)
    fee = total_in - total if known and not coinbase else None
    return {'txid': tx['txid'], 'height': height, 'blockhash': blockhash, 'time': timestamp,
            'version': tx['version'], 'locktime': tx['locktime'], 'size': tx['size'],
            'vsize': tx['vsize'], 'weight': tx['weight'], 'coinbase': coinbase,
            'total': total, 'fee': fee, 'inputs': inputs, 'outputs': outputs}


def brief(tx):
    return {k: tx[k] for k in ('txid', 'height', 'time', 'vsize', 'fee', 'total', 'coinbase')}


class Collector:
    def __init__(self, db_path, rpc):
        self.db = sqlite3.connect(db_path, timeout=10)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript(SCHEMA)
        self.rpc = rpc

    def sync(self):
        db, rpc = self.db, self.rpc
        info = rpc('getblockchaininfo')
        if info['chain'] != 'signet' or info.get('signet_challenge') != CHALLENGE:
            raise ValueError('Wrong network')
        node_height = info['blocks']
        tip = db.execute('SELECT COALESCE(MAX(height), -1) FROM blocks').fetchone()[0]
        common = tip
        while common >= 0:
            row = db.execute('SELECT hash FROM blocks WHERE height=?', (common,)).fetchone()
            if common <= node_height and row[0] == rpc('getblockhash', common):
                break
            common -= 1
        if common != tip:
            with db:
                db.execute('DELETE FROM txs WHERE height>? OR height IS NULL', (common,))
                db.execute('DELETE FROM blocks WHERE height>?', (common,))
        for height in range(common + 1, min(node_height, common + 100) + 1):
            blockhash = rpc('getblockhash', height)
            b = rpc('getblock', blockhash, 2)
            if height > 0:
                parent = db.execute('SELECT hash FROM blocks WHERE height=?', (height - 1,)).fetchone()
                if not parent or parent[0] != b['previousblockhash']:
                    raise RuntimeError('Chain changed while indexing')
            with db:
                fees, fees_known = 0, True
                for pos, tx in enumerate(b['tx']):
                    t = transaction(db, tx, height, b['time'], blockhash)
                    db.execute('INSERT OR REPLACE INTO txs VALUES(?,?,?,?)', (t['txid'], height, pos, json.dumps(t)))
                    if not t['coinbase']:
                        if t['fee'] is None:
                            fees_known = False
                        else:
                            fees += t['fee']
                summary = {'height': height, 'hash': blockhash, 'time': b['time'], 'size': b['size'],
                           'weight': b['weight'], 'tx_count': len(b['tx']), 'bits': b['bits'],
                           'previous': b.get('previousblockhash'), 'merkle_root': b['merkleroot'],
                           'fees': fees if fees_known else None}
                db.execute('INSERT INTO blocks VALUES(?,?,?)', (height, blockhash, json.dumps(summary)))
        mempool = rpc('getrawmempool', True)
        pending = []
        # Bound collection independently of public request volume. Parents first.
        sample = sorted(mempool, key=lambda x: mempool[x].get('ancestorcount', 1))[:200]
        for txid in sample:
            try:
                tx = rpc('getrawtransaction', txid, True)
                t = transaction(db, tx, None, mempool[txid]['time'])
                t['fee'] = sats(mempool[txid]['fees']['base'])
                pending.append(t)
            except Exception:
                continue  # Transaction may have confirmed or left the mempool.
        with db:
            db.execute('DELETE FROM txs WHERE height IS NULL')
            for t in pending:
                # Do not overwrite a confirmed transaction after a racing block.
                db.execute('INSERT OR IGNORE INTO txs VALUES(?,NULL,0,?)', (t['txid'], json.dumps(t)))
            indexed = db.execute('SELECT MAX(height) FROM blocks').fetchone()[0]
            status = {'network': 'Paperclip Bitcoin signet', 'node_height': node_height, 'indexed_height': indexed,
                      'mempool_count': len(mempool), 'mempool_indexed': len(pending),
                      'mempool_vsize': sum(e['vsize'] for e in mempool.values()), 'updated': int(time.time()),
                      'transactions': db.execute('SELECT COUNT(*) FROM txs WHERE height IS NOT NULL').fetchone()[0]}
            db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', ('status', json.dumps(status)))
        return indexed == node_height


def open_readonly(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True, timeout=2)
    db.execute('PRAGMA query_only=ON')
    return db


def api(db, path, query):
    status_row = db.execute("SELECT value FROM meta WHERE key='status'").fetchone()
    if not status_row:
        return 503, {'error': 'Index is starting'}
    status = json.loads(status_row[0])
    status['delayed'] = time.time() - status['updated'] > 45
    if path == '/api/status':
        return 200, status
    if path == '/api/blocks':
        before = int(query.get('before', [str(status['indexed_height'] + 1)])[0])
        if not 0 <= before <= 2_147_483_647:
            raise ValueError('Invalid height')
        return 200, [json.loads(r[0]) for r in db.execute('SELECT data FROM blocks WHERE height<? ORDER BY height DESC LIMIT 25', (before,))]
    if path == '/api/mempool':
        return 200, [brief(json.loads(r[0])) for r in db.execute('SELECT data FROM txs WHERE height IS NULL ORDER BY txid LIMIT 200')]
    if path.startswith('/api/block/'):
        value = path.removeprefix('/api/block/')
        if value.isdigit() and len(value) < 11:
            row = db.execute('SELECT data FROM blocks WHERE height=?', (int(value),)).fetchone()
        elif HEX.fullmatch(value):
            row = db.execute('SELECT data FROM blocks WHERE hash=?', (value,)).fetchone()
        else:
            raise ValueError('Invalid block identifier')
        if not row:
            return 404, {'error': 'Block not found'}
        block = json.loads(row[0])
        offset = int(query.get('offset', ['0'])[0])
        if not 0 <= offset <= 100_000:
            raise ValueError('Invalid offset')
        block['transactions'] = [brief(json.loads(r[0])) for r in db.execute('SELECT data FROM txs WHERE height=? ORDER BY position LIMIT 25 OFFSET ?', (block['height'], offset))]
        block['offset'] = offset
        block['confirmations'] = status['indexed_height'] - block['height'] + 1
        return 200, block
    if path.startswith('/api/tx/'):
        txid = path.removeprefix('/api/tx/')
        if not HEX.fullmatch(txid):
            raise ValueError('Invalid transaction ID')
        row = db.execute('SELECT data FROM txs WHERE txid=?', (txid,)).fetchone()
        if not row:
            return 404, {'error': 'Transaction not found in the indexed chain or recent mempool snapshot'}
        tx = json.loads(row[0])
        tx['confirmations'] = 0 if tx['height'] is None else status['indexed_height'] - tx['height'] + 1
        return 200, tx
    return 404, {'error': 'Not found'}


class BoundedServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, *args):
        self.slots = threading.BoundedSemaphore(12)
        super().__init__(*args)

    def process_request(self, request, address):
        if not self.slots.acquire(False):
            request.close()
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


def serve(db_path, port):
    static = Path(__file__).parent / 'static'
    files = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'),
             '/style.css': ('style.css', 'text/css'), '/brand.svg': ('brand.svg', 'image/svg+xml')}

    class Handler(BaseHTTPRequestHandler):
        server_version = 'PaperclipExplorer'
        sys_version = ''

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *args):
            pass

        def do_GET(self):
            if len(self.path) > 512:
                self.send_error(414)
                return
            url = urlsplit(self.path)
            try:
                if url.path in files:
                    name, mime = files[url.path]
                    body = (static / name).read_bytes()
                    code = 200
                else:
                    with closing(open_readonly(db_path)) as db:
                        db.execute('BEGIN')  # Consistent snapshot across reorgs/updates.
                        code, value = api(db, url.path, parse_qs(url.query, max_num_fields=4))
                    body, mime = json.dumps(value).encode(), 'application/json'
            except (ValueError, OverflowError):
                code, body, mime = 400, b'{"error":"Invalid request"}', 'application/json'
            except Exception:
                code, body, mime = 503, b'{"error":"Explorer index temporarily unavailable"}', 'application/json'
            self.send_response(code)
            self.send_header('Content-Type', mime + '; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store' if mime == 'application/json' else 'public, max-age=300')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)

        do_HEAD = do_GET

    BoundedServer(('127.0.0.1', port), Handler).serve_forever()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['collect', 'serve'])
    parser.add_argument('--db', required=True)
    parser.add_argument('--cookie')
    parser.add_argument('--rpc', default='http://127.0.0.1:48332/')
    parser.add_argument('--port', type=int, default=48400)
    args = parser.parse_args()
    if args.mode == 'serve':
        serve(args.db, args.port)
        return
    collector = Collector(args.db, RPC(args.cookie, args.rpc))
    while True:
        try:
            caught_up = collector.sync()
            time.sleep(10 if caught_up else 1)
        except Exception as e:
            logging.error('Collector retry: %s', type(e).__name__)
            time.sleep(10)


if __name__ == '__main__':
    main()
