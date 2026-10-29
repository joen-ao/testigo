# Synthetic receipts (decision D7)

Two receipts so anyone can try `testigo verify` without running anything:

- `clean/` — every check passes.
- `a3/` — the receipt is correctly signed, but what executed differs from what
  was approved, so it fails at step 4.

They are **synthetic**: built from test fixtures, and the "crop" files are
placeholder bytes, not real screenshots. They were signed with a throwaway key
whose private half was never saved; only `pubkey.txt` remains. They say nothing
about how TESTIGO+ performs on real runs.

```bash
testigo verify examples/clean/receipt.json --pubkey "$(cat examples/pubkey.txt)"
testigo verify examples/a3/receipt.json    --pubkey "$(cat examples/pubkey.txt)"
```
