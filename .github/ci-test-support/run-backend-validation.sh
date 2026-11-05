#!/usr/bin/env bash
set -euo pipefail

fail() {
  printf 'BACKEND ISOLATION FAILURE: %s\n' "$*" >&2
  exit 90
}

test "$(git -c safe.directory=/source -C /source rev-parse HEAD)" = "$MIDAS_CI_SOURCE_SHA" \
  || fail "source commit mismatch"
test "$(git -c safe.directory=/source -C /source rev-parse 'HEAD^{tree}')" = "$MIDAS_CI_SOURCE_TREE" \
  || fail "source tree mismatch"
test "$(git -c safe.directory=/capacity-base -C /capacity-base rev-parse HEAD)" = \
  c83320000a085bf30490b4b76b425527fe8574f7 \
  || fail "pinned archive base mismatch"
test "$(git -c safe.directory=/veritas-memory-baseline -C /veritas-memory-baseline rev-parse HEAD)" = \
  "$MIDAS_CI_VERITAS_BASELINE_SHA" \
  || fail "pinned Veritas memory baseline mismatch"

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
root = Path("/sys/fs/cgroup").resolve()
if group.is_symlink() or not group.is_dir() or not group.resolve().is_relative_to(root):
    raise SystemExit("test container cgroup is missing or unsafe")
high = (group / "memory.high").read_text(encoding="ascii").strip()
maximum = (group / "memory.max").read_text(encoding="ascii").strip()
swap = (group / "memory.swap.max").read_text(encoding="ascii").strip()
if not high.isdecimal() or not maximum.isdecimal() or int(high) <= 0 or int(maximum) <= int(high):
    raise SystemExit("test cgroup must have finite positive memory.high below memory.max")
if int(maximum) != 11 * 1024**3 or swap != "0":
    raise SystemExit(f"unexpected test cgroup limits: max={maximum}, swap={swap}")
if os.access("/sys/fs/cgroup", os.W_OK):
    raise SystemExit("candidate UID can write the cgroup hierarchy")
tmp = os.statvfs("/tmp")
available = tmp.f_bavail * tmp.f_frsize
if available < 6 * 1024**3:
    raise SystemExit("isolated /tmp has less than 6 GiB available")
print(f"Bounded backend cgroup verified: memory.high={high} memory.max={maximum} memory.swap.max={swap}")
print(f"Disposable /tmp capacity available: {available} bytes")
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
    options = set(fields[5].split(","))
    mounts[mountpoint] = (right.split()[0], options)

for point in ("/tmp", "/workspace", "/home/midas", "/home/charlie", "/run", "/var/tmp"):
    if mounts.get(point, (None,))[0] != "tmpfs":
        raise SystemExit(f"{point} is not a disposable tmpfs mount")
if "/test-data" not in mounts or not os.access("/test-data", os.W_OK):
    raise SystemExit("dedicated test-data mount is missing or read-only")
if "/veritas-memory-baseline" not in mounts or "ro" not in mounts["/veritas-memory-baseline"][1]:
    raise SystemExit("pinned Veritas memory baseline is missing or writable")
if "ro" not in mounts["/home/charlie"][1]:
    raise SystemExit("/home/charlie must be a read-only shadow of host paths")
if os.access("/sys/fs/cgroup", os.W_OK):
    raise SystemExit("candidate UID can write the cgroup hierarchy")
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
        raise SystemExit(f"host control or production path is present: {path}")

for name in (
    "MIDAS_RUNTIME_ROOT",
    "MIDAS_RECORDING_ROOT",
    "MIDAS_ARENA_ROOT",
    "MIDAS_FRONTIER_ROOT",
    "MIDAS_REALITY_WORKSPACE",
):
    path = Path(os.environ[name]).resolve()
    if not path.is_relative_to(Path("/tmp/midas-ci")):
        raise SystemExit(f"{name} is outside disposable storage: {path}")
if "MIDAS_LABORATORY_ROOT" in os.environ:
    raise SystemExit("CI must leave Laboratory root unset for per-test isolation")
if Path(os.environ["MIDAS_VERITAS_WORKSPACE"]).resolve() != Path("/workspace"):
    raise SystemExit("Veritas workspace is not the disposable source copy")
if not os.environ["MIDAS_DATABASE_URL"].startswith("sqlite+aiosqlite:////tmp/midas-ci/"):
    raise SystemExit("default database is not disposable SQLite")
if os.environ.get("MIDAS_MODE") != "demo":
    raise SystemExit("runtime is not in simulation-only demo mode")
if any(
    name.startswith(("GITHUB_", "ACTIONS_", "AWS_", "AZURE_", "DEPLOY_"))
    or name in {"GH_TOKEN", "GH_ENTERPRISE_TOKEN", "KUBECONFIG"}
    or name.endswith(("_TOKEN", "_SECRET", "_PASSWORD", "_CREDENTIALS"))
    for name in os.environ
):
    raise SystemExit("credential-like environment reached the backend test container")
