# Captured public fixtures

`gamma_live.json` and `book_live.json` were retrieved from unauthenticated Gamma `/markets?active=true&closed=false&limit=3` and CLOB `/book?token_id=...` on 2026-10-11. They are actual public v1 responses for adapter tests, never demo observations or positive trading claims. Both identifier fields appear; selection follows `version`, not presence. Monetary JSON values are preserved as source values. The fixed fixture files make ordinary CI independent of internet availability.
