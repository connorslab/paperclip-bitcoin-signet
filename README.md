# Paperclip XBT covenant signet

**Experimental software. Test coins only, with no monetary value. Not a mainnet upgrade.**

This repository starts from Bitcoin Knots `v29.4.2.knots20260508`
(`58398baf33e588779685ead478e6397bb28ed3d6`) and adds an isolated
Blake2b/XBT signet for testing two draft proposals:

- [BIP446 TEMPLATEHASH](https://bips.dev/446/), opcode `0xce`.
- [BIP348 CHECKSIGFROMSTACK](https://bips.dev/348/), opcode `0xcc`.

Deployment and validation are in progress. Do not treat this branch as a tested
release until the release notes include passing tests and joining configuration.

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
