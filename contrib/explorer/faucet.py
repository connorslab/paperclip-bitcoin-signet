#!/usr/bin/env python3
"""Bounded signet-only faucet. Uncertain sends are never retried automatically."""
import hashlib
import hmac
import ipaddress
import json
import os
import sqlite3
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
import base64

CHALLENGE = '2102396d38e3ff703be31a2d97317835f4e9645b5ae5ea2d2d1ba406afa7ab185b5fac'
ORIGIN = 'https://node2.paperclippool.xyz'
AMOUNT = 1_000_000  # 0.01 test BTC
DAILY_CAP = 100_000_000
COOLDOWN = 86400
WALLET = 'public-faucet'


class Rejected(Exception):
    pass


class RPC:
    def __call__(self, method, params=None):
        cookie = Path('/var/lib/paperclip-xbt-signet/signet/.cookie').read_text().strip()
        auth = base64.b64encode(cookie.encode()).decode()
        req = Request('http://127.0.0.1:48332/wallet/' + WALLET,
                      json.dumps({'jsonrpc': '2.0', 'id': 'faucet', 'method': method,
                                  'params': params or {}}).encode(),
                      {'Authorization': 'Basic ' + auth, 'Content-Type': 'application/json'})
        with urlopen(req, timeout=20) as response:
            result = json.load(response)
        if result.get('error'):
            raise RuntimeError('Node RPC rejected request')
        return result['result']


class Faucet:
    def __init__(self, path, rpc, salt):
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS claims (id TEXT PRIMARY KEY, ip TEXT NOT NULL, destination TEXT NOT NULL, created INTEGER NOT NULL, state TEXT NOT NULL, txid TEXT)')
        self.rpc, self.salt = rpc, salt

    def identity(self, ip):
        address = ipaddress.ip_address(ip)
        if address.version == 6:
            if address.ipv4_mapped:
                address = address.ipv4_mapped
            else:
                address = ipaddress.ip_network(str(address) + '/64', strict=False).network_address
        return hmac.new(self.salt, str(address).encode(), hashlib.sha256).hexdigest()

    def claim(self, request_id, address, ip):
        if not isinstance(request_id, str) or str(uuid.UUID(request_id)) != request_id:
            raise Rejected('Invalid request ID.')
        if not isinstance(address, str) or not 14 <= len(address) <= 100 or address != address.strip():
            raise Rejected('Enter a valid Bitcoin signet address.')
        identity = self.identity(ip)
        existing = self.db.execute('SELECT ip,state,txid FROM claims WHERE id=?', (request_id,)).fetchone()
        if existing:
            if existing[0] != identity:
                raise Rejected('Request ID already used.')
            return {'state': existing[1], 'txid': existing[2], 'amount_sats': AMOUNT}
        chain = self.rpc('getblockchaininfo')
        if chain.get('chain') != 'signet' or chain.get('signet_challenge') != CHALLENGE or chain.get('initialblockdownload'):
            raise Rejected('Faucet unavailable: test network is not ready.')
        if time.time() - chain.get('time', 0) > 600:
            raise Rejected('Faucet paused while the test chain catches up.')
        valid = self.rpc('validateaddress', {'address': address})
        if not valid.get('isvalid'):
            raise Rejected('Enter a valid Bitcoin signet address (not a mainnet address).')
        destination = hashlib.sha256(bytes.fromhex(valid['scriptPubKey'])).hexdigest()
        now = int(time.time())
        # Persist authorization before the irreversible RPC. Even crashes and RPC
        # timeouts consume the allowance; an operator must reconcile these cases.
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if self.db.execute('SELECT 1 FROM claims WHERE created>? AND (ip=? OR destination=?)', (now-COOLDOWN, identity, destination)).fetchone():
                raise Rejected('One request per network/address every 24 hours. Please try again later.')
            count = self.db.execute('SELECT count(*) FROM claims WHERE created>?', (now-COOLDOWN,)).fetchone()[0]
            if (count + 1) * AMOUNT > DAILY_CAP:
                raise Rejected('The daily faucet limit has been reached. Please try again later.')
            balance = self.rpc('getbalances')['mine']['trusted']
            if balance < (AMOUNT + 10000) / 1e8:
                raise Rejected('Faucet temporarily empty. Please try again later.')
            self.db.execute('INSERT INTO claims VALUES (?,?,?,?,?,NULL)', (request_id, identity, destination, now, 'pending'))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        try:
            txid = self.rpc('sendtoaddress', {'address': address, 'amount': AMOUNT / 1e8,
                'comment': 'public-faucet:' + request_id, 'fee_rate': 1, 'subtractfeefromamount': False})
            if not isinstance(txid, str) or len(txid) != 64 or any(c not in '0123456789abcdef' for c in txid):
                raise RuntimeError('Invalid transaction response')
            self.db.execute("UPDATE claims SET state='sent',txid=? WHERE id=?", (txid, request_id))
            self.db.commit()
            return {'state': 'sent', 'txid': txid, 'amount_sats': AMOUNT}
        except Exception:
            # Never repeat a payment just because its response was lost.
            return {'state': 'pending', 'txid': None, 'amount_sats': AMOUNT}


def main():
    directory = Path('/var/lib/paperclip-signet-faucet')
    salt_file = directory / 'identity.key'
    if not salt_file.exists():
        with salt_file.open('xb') as stream:
            stream.write(os.urandom(32))
    faucet = Faucet(directory / 'claims.sqlite', RPC(), salt_file.read_bytes())

    class Handler(BaseHTTPRequestHandler):
        server_version = 'PaperclipFaucet'
        sys_version = ''

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *args):
            pass

        def reply(self, code, value):
            body = json.dumps(value).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            try:
                if self.path != '/signet/api/faucet' or self.headers.get('Origin') != ORIGIN:
                    return self.reply(403, {'error': 'Use the faucet form on the signet site.'})
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 512 or self.headers.get('Content-Type') != 'application/json' or self.headers.get('Transfer-Encoding'):
                    return self.reply(400, {'error': 'Invalid request.'})
                data = json.loads(self.rfile.read(length))
                # Caddy overwrites this header with the actual TCP client address.
                result = faucet.claim(data['id'], data['address'], self.headers['X-Faucet-Client'])
                self.reply(200 if result['state'] == 'sent' else 202, result)
            except Rejected as exc:
                self.reply(429, {'error': str(exc)})
            except (ValueError, KeyError, TypeError, AttributeError):
                self.reply(400, {'error': 'Invalid request.'})
            except Exception:
                self.reply(503, {'error': 'Faucet temporarily unavailable. Please try again later.'})

    HTTPServer(('127.0.0.1', 48401), Handler).serve_forever()


if __name__ == '__main__':
    main()
