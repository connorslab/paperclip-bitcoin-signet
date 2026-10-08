# Template-only CSFS: fixed consensus message size

CSFS requires exactly 32 bytes equal to the current input's BIP446 TEMPLATEHASH.
The rule applies before signature handling, including empty signatures and unknown
key types. A different 32-byte digest, or a hash of unrelated data, fails.

This is consensus, not a configurable size policy. The former `-maxcsfsmsgsize`
option has been removed; remove it from existing configurations. There is no
signet opt-out. Matching digest values may be supplied by any stack source; no
opcode-origin tracking is implied.

The experimental signet activates at height **3250**, inclusive. Historical blocks
retain the previous rules. Updated nodes enforce the restriction immediately in
mempool admission and mining selection, before block activation. Regtest defaults
to activation at zero; `-testactivationheight=csfstemplate@<height>` and the
regtest-only value `-1` exist for historical/activation tests.

This is a per-message rule, not a transaction-wide 32-byte budget. The experimental
Ark two-input refund uses two 32-byte messages and remains valid. Script signature
budgets, transaction weight, and RDTS limits still apply. This restriction does
not eliminate other data-carrying paths or supply application replay domains.

Existing outputs that require arbitrary-message CSFS may become unspendable after
activation. General BIP348 delegation and oracle constructions are not supported
by the narrowed rule. Test coins only; no production activation is proposed.

Validation entry points:

```sh
build/bin/test_bitcoin --run_test=script_tests
python3 test/functional/feature_csfs_template.py --configfile=build/test/config.ini
python3 test/functional/feature_bitcoin_covenants.py --configfile=build/test/config.ini
python3 test/functional/mempool_csfs_policy.py --configfile=build/test/config.ini
```

The last test explicitly disables the new deployment on private regtest to retain
coverage of historical blocks. It is not a signet configuration example.
