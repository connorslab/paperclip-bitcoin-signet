# Validation — 2026-10-05

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
