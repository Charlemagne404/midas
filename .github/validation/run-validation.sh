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

cgroup_relative="$(awk -F: '$1 == "0" && $2 == "" { print $3; exit }' /proc/self/cgroup)"
test -n "$cgroup_relative" || fail "test container has no cgroup v2 membership"
case "$cgroup_relative" in
  /*) ;;
  *) fail "cgroup path must be absolute" ;;
esac
case "/$cgroup_relative/" in
  */../*|*/./*) fail "cgroup path contains traversal components" ;;
esac
preflight_cgroup="/sys/fs/cgroup${cgroup_relative}"
/opt/venv/bin/python - "$preflight_cgroup" <<'PY'
import os
import sys
from pathlib import Path

group = Path(sys.argv[1])
if group.is_symlink() or not group.is_dir():
    raise SystemExit("test container cgroup is missing or unsafe")
if not group.resolve().is_relative_to(Path("/sys/fs/cgroup").resolve()):
    raise SystemExit("test container cgroup escaped the cgroup mount")
limits = {}
for name in ("memory.high", "memory.max"):
    limits[name] = (group / name).read_text(encoding="ascii").strip()
maximum = limits["memory.max"]
high = limits["memory.high"]
if maximum in {"max", "infinity"} or not maximum.isdecimal() or int(maximum) <= 0:
    raise SystemExit("test container memory.max is not finite and positive")
if high in {"max", "infinity"} or not high.isdecimal() or int(high) <= 0:
    raise SystemExit("test container memory.high is not finite and positive")
if int(high) >= int(maximum):
    raise SystemExit("test container memory.high must be below memory.max")
swap_max = (group / "memory.swap.max").read_text(encoding="ascii").strip()
if swap_max != "0":
    raise SystemExit(f"test container swap is not disabled: memory.swap.max={swap_max}")
if os.access("/sys/fs/cgroup", os.W_OK):
    raise SystemExit("candidate UID can write the cgroup hierarchy")
tmp = os.statvfs("/tmp")
if tmp.f_bavail * tmp.f_frsize < 6 * 1024**3:
    raise SystemExit("test temporary filesystem is smaller than the required 6 GiB reserve")
print(
    "Bounded container cgroup verified: "
    f"memory.high={high} memory.max={maximum} memory.swap.max={swap_max} "
    f"effective_limit={high if high not in {'max', 'infinity'} else maximum}"
)
print(f"Disposable /tmp available capacity: {tmp.f_bavail * tmp.f_frsize} bytes")
PY
export MIDAS_RESOURCE_PREFLIGHT_CGROUP="$preflight_cgroup"
export MIDAS_RESOURCE_PREFLIGHT_PROFILE=bounded-test
export MIDAS_RESOURCE_PREFLIGHT_AT_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

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
if "/test-data" not in mounts:
    raise SystemExit("/test-data is not the dedicated disposable validation mount")
if not os.access("/test-data", os.W_OK):
    raise SystemExit("dedicated disposable test-data mount is not writable")
if "ro" not in mounts["/home/charlie"][1]:
    raise SystemExit("/home/charlie must be a read-only tmpfs shadow of host paths")
if os.access("/sys/fs/cgroup", os.W_OK):
    raise SystemExit("candidate UID can write the cgroup hierarchy")
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
    "MIDAS_FRONTIER_ROOT",
    "MIDAS_REALITY_WORKSPACE",
):
    value = Path(os.environ[name])
    resolved = value.resolve(strict=False)
    if not resolved.is_relative_to(Path("/tmp/midas-phase5")):
        raise SystemExit(f"{name} is outside disposable storage: {resolved}")
lab_root = os.environ.get("MIDAS_LABORATORY_ROOT")
if lab_root and not Path(lab_root).resolve(strict=False).is_relative_to(Path("/tmp/midas-phase5")):
    raise SystemExit("MIDAS_LABORATORY_ROOT is outside disposable storage")
if not Path(os.environ["MIDAS_VERITAS_WORKSPACE"]).resolve().is_relative_to(Path("/workspace")):
    raise SystemExit("Veritas workspace is outside the disposable source copy")
if not os.environ["MIDAS_DATABASE_URL"].startswith(
    "sqlite+aiosqlite:////tmp/midas-phase5/"
):
    raise SystemExit("default database is not a disposable SQLite file")
if os.environ.get("GITHUB_TOKEN") or os.environ.get("ACTIONS_RUNTIME_TOKEN"):
    raise SystemExit("GitHub credential was passed into the candidate container")
secret_like = sorted(
    name
    for name in os.environ
    if name.startswith(("GITHUB_", "ACTIONS_", "AWS_", "AZURE_", "DEPLOY_"))
    or name in {"KUBECONFIG", "GH_TOKEN", "GH_ENTERPRISE_TOKEN"}
    or name.endswith(("_TOKEN", "_SECRET", "_PASSWORD", "_CREDENTIALS"))
)
if secret_like:
    raise SystemExit(f"credential-like environment variables reached candidate: {secret_like}")
print("Isolation mounts, runtime roots, database target, and absent host sockets verified.")
PY

for command in systemctl systemd-run busctl dbus-send gdbus sudo; do
  set +e
  "$command" --midas-phase5-isolation-probe >/dev/null 2>&1
  command_status=$?
  set -e
  test "$command_status" -eq 125 || fail "$command was not rejected"
  test "$(realpath "$(command -v "$command")")" = /opt/isolation/bin/midas-deny-command || \
    fail "$command shim is not first on PATH"
  for absolute_path in "/usr/bin/$command" "/bin/$command"; do
    test "$(realpath "$absolute_path")" = /opt/isolation/bin/midas-deny-command || \
      fail "absolute $absolute_path is not intercepted"
  done
  grep -q "^blocked $command " /tmp/midas-blocked-command.log || \
    fail "$command rejection was not recorded"
done

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

outside_v6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
outside_v6.settimeout(2)
try:
    outside_v6.connect(("2606:4700:4700::1111", 443))
except OSError:
    print("External IPv6 connection is blocked.")
else:
    raise SystemExit("external IPv6 access is available")
finally:
    outside_v6.close()

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

mkdir -p /test-data/tmp /tmp/midas-phase5/runtime /tmp/midas-phase5/recordings \
  /tmp/midas-phase5/tmp \
  /tmp/midas-phase5/arena /tmp/midas-phase5/laboratory \
  /tmp/midas-phase5/frontier /tmp/midas-phase5/reality \
  /tmp/midas-phase5/veritas /tmp/midas-phase5/xdg-runtime \
  /tmp/home-cache /tmp/home-config /tmp/home-state /tmp/reports
chmod 0700 /tmp/midas-phase5/xdg-runtime
cp -R /source/. /workspace/
test "$(git -C /workspace rev-parse 'HEAD^{tree}')" = "$MIDAS_PHASE5_SOURCE_TREE" || fail "writable source copy has the wrong tree"
git -C /workspace diff --exit-code >/dev/null || fail "writable source copy differs from its commit"
git -C /workspace diff --cached --exit-code >/dev/null || fail "writable source copy index differs from its commit"
test -z "$(git -C /workspace ls-files --others --exclude-standard)" || fail "writable source copy contains unexpected untracked files"
ln -s /opt/web-deps/node_modules /workspace/node_modules
# Vite writes its temporary bundled-config file under apps/web/node_modules.
# Keep the dependency graph from the lockfile install, but place the app-level
# links in the writable tmpfs workspace so this cache write cannot target the
# read-only image layer.
cp -a /opt/web-deps/apps/web/node_modules /workspace/apps/web/node_modules

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
/opt/venv/bin/python -m compileall -q packages/midas apps/api scripts
/opt/venv/bin/ruff check packages apps/api tests infra scripts
/opt/venv/bin/ruff format --check packages apps/api tests infra scripts
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

# Keep the verified demo mode and disposable roots for every child process.
# Pytest temporary paths remain on the isolated tmpfs at the approved /tmp root.
export TMPDIR=/tmp/midas-phase5/tmp
cd /workspace

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
  /workspace/tests/arena
  /workspace/tests/frontier
  /workspace/tests/laboratory
  /workspace/tests/simulation
  /workspace/tests/test_autonomy_campaign.py
  /workspace/tests/test_api_contract_diff.py
  /workspace/tests/test_host_capacity_summary.py
  /workspace/tests/test_readiness_resources.py
  /workspace/tests/test_midas_candidate_db_smoke.py
  /workspace/tests/test_midas_resource_preflight.py
  /workspace/tests/test_midas_sqlite_snapshot.py
)
while IFS= read -r file; do focused+=("$file"); done < <(find /workspace/tests -maxdepth 1 -type f \( -name 'test_reality*.py' -o -name 'test_veritas*.py' -o -name 'test_reconcile_reality_source_quality.py' \) | sort)
run_pytest focused-integration "${focused[@]}"

printf '\n=== Stage C: Frontend component and browser suites ===\n'
corepack pnpm --dir /workspace/apps/web exec vitest run --maxWorkers=2 --minWorkers=1
export MIDAS_FRONTIER_E2E_ROOT=/tmp/midas-browser-phase5
corepack pnpm --dir /workspace/apps/web exec playwright test --workers=1 --reporter=line
corepack pnpm --dir /workspace/apps/web exec playwright test --config playwright.reality.config.ts --workers=1 --reporter=line
unset MIDAS_FRONTIER_E2E_ROOT

printf '\n=== Stage D: Full backend regression ===\n'
run_pytest full-backend /workspace/tests

printf '\n=== Stage E: Native process-pool and recovery ===\n'
run_pytest native-process-pool \
  /workspace/tests/laboratory/test_campaigns.py::test_campaign_parallel_results_deterministic_and_compact_reconstruction \
  /workspace/tests/laboratory/test_campaigns.py::test_interrupt_checkpoint_cancel_resume_and_reopen

printf '\n=== Stage F: Storage, migration, archive, and replay ===\n'
export MIDAS_DATABASE_URL='postgresql+asyncpg://midas:phase5_synthetic_only@postgres:5432/midas_ci'
export MIDAS_TEST_POSTGRES_URL="$MIDAS_DATABASE_URL"
cd /workspace
/opt/venv/bin/alembic upgrade head
/opt/venv/bin/python scripts/storage_smoke.py
cd /workspace
run_pytest postgres-integration /workspace/tests/integration/test_postgres_paper.py
unset MIDAS_DATABASE_URL MIDAS_TEST_POSTGRES_URL
export MIDAS_DATABASE_URL='sqlite+aiosqlite:////tmp/midas-phase5/runtime/offline.sqlite3'
run_pytest offline-recovery-replay \
  /workspace/tests/test_reality_recovery.py \
  /workspace/tests/test_reality_full_scale_validation.py \
  /workspace/tests/test_veritas_scan_catalog.py \
  /workspace/tests/test_veritas_v6_offline_replay.py \
  /workspace/tests/frontier/test_historical_replay.py
cd /workspace
/opt/venv/bin/python scripts/replay.py

printf '\nAll requested validation stages completed. Review per-stage counts above.\n'
