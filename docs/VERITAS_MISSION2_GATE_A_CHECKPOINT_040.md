# Gate A checkpoint 040 — reject dangling successor roots

Captured 2026-10-16 00:38:24 UTC. This is a path-safety follow-up to the
isolated discovery successor. It does not change the scanner protocol or
activate it.

## Finding and fix

Code review found that `_isolated_root` checked whether the requested root
both existed and was a symlink before resolving it. A dangling symlink has
`exists() == false`, so resolution could follow it and create the target as the
successor's artifact root. That path was not exercised by the original tests.

The successor now rejects any symlink root before resolution. A regression
test supplies a dangling link to an absent temporary target and verifies that
the call fails and the target is not created.

## Verification

- Focused successor, observer, and control-retrieval tests: **19 passed** in
  8.91 seconds.
- Ruff lint, Ruff format, strict Mypy for the successor module and CLI, and
  `git diff --check`: passed.
- Commit: `70144d9` (`fix(veritas): reject dangling successor roots`).
- Updated module SHA-256:
  `3796e8dd1a7b0fcbc5eb11f033dcf0b15c85a26ea231acfb86619b670ced6f52`.
- Updated test SHA-256:
  `a445c8058d5528316467b845a86dd658643c46cadd04e37914ed1b8eac9a2ac7`.

The test uses a temporary directory and mocked transport. It made no public
market request and wrote no artifact outside its temporary root. No live
successor scan, service change, campaign change, deployment, or pilot mutation
occurred. The issue was found before the successor's first live run, so there
is no observed artifact impact.

The fixed v1 pilot remains active through 2026-10-16 19:00:55 UTC. The
successor remains gated and has no live control-yield or economic evidence.
See [checkpoint 039](VERITAS_MISSION2_GATE_A_CHECKPOINT_039.md), [H087](VERITAS_RESEARCH_LEDGER.json),
and [inventory 049](VERITAS_MISSION2_RESEARCH_INVENTORY_049.json).