print("Disposable roots, isolated mounts, absent services/secrets, and demo mode verified.")
PY

for command in systemctl systemd-run busctl dbus-send gdbus sudo; do
  set +e
  "$command" --midas-ci-isolation-probe >/dev/null 2>&1
  status=$?
  set -e
  test "$status" -eq 125 || fail "$command was not rejected"
  test "$(realpath "$(command -v "$command")")" = /opt/isolation/bin/midas-deny-command \
    || fail "$command shim is not first on PATH"
  for absolute_path in "/usr/bin/$command" "/bin/$command"; do
    test "$(realpath "$absolute_path")" = /opt/isolation/bin/midas-deny-command \
      || fail "absolute $absolute_path is not intercepted"
  done
  grep -q "^blocked $command " /tmp/midas-blocked-command.log \
    || fail "$command rejection was not recorded"
done

mkdir -p /test-data/tmp /tmp/midas-ci/runtime /tmp/midas-ci/recordings \
  /tmp/midas-ci/tmp /tmp/midas-ci/arena /tmp/midas-ci/frontier \
  /tmp/midas-ci/reality /tmp/midas-ci/veritas /tmp/midas-ci/xdg-runtime \
  /tmp/home-cache /tmp/home-config /tmp/home-state /tmp/reports
chmod 0700 /tmp/midas-ci/xdg-runtime
export TMPDIR=/tmp/midas-ci/tmp

git -c safe.directory=/source -C /source archive --format=tar HEAD | tar -C /workspace -xf -
cp -R /source/.git /workspace/.git
test "$(git -C /workspace rev-parse HEAD)" = "$MIDAS_CI_SOURCE_SHA" \
  || fail "writable source copy has the wrong commit"
test "$(git -C /workspace rev-parse 'HEAD^{tree}')" = "$MIDAS_CI_SOURCE_TREE" \
  || fail "writable source copy has the wrong tree"
git -C /workspace diff --exit-code >/dev/null || fail "writable source copy differs from its commit"
git -C /workspace diff --cached --exit-code >/dev/null || fail "writable source index differs from its commit"
test -z "$(git -C /workspace ls-files --others --exclude-standard)" \
  || fail "writable source copy contains unexpected untracked files"
if git -C /workspace config --local --get-regexp 'http\..*\.extraheader' >/dev/null 2>&1; then
  fail "checkout credentials persisted in the source configuration"
fi

cd /workspace
export PYTHONPATH=/control:/workspace:/workspace/packages

printf '\n=== Python syntax and imports ===\n'
/opt/venv/bin/python -m compileall -q packages/midas apps/api scripts
/opt/venv/bin/python - <<'PY'
import apps.api.main
import apps.api.frontier
import apps.api.readiness
import apps.api.reality
import apps.api.veritas

print("API import smoke passed without starting a server.")
PY

printf '\n=== Python lint, format, and type checks ===\n'
/opt/venv/bin/ruff check packages apps/api tests infra scripts .github/ci-test-support
/opt/venv/bin/ruff format --check packages apps/api tests infra scripts .github/ci-test-support
/opt/venv/bin/mypy packages/midas apps/api

printf '\n=== Full backend regression suite ===\n'
set +e
/opt/venv/bin/pytest -q --junitxml=/test-data/backend.xml 2>&1 | tee /test-data/backend.log
test_status=${PIPESTATUS[0]}
set -e
/opt/venv/bin/python - /test-data/backend.xml <<'PY'
import sys
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1]).getroot()
cases = list(root.iter("testcase"))
failed = sum(case.find("failure") is not None or case.find("error") is not None for case in cases)
skipped = sum(case.find("skipped") is not None for case in cases)
print(
    f"Backend JUnit: total={len(cases)} passed={len(cases) - failed - skipped} "
    f"failed={failed} skipped={skipped} deselected=0"
)
PY
if [[ "$test_status" -ne 0 ]]; then
  exit "$test_status"
fi

printf '\n=== Native worker and process lifecycle checks ===\n'
/opt/venv/bin/pytest -q \
  tests/laboratory/test_campaigns.py::test_campaign_parallel_results_deterministic_and_compact_reconstruction \
  tests/laboratory/test_campaigns.py::test_interrupt_checkpoint_cancel_resume_and_reopen

printf '\n=== Isolated Veritas catalog memory comparison ===\n'
/opt/venv/bin/python /control/measure-veritas-catalog-memory.py \
  --current-root /workspace \
  --baseline-root /veritas-memory-baseline

printf '\n=== Offline synthetic replay ===\n'
/opt/venv/bin/python scripts/replay.py
