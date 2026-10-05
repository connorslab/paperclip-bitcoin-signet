# Bitcoin signet faucet

Public form: https://node2.paperclippool.xyz/signet/#faucet

The faucet pays 0.01 test BTC per successful request. A network (IPv4 address
or IPv6 /64) and destination script can each claim once per rolling 24 hours.
The shared cap is 1 test BTC per rolling 24 hours, excluding transaction fees.
Fees are paid by the faucet at 1 sat/vbyte. These coins have no monetary value.
Shared networks share their allowance. This is abuse mitigation, not proof
that every requester is a unique person.

## Deployment and boundaries

`explorer-faucet.service` runs `faucet.py` on localhost:48401. Caddy proxies only
`/signet/api/faucet`, limits the request body, and overwrites X-Faucet-Client
with the TCP client's address. Do not add a CDN/proxy without revisiting that
client identity handling. Requests require the site's exact Origin.

The explorer web process remains read-only without node cookie access.
The separate faucet process uses the signet RPC cookie and the dedicated
`public-faucet` wallet, loaded on node startup. It verifies the chain name,
exact challenge, synchronization, and chain freshness before sending. There
is no generic public RPC interface or public wallet balance endpoint.

The service cannot read the signer file or wallet files. Its RPC cookie still
has node-level authority: the dedicated wallet is an accounting/spending
boundary in the application, not a wallet-scoped RPC credential. Keep this
service on the test-only node and never provide mainnet credentials. No
automatic treasury refill is configured. Initial funding was 10 test BTC.

## Persistence and recovery

`/var/lib/paperclip-signet-faucet/claims.sqlite` is the durable request journal;
`identity.key` keys network-address hashes. Both are private and persist across
service restarts. Never delete them to fix a payment: doing so resets limits
and loses duplicate-send protection. Back up SQLite using its backup API (or
stop only explorer-faucet before copying its complete state directory).
Keep wallet backups private and out of the public repository.

Each request UUID is committed before sendtoaddress. A repeated UUID returns
its recorded result, never another send. An RPC timeout/crash leaves `pending`;
this consumes its allowance and is not automatically retried. Search the
public-faucet wallet transaction history for comment `public-faucet:<UUID>`.
Verify the transaction, destination, and amount before updating that journal
row to `sent` with its txid. If no transaction is found, investigate the node
logs and complete wallet history; absence from a short history page is not
proof of nonpayment. Do not blindly refund, resend, or clear the row.

## Operations

Use the existing private SSH access. Signet CLI prefix:

```sh
runuser -u xbt-signet -- /opt/paperclip-xbt-signet/bin/bitcoin-cli \
  -datadir=/var/lib/paperclip-xbt-signet -rpcwallet=public-faucet getbalances
```

Replace `getbalances` with `getnewaddress` for a refill destination. Fund it
only from this signet's test coins. Never import production private keys.
Use `backupwallet` to an xbt-signet-writable private location, then move the
backup into root-only recovery storage. To pause the faucet:
`systemctl stop explorer-faucet`; neither mining nor the explorer needs to stop.
Start it again with `systemctl start explorer-faucet` after troubleshooting.

Deploy root-owned source files mode 0644, service unit in /etc/systemd/system,
validate Caddy before reloading it, and restart only explorer-web when its
static-file allowlist changes. No node or miner restart is needed.

## Validation (2026-10-05)

Eight combined explorer/faucet tests pass: accounting, reorgs, mempool,
route limits, durable cooldown/idempotency, ambiguous RPC failure, network
rejection, IPv6 aggregation and global cap. Run:

```sh
python3 -m unittest discover -s contrib/explorer -p 'test_*.py' -v
```

Live form smoke test sent 0.01 test BTC at 1 sat/vbyte:
`f37850f7a1eaea20f9ee6a79ce7c5680b9c418fd2500032ccf93c4409c85f404`.
Node/miner/mainnet-fallback process IDs were unchanged during deployment.
