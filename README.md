# Paperclip Bitcoin covenant signet

**Experimental software. Test coins only, with no monetary value. Not a mainnet upgrade.**

This repository starts from [Bitcoin Knots](https://github.com/bitcoinknots/bitcoin) `v29.4.2.knots20260508`
(`58398baf33e588779685ead478e6397bb28ed3d6`) and adds an isolated
Bitcoin signet for testing the three operations proposed by [BIP448](https://bips.dev/448/):

- [BIP446 TEMPLATEHASH](https://bips.dev/446/), opcode `0xce`.
- [BIP348 CHECKSIGFROMSTACK](https://bips.dev/348/), opcode `0xcc`.
- [BIP349 INTERNALKEY](https://bips.dev/349/), opcode `0xcb`.

The network is live at `node2.paperclippool.xyz:48333`. See
[validation results](doc/paperclip-signet-validation.md) for the tested scope.

## Relationship to the unnumbered BIP draft

This repository implements the [unnumbered BIP draft, Taproot Rebindable Transactions under RDTS](https://github.com/connorslab/bitcoin-rebindable-transactions). No BIP number has been assigned, and the draft has not been submitted to the upstream BIPs repository. Production activation is unspecified.

### How this differs from upstream BIP 448

The opcode numbers are unchanged. CSFS is narrowed to exactly the current input's 32-byte TEMPLATEHASH; arbitrary-message CSFS is prohibited. TEMPLATEHASH and INTERNALKEY retain their upstream definitions.

| Area | Upstream BIP 448 | This experiment |
| --- | --- | --- |
| Upgrade type | Tightens ordinary Tapscript OP_SUCCESS behavior, allowing a soft fork. | RDTS already rejects unknown OP_SUCCESS operations at consensus. Allowing these operations relaxes that rule and requires upgraded clients. |
| CSFS message | Arbitrary stack messages under BIP 348. | Exactly 32 bytes equal to the current input template hash; consensus-enforced after activation, including empty signatures. |
| Script limits | Uses ordinary Tapscript rules. | Retains 256-byte stack elements, at most seven Taproot Merkle branch hashes, no annexes, and no Tapscript OP_IF or OP_NOTIF. |
| Hashing and signatures | BIP 446 tagged SHA256 template hashes and BIP 340 signatures. | Same definitions. Header hashing does not change template hashing; CSFS does not automatically inherit transaction-signature replay protection. |
| Deployment | Activation is unspecified. | Live on experimental signet, with custom signet and regtest support. Production activation remains unspecified. |

CSFS has a fixed consensus requirement: exactly 32 bytes equal to the current input's template hash. The old `-maxcsfsmsgsize` option is removed. Signet block activation is height 3250; updated nodes reject other CSFS messages from the mempool immediately. A construction valid under upstream BIP 448 may fail here if it needs features prohibited by RDTS.

## Network identity

Repository wording, filenames and new-install examples use Bitcoin/BTC.
The previous covenant option remains accepted as a hidden compatibility alias,
and the established network discriminator is unchanged so existing peers stay
on the same network, provided they upgrade for the new rules. Upstream addresses, encoded test data and contributor names
are preserved verbatim.

When upgrading an existing installation, retain its current data directory,
service account and service names. The service examples in this repository use
Bitcoin names for fresh installations; do not replace existing units without
adapting their paths and permissions. This source update does not migrate live
services or start a new chain.

## Rules and scope

`-btccovtest` enables all three opcodes only on custom signet or regtest. It is rejected
on mainnet and other networks. Without that option, their existing OP_SUCCESS
behavior and policy restrictions remain unchanged. All three instructions are defined
only in tapscript. TEMPLATEHASH uses cached BIP341 components and the BIP446
`TemplateHash` tag. CSFS verifies only the current input's 32-byte template digest with
BIP340 Schnorr verification after activation, and charges the tapscript signature budget.
INTERNALKEY pushes the 32-byte internal key from the validated Taproot control
block. It does not expose private keys or modify the output's spending conditions.

Existing signet participants must upgrade to accept INTERNALKEY spends. RDTS
makes unknown OP_SUCCESS rejection mandatory, so this is a consensus relaxation
relative to the previous signet client, not an upstream-style soft fork.
An old client that already marked block 3179 invalid must upgrade and then
reconsider block `12efe2b4c124965637322592e81abdd5cc22308a084ff4128d5973ccf2dfb8ea`
or rebuild its block index with the upgraded binary.
The existing network magic, challenge and chain are preserved. The TEMPLATEHASH and INTERNALKEY definitions follow their referenced drafts; CSFS
now additionally restricts its message, while this network retains the RDTS
restrictions described below; this is not an unrestricted upstream BIP448 network.

The experimental signet activates Blake2b header-v2 at height 1, uses easy fixed
proof of work and a private block-signing challenge, and uses separate network
magic. Genesis is the inherited signet genesis; subsequent blocks use Blake2b.
The intended signer produces one block per minute. Coinbase maturity is 100
blocks on this test network; this is not the mainnet maturity schedule.

RDTS is active. This experiment deliberately makes two exceptions: activated
TEMPLATEHASH/CSFS/INTERNALKEY opcodes, and the verified BIP325 signature envelope in the
coinbase witness commitment (bounded to 160 bytes). Other output-size limits,
annex restrictions, control-block limits and conditional-opcode restrictions remain.
This is **not** consensus-compatible with unmodified Bitcoin nodes.

Upstream unified-sighash support is retained without changing its selection rules.
CSFS verifies application messages: it does not automatically apply unified
sighash or provide cross-chain replay protection. Use dedicated test keys and
explicit application-domain commitments when designing protocols. Never reuse
mainnet keys or assume these primitives alone provide a safe Ark or Lightning
implementation.

## Build

### Fixed CSFS message rule

CSFS accepts exactly the current input's 32-byte TEMPLATEHASH. This is a
consensus rule from signet height **3250**, with immediate mempool enforcement
on updated nodes. Arbitrary messages and unrelated hashes fail, even with empty
signatures. The former `maxcsfsmsgsize` setting has been removed; remove it from
existing configurations. There is no signet opt-out.

The limit is per message, not per transaction. Two-input Ark refunds can use two
32-byte digests. Other script data paths remain possible; this is not a blanket
anti-data guarantee. See [rule details and tests](doc/csfs-message-policy.md).

### Build from source

Clone `https://github.com/connorslab/paperclip-bitcoin-signet` and run the commands
from its root. The example scripts and joining configuration are in this repo.

On Ubuntu, install `cmake ninja-build g++ libevent-dev libboost-dev libsqlite3-dev`.

```sh
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_GUI=OFF -DBUILD_BENCH=OFF -DENABLE_IPC=OFF -DWITH_BDB=OFF
cmake --build build -j 4
ctest --test-dir build --output-on-failure -j 4 -R 'script|sighash|signet|pow|validation'
python3 build/test/functional/feature_bitcoin_covenants.py
python3 build/test/functional/feature_bitcoin_signet.py
```

The functional tests use disposable local chains and no real funds. The covenant
test exercises default mempool policy, valid spends, altered-output rejection,
mining and restart. The signet test exercises signed Blake2b block production.
The unit suite includes the published BIP446 basic vectors and CSFS checks.

## Join

Release binaries target **Ubuntu 26.04 x86_64**. Runtime packages are
`libevent-extra-2.1-7t64`, `libevent-pthreads-2.1-7t64`, and `libsqlite3-0`.
Use [v0.2.0-bitcoin-signet](https://github.com/connorslab/paperclip-bitcoin-signet/releases/tag/v0.2.0-bitcoin-signet), version `paperclip-signet3-template-csfs`, or build current source. Verify the archive hash in the release notes and the extracted binaries against SHA256SUMS. Earlier builds do not enforce template-only CSFS at height 3250; builds before INTERNALKEY also cannot validate the existing chain past its first INTERNALKEY spend.

```sh
mkdir -m 700 "$HOME/.paperclip-bitcoin-signet"
cp contrib/signet/paperclip/join.conf "$HOME/.paperclip-bitcoin-signet/bitcoin.conf"
build/bin/bitcoind -datadir="$HOME/.paperclip-bitcoin-signet" -daemonwait
build/bin/bitcoin-cli -datadir="$HOME/.paperclip-bitcoin-signet" getblockchaininfo
build/bin/bitcoin-cli -datadir="$HOME/.paperclip-bitcoin-signet" createwallet test
build/bin/bitcoin-cli -datadir="$HOME/.paperclip-bitcoin-signet" -rpcwallet=test getnewaddress
```

For release binaries replace `build/bin/` with their extracted location. This
syncs only the test chain. Change the local RPC/P2P ports if already occupied.
The joining configuration contains the public challenge, never the signing key.

Get test coins from the [public faucet](https://node2.paperclippool.xyz/signet/#faucet):
0.01 test BTC per network/address every 24 hours, with a shared daily cap of
1 test BTC. See [faucet operations](contrib/explorer/FAUCET.md) for limits and
recovery details. Never publish seeds, keys, RPC cookies or credentials.
After receiving at least 0.0011 test BTC:

```sh
python3 contrib/signet/covenant_demo.py --cli="$PWD/build/bin/bitcoin-cli" \
  --datadir="$HOME/.paperclip-bitcoin-signet" --wallet=test --internal-key
```

This funds and spends a TEMPLATEHASH + INTERNALKEY + CSFS output, and checks rejection of an
altered output. It prints transaction IDs; verify confirmation in the next block.
The demonstration key is public and also permits key-path spending. This tests opcode execution, not a secure covenant protocol. Omit --internal-key for the earlier two-operation example with a NUMS internal key.
Never use this demonstration with anything of value. New test networks lack fee
estimates; specify an explicit fee, such as `fee_rate=1` sat/vB for wallet sends.

## Operations

Example systemd services are in `contrib/signet/paperclip/`. Keep this network in
a dedicated data directory. Do not point it at a mainnet directory. Bind RPC to
loopback and use its cookie authentication; expose only the signet P2P port.
The block-signing key belongs only on the operator's signer, never in joining
configuration, release archives or this repository. Consensus changes require a coordinated network upgrade or a new test network. This deployment retains the existing chain and challenge but requires upgraded clients.

## Attribution

Bitcoin Knots and Bitcoin Core remain the upstream foundations. TEMPLATEHASH is
specified by Gregory Sanders, Antoine Poinsot and Steven Roose; CSFS by Brandon
Black and Jeremy Rubin; INTERNALKEY by Brandon Black. Source licensing remains MIT except where individual
files specify otherwise; the imported BIP446 vectors are CC0-1.0. This deployment
and integration are an independent Paperclip experiment, not an endorsement by
those authors or upstream projects.
