# Captured public Milestone 2 evidence

The `ctf-*.json` artifacts were captured from genuine unauthenticated Gamma, CLOB and
Polygon read responses on 2026-10-11. They contain no credentials, private keys, wallet
balances or real orders. CTF contract addresses and instrument IDs are public identifiers.
They retain raw metadata/books, finalized helper-call results, normalized contracts,
attestation, proof, paper rejection and source timestamps. Original rules are descriptive
metadata and do not constitute human review. Captured artifacts can expire; offline tests
replay their receipt clock rather than presenting them as current quotes.

`websocket-ctf.json` retains the actual public snapshot/PONG probe for the first selected
CTF asset. This is not sustained delta/reconnect verification. `ctf-4061337.json` also
preserves an earlier genuinely captured stale-book rejection. Service evidence retains
its own independently sampled market IDs and timestamps. A fixture replay verifies compatibility, never a new live
integration. Regenerate a controlled current sample with `scripts/verify_economics.py`.
