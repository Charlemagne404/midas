#!/usr/bin/env bash
set -euo pipefail

fail() {
  printf 'ISOLATION FAILURE: %s\n' "$*" >&2
  exit 90
}

test "$(git -c safe.directory=/source -C /source rev-parse HEAD)" = "$MIDAS_PHASE5_SOURCE_SHA" || fail "source SHA mismatch"
test "$(git -c safe.directory=/source -C /source rev-parse 'HEAD^{tree}')" = "$MIDAS_PHASE5_SOURCE_TREE" || fail "source tree mismatch"
if git -c safe.directory=/source -C /source config --local --get-regexp 'http\..*\.extraheader' >/dev/null 2>&1; then
  fail "checkout credentials persisted in source configuration"
fi

/opt/venv/bin/python - <<'PY'
import os
from pathlib import Path

mounts = {}
for line in Path("/proc/self/mountinfo").read_text().splitlines():
    left, right = line.split(" - ", 1)
    fields = left.split()
    mountpoint = fields[4].replace("\\040", " ")
    mount_options = set(fields[5].split(","))
    fstype = right.split()[0]
    mounts[mountpoint] = (fstype, mount_options)

for point in ("/tmp", "/workspace", "/home/midas", "/home/charlie", "/run"):
    if mounts.get(point, (None,))[0] != "tmpfs":
        raise SystemExit(f"{point} is not an isolated tmpfs mount")
if "ro" not in mounts["/home/charlie"][1]:
    raise SystemExit("/home/charlie must be a read-only tmpfs shadow of host paths")
if any(Path("/home/midas").iterdir()) or any(Path("/home/charlie").iterdir()):
    raise SystemExit("fresh disposable homes are not empty")
for path in (
    "/run/dbus/system_bus_socket",
    "/run/systemd/private",
    "/run/user/10001/bus",
    "/run/docker.sock",
    "/var/run/docker.sock",
    "/home/charlie/midas/data/midas.db",
    "/home/charlie/midas-reality/data/recordings",
    "/home/charlie/midas-reality/data/research",
    "/home/charlie/midas-veritas/data",
):
    if Path(path).exists() or Path(path).is_socket():
        raise SystemExit(f"host control socket is present: {path}")

for name in (
    "MIDAS_RUNTIME_ROOT",
    "MIDAS_RECORDING_ROOT",
    "MIDAS_ARENA_ROOT",
    "MIDAS_LABORATORY_ROOT",
    "MIDAS_FRONTIER_ROOT",
    "MIDAS_REALITY_WORKSPACE",
):
    value = Path(os.environ[name])
    resolved = value.resolve(strict=False)
    if not resolved.is_relative_to(Path("/tmp/midas-phase5")):
        raise SystemExit(f"{name} is outside disposable storage: {resolved}")
if not Path(os.environ["MIDAS_VERITAS_WORKSPACE"]).resolve().is_relative_to(Path("/workspace")):
    raise SystemExit("Veritas workspace is outside the disposable source copy")
if not os.environ["MIDAS_DATABASE_URL"].startswith(
    "sqlite+aiosqlite:////tmp/midas-phase5/"
):
    raise SystemExit("default database is not a disposable SQLite file")
if os.environ.get("GITHUB_TOKEN") or os.environ.get("ACTIONS_RUNTIME_TOKEN"):
    raise SystemExit("GitHub credential was passed into the candidate container")
print("Isolation mounts, runtime roots, database target, and absent host sockets verified.")
PY

set +e
systemctl --user list-units >/dev/null 2>&1
systemctl_status=$?
systemd-run --user --unit=midas-phase5-denied true >/dev/null 2>&1
systemd_run_status=$?
set -e
test "$systemctl_status" -eq 125 || fail "systemctl was not rejected"
test "$systemd_run_status" -eq 125 || fail "systemd-run was not rejected"
test "$(realpath "$(command -v systemctl)")" = /opt/isolation/bin/midas-deny-command || fail "systemctl shim is not first on PATH"
test "$(realpath /usr/bin/systemctl)" = /opt/isolation/bin/midas-deny-command || fail "absolute systemctl path is not intercepted"
test "$(realpath /usr/bin/systemd-run)" = /opt/isolation/bin/midas-deny-command || fail "absolute systemd-run path is not intercepted"
grep -q '^blocked systemctl ' /tmp/midas-blocked-command.log || fail "systemctl rejection was not recorded"
grep -q '^blocked systemd-run ' /tmp/midas-blocked-command.log || fail "systemd-run rejection was not recorded"

