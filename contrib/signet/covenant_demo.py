#!/usr/bin/env python3
"""Spend test coins through TEMPLATEHASH + CSFS. Dedicated test wallet required."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'test/functional'))
from test_framework.key import compute_xonly_pubkey, sign_schnorr
from test_framework.messages import CTransaction, CTxIn, CTxOut, COutPoint, CTxInWitness
from test_framework.script import CScript, CScriptOp, taproot_construct
from test_framework.segwit_addr import encode_segwit_address

parser = argparse.ArgumentParser()
parser.add_argument('--cli', required=True)
parser.add_argument('--datadir', required=True)
parser.add_argument('--wallet', required=True)
args = parser.parse_args()
base = [args.cli, '-datadir=' + args.datadir, '-rpcwallet=' + args.wallet]
def rpc(method, *params):
    raw = subprocess.check_output(base + [method] + list(params), text=True).strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw

info = rpc('getblockchaininfo')
assert info['chain'] == 'signet'
assert info['signet_challenge'] == '2102396d38e3ff703be31a2d97317835f4e9645b5ae5ea2d2d1ba406afa7ab185b5fac', 'Wrong test network'
assert rpc('getnetworkinfo')['subversion'], 'Missing node version'
# Deliberately public demonstration signing key. Never use for real funds.
secret = (42).to_bytes(32, 'big')
pubkey = compute_xonly_pubkey(secret)[0]
# BIP341 NUMS internal key removes the known-key taproot bypass.
internal = bytes.fromhex('50929b74c1a04954b78b4b6035e97a5e078a5a0f28ec96d547bfee9ace803ac0')
script = CScript([CScriptOp(0xce), pubkey, CScriptOp(0xcc)])
tap = taproot_construct(internal, [('covenant', script)])
address = encode_segwit_address('tb', 1, tap.output_pubkey)
return_address = rpc('getnewaddress', 'covenant-return', 'bech32m')
return_script = bytes.fromhex(rpc('getaddressinfo', return_address)['scriptPubKey'])
funding = rpc('-named', 'sendtoaddress', 'address=' + address, 'amount=0.001', 'fee_rate=1')
decoded = rpc('decoderawtransaction', rpc('gettransaction', funding)['hex'])
index = next(o['n'] for o in decoded['vout'] if o['scriptPubKey']['hex'] == tap.scriptPubKey.hex())
tx = CTransaction()
tx.vin = [CTxIn(COutPoint(int(funding, 16), index), nSequence=0xfffffffd)]
tx.vout = [CTxOut(99000, return_script)]
tag = hashlib.sha256(b'TemplateHash').digest()
data = struct.pack('<II', tx.version, tx.nLockTime)
data += hashlib.sha256(struct.pack('<I', tx.vin[0].nSequence)).digest()
data += hashlib.sha256(tx.vout[0].serialize()).digest()
data += b'\x00' + struct.pack('<I', 0)
digest = hashlib.sha256(tag + tag + data).digest()
control = bytes([0xc0 | tap.negflag]) + internal + tap.leaves['covenant'].merklebranch
tx.wit.vtxinwit = [CTxInWitness()]
tx.wit.vtxinwit[0].scriptWitness.stack = [sign_schnorr(secret, digest), script, control]
valid = rpc('testmempoolaccept', json.dumps([tx.serialize().hex()]))[0]
assert valid['allowed'], valid
tx.vout[0].nValue -= 1
invalid = rpc('testmempoolaccept', json.dumps([tx.serialize().hex()]))[0]
assert not invalid['allowed'], invalid
tx.vout[0].nValue += 1
spending = rpc('sendrawtransaction', tx.serialize().hex())
print(json.dumps({'funding_txid': funding, 'covenant_spend_txid': spending, 'template_hash': digest.hex(), 'altered_output_rejection': invalid, 'status': 'broadcast; verify confirmation separately'}, indent=2))
