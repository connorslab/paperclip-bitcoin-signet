# Current scope

This implementation accompanies the [unnumbered BIP draft](https://github.com/connorslab/bitcoin-rebindable-transactions). It keeps the three BIP 448 opcode semantics while retaining RDTS restrictions. Activation relaxes RDTS consensus rules and requires upgraded clients. The CSFS message cap is separate local policy. The dated records below describe each deployment stage.

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