/opt/venv/bin/python - <<'PY'
import socket
import time

listener = socket.socket()
listener.bind(("127.0.0.1", 0))
listener.listen(1)
client = socket.create_connection(listener.getsockname(), timeout=2)
conn, _ = listener.accept()
client.close()
conn.close()
listener.close()

outside = socket.socket()
outside.settimeout(2)
try:
    outside.connect(("1.1.1.1", 443))
except OSError:
    print("Loopback works; external IPv4 connection is blocked.")
else:
    raise SystemExit("external network access is available")
finally:
    outside.close()

deadline = time.monotonic() + 5
while True:
    try:
        socket.create_connection(("postgres", 5432), timeout=1).close()
        break
    except OSError:
        if time.monotonic() >= deadline:
            raise SystemExit("synthetic PostgreSQL is unreachable on the internal network")
        time.sleep(0.2)
print("Only the expected synthetic PostgreSQL service is reachable.")
PY

mkdir -p /tmp/midas-phase5/runtime /tmp/midas-phase5/recordings \
  /tmp/midas-phase5/arena /tmp/midas-phase5/laboratory \
  /tmp/midas-phase5/frontier /tmp/midas-phase5/reality \
  /tmp/midas-phase5/veritas /tmp/midas-phase5/xdg-runtime \
  /tmp/home-cache /tmp/home-config /tmp/home-state /tmp/reports
chmod 0700 /tmp/midas-phase5/xdg-runtime
cp -R /source/. /workspace/
ln -s /opt/web-deps/node_modules /workspace/node_modules
ln -s /opt/web-deps/apps/web/node_modules /workspace/apps/web/node_modules

printf '\n=== Candidate source ===\n'
printf 'commit=%s\ntree=%s\n' \
  "$(git -C /workspace rev-parse HEAD)" \
  "$(git -C /workspace rev-parse 'HEAD^{tree}')"
node --version
corepack pnpm --version
/opt/venv/bin/python --version

/opt/venv/bin/python - <<'PY'
import os
from pathlib import Path

from apps.api.config import Settings

settings = Settings()
expected = {
    "runtime_root": "MIDAS_RUNTIME_ROOT",
    "reality_workspace": "MIDAS_REALITY_WORKSPACE",
    "veritas_workspace": "MIDAS_VERITAS_WORKSPACE",
    "laboratory_root": "MIDAS_LABORATORY_ROOT",
    "arena_root": "MIDAS_ARENA_ROOT",
    "recording_root": "MIDAS_RECORDING_ROOT",
    "frontier_root": "MIDAS_FRONTIER_ROOT",
}
for field, variable in expected.items():
    actual = getattr(settings, field)
    configured = Path(os.environ[variable])
    if actual is None or Path(actual).resolve() != configured.resolve():
        raise SystemExit(f"{field} did not resolve to its disposable path")
if settings.database_url != os.environ["MIDAS_DATABASE_URL"]:
    raise SystemExit("database_url did not resolve to the disposable SQLite target")
if settings.mode != "demo":
    raise SystemExit("runtime mode is not simulation-only")
print("Application settings resolve to disposable roots and demo mode.")
PY

printf '\n=== Stage A: Static verification ===\n'
static_gate_failures=0
/opt/venv/bin/python -m compileall -q packages/midas apps/api scripts
/opt/venv/bin/ruff check packages apps/api tests infra scripts
if ! /opt/venv/bin/ruff format --check packages apps/api tests infra scripts; then
  printf 'Static gate failure: Ruff formatting check found pre-existing formatting in the unchanged main-side autonomy script. Continuing to collect functional validation results.\n' >&2
  static_gate_failures=1
fi
/opt/venv/bin/mypy packages/midas apps/api
/opt/venv/bin/python - <<'PY'
import apps.api.main
import apps.api.frontier
import apps.api.readiness
import apps.api.reality
import apps.api.veritas
print("API module import smoke passed without starting an application server.")
PY
corepack pnpm format:check
corepack pnpm lint
corepack pnpm typecheck
corepack pnpm build

