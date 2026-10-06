#!/usr/bin/env python3
"""Test-only signet signer. Key path must refer to a dedicated, private test key.
Uses the upstream functional framework: never use this signer with real funds.
"""
import argparse
import importlib.machinery
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'test/functional'))
from test_framework.key import ECKey
from test_framework.messages import ser_string
from test_framework.script import CScript, OP_CHECKSIG, LegacySignatureHash, SIGHASH_ALL
miner = importlib.machinery.SourceFileLoader('signet_miner', str(ROOT / 'contrib/signet/miner')).load_module()


def signed_block(template, reward_script, secret):
    key = ECKey()
    key.set(secret, compressed=True)
    challenge = CScript([key.get_pubkey().get_bytes(), OP_CHECKSIG])
    if template['signet_challenge'] != challenge.hex():
        raise ValueError('Signer does not match configured challenge')
    psbt = miner.generate_psbt(template, reward_script)
    block, _ = miner.decode_psbt(psbt)
    spend, _ = miner.signet_txs(block, challenge)
    digest, error = LegacySignatureHash(challenge, spend, 0, SIGHASH_ALL)
    if error is not None:
        raise ValueError(error)
    signature = key.sign_ecdsa(digest) + bytes([SIGHASH_ALL])
    solution = ser_string(CScript([signature])) + b'\x00'
    return miner.finish_block(block, solution, None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cli', required=True)
    parser.add_argument('--datadir', required=True)
    parser.add_argument('--key-file', required=True)
    parser.add_argument('--reward-script-file', required=True)
    parser.add_argument('--interval', type=int, default=60)
    parser.add_argument('--count', type=int, default=0)
    args = parser.parse_args()
    if args.interval < 1:
        parser.error('interval must be positive')
    key_path = Path(args.key_file)
    if key_path.stat().st_mode & 0o077:
        raise ValueError('Test signer key must not be accessible to other users')
    secret = bytes.fromhex(key_path.read_text().strip())
    reward = bytes.fromhex(Path(args.reward_script_file).read_text().strip())
    command = [args.cli, '-datadir=' + args.datadir]
    def rpc(method, *params):
        raw = subprocess.check_output(command + [method] + list(params), text=True)
        return json.loads(raw) if raw.strip() else None
    made = 0
    while True:
        template = rpc('getblocktemplate', '{"rules":["signet","segwit","blake2b","rdts"]}')
        block = signed_block(template, reward, secret)
        result = rpc('submitblock', block.serialize().hex())
        if result is not None:
            raise RuntimeError('Block rejected: ' + str(result))
        made += 1
        print(json.dumps({'height': template['height'], 'hash': block.hash}), flush=True)
        if args.count and made >= args.count:
            return
        time.sleep(args.interval)

if __name__ == '__main__':
    main()
