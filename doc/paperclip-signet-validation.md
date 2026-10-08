# Current scope

This implementation accompanies the [unnumbered BIP draft](https://github.com/connorslab/bitcoin-rebindable-transactions). It retains RDTS restrictions and narrows CSFS to the current input template hash after height 3250. Activation relaxes RDTS consensus rules and requires upgraded clients. The new CSFS rule has a fixed 32-byte consensus requirement; historical policy-only records below describe earlier versions. The dated records below describe each deployment stage.

# Validation - 2026-10-05

Native Ubuntu 26.04 x86_64 tests passed:

- 19 selected unit suites covering script, signatures, proof of work and validation.
- Published BIP446 basic vectors, including incorrect commitments.
- All 19 BIP340 vectors through CSFS, with 0-, 1-, 17-, 32- and 100-byte messages.
- Default-policy covenant spends: accepted, mined, altered-output rejected, restart verified.
- Two-node signed Blake2b signet: invalid signatures rejected, peers synchronize, restart verified.
- Upstream `feature_rdts.py` and `feature_unified_sighash.py --descriptors` pass with the experimental flag off.
- Flynn independently synchronized from node2 and verified the public demonstration block.

GitHub runners stayed queued during preparation and were cancelled. These are
completed native build results, not a claim that queued CI jobs passed. A manual
CI workflow is included. This work is not a security audit.

## Public test-chain evidence

Block 107: `356eea2e89180e202fb415577c796a7fd6f0ec702d45eb4bc28b0a6005d4a476`

Funding: `b7abdb1b10b1a96fe99cec95d4fbe4741ef10530f297a55d93948921428d4568`

TEMPLATEHASH + CSFS spend: `64c44225e3c1a9a403101e75f37360e4d1a1a31833f4e765aa7889d5ac9c1469`

Template hash: `4c15957a86ea68a2a813caad213e229e7e9afdf52df1ede06ac58ebaf4ecdf66`

Reducing the committed output by one satoshi was rejected with `Invalid Schnorr
signature`. The valid spend and funding transaction were mined together.
The first 106 blocks bootstrapped mature faucet funds quickly; ongoing block
production targets one minute. Test coinbase maturity is 100 blocks.

## Limits

No Ark refresh, LN-symmetry, application replay-domain design, production wallet
integration, automatic faucet, or external libbitcoinconsensus API support is
claimed. Only BIP446's basic vectors were imported, not its full large script-assets
corpus. Exhaustive fuzzing and independent consensus review remain future work.
See README for the two deliberate RDTS exceptions and replay-protection limits.

## BIP448 operation set — 2026-10-07

The signet now implements all three operations referenced by BIP448, adding
BIP349 INTERNALKEY (0xcb) to TEMPLATEHASH and CHECKSIGFROMSTACK.

Validation: 19 selected native unit suites passed, including internal-key
extraction and non-tapscript rejection. Functional covenant tests passed with
two distinct internal keys, valid signatures, altered-output rejection,
mining, and restart verification. Signed-signet and CSFS-policy tests passed.
RDTS and unified-sighash regression tests also passed.

An independent node synchronized the existing public chain and passed
verifychain at level 4 over its entire chain. Node2 passed the same check after
upgrade. The existing mainnet service was not restarted.

A spend executing TEMPLATEHASH INTERNALKEY CHECKSIGFROMSTACK confirmed in
block 3179 (12efe2b4c124965637322592e81abdd5cc22308a084ff4128d5973ccf2dfb8ea):
973537dde4725fcdc2fabb0d923cf455e51c45aa52b7e31a3ce7cfd6c6c54083.
Changing its output amount by one satoshi was rejected with Invalid Schnorr
signature. This demonstration uses a public test key and also permits key-path
spending; it is an opcode test, not a secure covenant protocol.

Binary version: paperclip-signet2-bip448. The network retains RDTS restrictions
and the configurable CSFS relay-message cap. No mainnet activation is proposed
by this deployment. Full BIP446 script-assets import, fuzzing, and independent
consensus review remain outstanding.

## Upgrade compatibility clarification

RDTS includes DISCOURAGE_OP_SUCCESS in mandatory consensus flags. An old
verification node rejected the INTERNALKEY demonstration block at height 3179.
After restarting it with the completed build and reconsidering that block, the
node accepted it and passed full-chain verifychain (level 4). Participants must
upgrade; this test-network rule relaxation is not an upstream-style soft fork.

## Template-only CSFS upgrade — October 8, 2026 UTC

Version: `paperclip-signet3-template-csfs`. Deployed on node2 at height 3240.
The new fixed rule activates for blocks at height **3250**, inclusive. Updated
mempools enforce it immediately. Earlier blocks retain the previous rules.

Every CSFS message must be exactly 32 bytes equal to the current input template
hash, including empty-signature calls and unknown key types. This narrows the
message domain without changing the BIP340 verification algorithm. The optional
size-policy setting and additional policy-only script pass were removed.

Validation of the deployed build:

- All 19 selected native unit suites passed.
- Functional tests passed: template-only activation, existing covenant spends,
  historical CSFS, RDTS, unified sighash, and signed signet synchronization.
- Boundary tests reject 0-, 31-, 33-, 64- and 80-byte messages, unrelated 32-byte
  values, and hashes of unrelated preimages. A correct digest supplied as a
  constant remains valid; the rule checks value rather than opcode provenance.
- A pre-activation arbitrary-message block remains valid; an activation-height
  block containing such a spend is rejected. Historical script cache population,
  restart, full-chain verification, and valid template spends are covered.
- Both experimental Ark harnesses passed against this exact build: offline
  refresh/recovery and native ASP/watchman crash, reorg and service-offline exit.
  These are single-balance experimental protocols, not complete production Ark.
- Node2 full-chain verification passed after deployment. Signet RPC downtime was
  1.48 seconds. The main Bitcoin node was not restarted. A clean private backup
  of the previous binaries and datadir was retained.

Deployed executable SHA256:

- bitcoind: `1e586a18863badd1d5205ca32704fb5b1383287d03a4727a52fe6912547102bb`
- bitcoin-cli: `74b004d2035848d40f8a189b287dfd445c580054ce0ab0c019dc74516fc0451c`

This restricts arbitrary CSFS messages, not all possible data storage in Bitcoin.