run_pytest() {
  local label="$1"
  shift
  local report="/tmp/reports/${label}.xml"
  local log="/tmp/reports/${label}.log"
  printf '\n=== %s ===\n' "$label"
  set +e
  /opt/venv/bin/pytest -q --junitxml="$report" "$@" 2>&1 | tee "$log"
  local status=$?
  set -e
  if [[ -s "$report" ]]; then
    /opt/venv/bin/python - "$report" "$label" "$log" <<'PY'
import re
import sys
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1]).getroot()
cases = list(root.iter("testcase"))
failures = sum(case.find("failure") is not None for case in cases)
errors = sum(case.find("error") is not None for case in cases)
skipped = sum(case.find("skipped") is not None for case in cases)
passed = len(cases) - failures - errors - skipped
deselected_match = re.search(r"(\d+)\s+deselected", open(sys.argv[3], encoding="utf-8").read())
deselected = int(deselected_match.group(1)) if deselected_match else 0
print(
    f"JUNIT {sys.argv[2]}: total={len(cases)} passed={passed} "
    f"failed={failures + errors} errors={errors} skipped={skipped} deselected={deselected}"
)
PY
  else
    printf 'JUNIT %s: report missing or incomplete; see runner log.\n' "$label" >&2
  fi
  return "$status"
}

printf '\n=== Stage B: Focused integration suites ===\n'
focused=(
  tests/arena
  tests/frontier
  tests/laboratory
  tests/simulation
  tests/test_autonomy_campaign.py
  tests/test_api_contract_diff.py
  tests/test_host_capacity_summary.py
  tests/test_readiness_resources.py
  tests/test_midas_candidate_db_smoke.py
  tests/test_midas_resource_preflight.py
  tests/test_midas_sqlite_snapshot.py
)
while IFS= read -r file; do focused+=("$file"); done < <(find tests -maxdepth 1 -type f \( -name 'test_reality*.py' -o -name 'test_veritas*.py' -o -name 'test_reconcile_reality_source_quality.py' \) | sort)
run_pytest focused-integration "${focused[@]}"

printf '\n=== Stage C: Frontend component and browser suites ===\n'
corepack pnpm --dir apps/web exec vitest run --maxWorkers=2 --minWorkers=1
corepack pnpm --dir apps/web exec playwright test --workers=1 --reporter=line

printf '\n=== Stage D: Full backend regression ===\n'
run_pytest full-backend

printf '\n=== Stage E: Native process-pool and recovery ===\n'
run_pytest native-process-pool \
  tests/laboratory/test_campaigns.py::test_campaign_parallel_results_deterministic_and_compact_reconstruction \
  tests/laboratory/test_campaigns.py::test_interrupt_checkpoint_cancel_resume_and_reopen

printf '\n=== Stage F: Storage, migration, archive, and replay ===\n'
export MIDAS_DATABASE_URL='postgresql+asyncpg://midas:phase5_synthetic_only@postgres:5432/midas_ci'
export MIDAS_TEST_POSTGRES_URL="$MIDAS_DATABASE_URL"
/opt/venv/bin/alembic upgrade head
/opt/venv/bin/python scripts/storage_smoke.py
run_pytest postgres-integration tests/integration/test_postgres_paper.py
unset MIDAS_DATABASE_URL MIDAS_TEST_POSTGRES_URL
export MIDAS_DATABASE_URL='sqlite+aiosqlite:////tmp/midas-phase5/runtime/offline.sqlite3'
run_pytest offline-recovery-replay \
  tests/test_reality_recovery.py \
  tests/test_reality_full_scale_validation.py \
  tests/test_veritas_scan_catalog.py \
  tests/test_veritas_v6_offline_replay.py \
  tests/frontier/test_historical_replay.py
/opt/venv/bin/python scripts/replay.py

printf '\nAll requested validation stages completed. Review per-stage counts above.\n'
if [[ "$static_gate_failures" -ne 0 ]]; then
  printf 'Required static validation remains failed; candidate is not fully validated.\n' >&2
  exit 1
fi
