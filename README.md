# Paperclip XBT covenant signet

**Experimental software. Test coins only, with no monetary value. Not a mainnet upgrade.**

This repository starts from Bitcoin Knots `v29.4.2.knots20260508`
(`58398baf33e588779685ead478e6397bb28ed3d6`) and adds an isolated
Blake2b/XBT signet for testing two draft proposals:

- [BIP446 TEMPLATEHASH](https://bips.dev/446/), opcode `0xce`.
- [BIP348 CHECKSIGFROMSTACK](https://bips.dev/348/), opcode `0xcc`.

The network is live at `node2.paperclippool.xyz:48333`. See
[validation results](doc/paperclip-signet-validation.md) for the tested scope.

## Rules and scope

`-xbtcovtest` enables both opcodes only on custom signet or regtest. It is rejected
on mainnet and other networks. Without that option, their existing OP_SUCCESS
behavior and policy restrictions remain unchanged. Both instructions are defined
only in tapscript. TEMPLATEHASH uses cached BIP341 components and the BIP446
`TemplateHash` tag. CSFS verifies an arbitrary-length stack message directly with
BIP340 Schnorr verification and charges the tapscript signature budget.

The experimental signet activates Blake2b header-v2 at height 1, uses easy fixed
proof of work and a private block-signing challenge, and uses separate network
magic. Genesis is the inherited signet genesis; subsequent blocks use Blake2b.
The intended signer produces one block per minute. Coinbase maturity is 100
blocks on this test network; this is not the mainnet maturity schedule.

RDTS is active. This experiment deliberately makes two exceptions: activated
TEMPLATEHASH/CSFS opcodes, and the verified BIP325 signature envelope in the
coinbase witness commitment (bounded to 160 bytes). Other output-size limits,
annex restrictions, control-block limits and conditional-opcode restrictions remain.
This is **not** consensus-compatible with unmodified XBT nodes.

Upstream unified-sighash support is retained without changing its selection rules.
CSFS verifies application messages: it does not automatically apply unified
sighash or provide cross-chain replay protection. Use dedicated test keys and
explicit application-domain commitments when designing protocols. Never reuse
mainnet keys or assume these primitives alone provide a safe Ark or Lightning
implementation.

## Build

Clone `https://github.com/connorslab/paperclip-xbt-signet` and run the commands
from its root. The example scripts and joining configuration are in this repo.

On Ubuntu, install `cmake ninja-build g++ libevent-dev libboost-dev libsqlite3-dev`.

```sh
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_GUI=OFF -DBUILD_BENCH=OFF -DENABLE_IPC=OFF -DWITH_BDB=OFF
cmake --build build -j 4
ctest --test-dir build --output-on-failure -j 4 -R 'script|sighash|signet|pow|validation'
python3 build/test/functional/feature_xbt_covenants.py
python3 build/test/functional/feature_xbt_signet.py
```

The functional tests use disposable local chains and no real funds. The covenant
test exercises default mempool policy, valid spends, altered-output rejection,
mining and restart. The signet test exercises signed Blake2b block production.
The unit suite includes the published BIP446 basic vectors and CSFS checks.

## Join

Release binaries target **Ubuntu 26.04 x86_64**. Runtime packages are
`libevent-extra-2.1-7t64`, `libevent-pthreads-2.1-7t64`, and `libsqlite3-0`.
Check release SHA256SUMS. For other systems, build from source.

```sh
mkdir -m 700 "$HOME/.paperclip-xbt-signet"
cp contrib/signet/paperclip/join.conf "$HOME/.paperclip-xbt-signet/bitcoin.conf"
build/bin/bitcoind -datadir="$HOME/.paperclip-xbt-signet" -daemonwait
build/bin/bitcoin-cli -datadir="$HOME/.paperclip-xbt-signet" getblockchaininfo
build/bin/bitcoin-cli -datadir="$HOME/.paperclip-xbt-signet" createwallet test
build/bin/bitcoin-cli -datadir="$HOME/.paperclip-xbt-signet" -rpcwallet=test getnewaddress
```

For release binaries replace `build/bin/` with their extracted location. This
syncs only the test chain. Change the local RPC/P2P ports if already occupied.
The joining configuration contains the public challenge, never the signing key.

Request test coins from the operator in a repository issue containing only your
test receiving address. There is no automatic public faucet yet. Never publish
seeds, keys, RPC cookies or credentials. After receiving at least 0.0011 test XBT:

```sh
python3 contrib/signet/covenant_demo.py --cli="$PWD/build/bin/bitcoin-cli" \
  --datadir="$HOME/.paperclip-xbt-signet" --wallet=test
```

This funds and spends a TEMPLATEHASH + CSFS output, and checks rejection of an
altered output. It prints transaction IDs; verify confirmation in the next block.
Its CSFS key is deliberately public and its internal taproot key is a NUMS point.
Never use this demonstration with anything of value. New test networks lack fee
estimates; specify an explicit fee, such as `fee_rate=1` sat/vB for wallet sends.

## Operations

Example systemd services are in `contrib/signet/paperclip/`. Keep this network in
a dedicated data directory. Do not point it at a mainnet directory. Bind RPC to
loopback and use its cookie authentication; expose only the signet P2P port.
The block-signing key belongs only on the operator's signer, never in joining
configuration, release archives or this repository. Never change consensus
options in an existing datadir; network-rule changes require a new test network.

## Attribution

Bitcoin Knots and Bitcoin Core remain the upstream foundations. TEMPLATEHASH is
specified by Gregory Sanders, Antoine Poinsot and Steven Roose; CSFS by Brandon
Black and Jeremy Rubin. Source licensing remains MIT except where individual
files specify otherwise; the imported BIP446 vectors are CC0-1.0. This deployment
and integration are an independent Paperclip experiment, not an endorsement by
those authors or upstream projects.
