#!/usr/bin/env bash
set -euo pipefail

workspace="$(realpath "$GITHUB_WORKSPACE")"
capacity_base="$workspace/validation-capacity-base"
support="$workspace/.github/ci-test-support"
source_sha="$(git -C "$workspace" rev-parse HEAD)"
source_tree="$(git -C "$workspace" rev-parse 'HEAD^{tree}')"
test "$source_sha" = "$GITHUB_SHA"
test "$(git -C "$capacity_base" rev-parse HEAD)" = c83320000a085bf30490b4b76b425527fe8574f7

context="$RUNNER_TEMP/midas-ci-backend-context-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
test_data="$RUNNER_TEMP/midas-ci-backend-data-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
container="midas-ci-backend-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
image="midas-ci-backend:$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
test ! -e "$context"
test ! -e "$test_data"
mkdir -p "$context"
mkdir -m 0777 "$test_data"
cp "$support/Dockerfile.backend" "$context/Dockerfile"
cp "$workspace/pyproject.toml" "$workspace/uv.lock" "$context/"

cleanup() {
  docker rm --force "$container" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker build --pull --file "$context/Dockerfile" --tag "$image" "$context"

docker create --name "$container" --init \
  --network none \
  --memory=11g --memory-reservation=10g --memory-swap=11g --cpus=3 --pids-limit=512 \
  --read-only --cap-drop=ALL --security-opt=no-new-privileges:true --shm-size=512m \
  --tmpfs /tmp:rw,nosuid,nodev,size=8192m,uid=10001,gid=10001,mode=1777 \
  --tmpfs /workspace:rw,nosuid,nodev,exec,size=4096m,uid=10001,gid=10001,mode=0755 \
  --tmpfs /home/midas:rw,nosuid,nodev,size=512m,uid=10001,gid=10001,mode=0755 \
  --tmpfs /home/charlie:ro,nosuid,nodev,size=64m,mode=0755 \
  --tmpfs /run:rw,nosuid,nodev,noexec,size=64m,mode=0755 \
  --tmpfs /var/tmp:rw,nosuid,nodev,size=256m,uid=10001,gid=10001,mode=1777 \
  --mount "type=bind,src=$workspace,dst=/source,readonly" \
  --mount "type=bind,src=$support,dst=/control,readonly" \
  --mount "type=bind,src=$capacity_base,dst=/capacity-base,readonly" \
  --mount "type=bind,src=$test_data,dst=/test-data" \
  --env MIDAS_CI_SOURCE_SHA="$source_sha" \
  --env MIDAS_CI_SOURCE_TREE="$source_tree" \
  --env GIT_ALTERNATE_OBJECT_DIRECTORIES=/capacity-base/.git/objects \
  --env MIDAS_PHASE5_SYNTHETIC_USER_PSI=1 \
  --env MIDAS_MODE=demo \
  --env MIDAS_RUNTIME_ROOT=/tmp/midas-ci/runtime \
  --env MIDAS_DATABASE_URL=sqlite+aiosqlite:////tmp/midas-ci/runtime/paper.sqlite3 \
  --env MIDAS_RECORDING_ROOT=/tmp/midas-ci/recordings \
  --env MIDAS_ARENA_ROOT=/tmp/midas-ci/arena \
  --env MIDAS_FRONTIER_ROOT=/tmp/midas-ci/frontier \
  --env MIDAS_REALITY_WORKSPACE=/tmp/midas-ci/reality \
  --env MIDAS_VERITAS_WORKSPACE=/workspace \
  --env MIDAS_FRONTIER_POLYMARKET_PUBLIC_PROBE_ENABLED=false \
  --env MIDAS_FRONTIER_KALSHI_PUBLIC_PROBE_ENABLED=false \
  --env MIDAS_FRONTIER_KRAKEN_PUBLIC_PROBE_ENABLED=false \
  --env MIDAS_FRONTIER_COINBASE_PUBLIC_PROBE_ENABLED=false \
  --env HOME=/home/midas \
  --env TMPDIR=/tmp/midas-ci/tmp \
  --env XDG_CACHE_HOME=/tmp/home-cache \
  --env XDG_CONFIG_HOME=/tmp/home-config \
  --env XDG_STATE_HOME=/tmp/home-state \
  --env XDG_RUNTIME_DIR=/tmp/midas-ci/xdg-runtime \
  --env DBUS_SESSION_BUS_ADDRESS=unix:path=/tmp/midas-ci/no-user-bus \
  --env DBUS_SYSTEM_BUS_ADDRESS=unix:path=/tmp/midas-ci/no-system-bus \
  --env SYSTEMD_BUS_ADDRESS=unix:path=/tmp/midas-ci/no-system-bus \
  --env MIDAS_BLOCKED_COMMAND_LOG=/tmp/midas-blocked-command.log \
  --env PYTHONPATH=/control:/workspace:/workspace/packages \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --env MIDAS_PYTHON=/opt/venv/bin/python \
  --env OMP_NUM_THREADS=1 \
  --env OPENBLAS_NUM_THREADS=1 \
  --env MKL_NUM_THREADS=1 \
  "$image" bash -c 'exec sleep infinity' >/dev/null

python3 - "$container" "$workspace" "$support" "$capacity_base" "$test_data" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

name, workspace, support, capacity_base, test_data = sys.argv[1:]
details = json.loads(subprocess.check_output(["docker", "inspect", name]))[0]
host = details["HostConfig"]
assert host["NetworkMode"] == "none"
assert host["ReadonlyRootfs"] is True
assert host["Privileged"] is False
assert "ALL" in host["CapDrop"]
assert any("no-new-privileges" in item for item in host["SecurityOpt"])
assert host["PidsLimit"] == 512
assert host["Memory"] == 11 * 1024**3
assert host["MemorySwap"] == 11 * 1024**3
assert host["NanoCpus"] == 3_000_000_000
assert details["Config"]["User"] == "10001:10001"
assert not host.get("Devices") and not host.get("DeviceRequests")

binds = {mount["Destination"]: mount for mount in details["Mounts"] if mount["Type"] == "bind"}
assert set(binds) == {"/source", "/control", "/capacity-base", "/test-data"}, binds
assert binds["/source"]["Source"] == workspace and not binds["/source"]["RW"]
assert binds["/control"]["Source"] == support and not binds["/control"]["RW"]
assert binds["/capacity-base"]["Source"] == capacity_base and not binds["/capacity-base"]["RW"]
assert binds["/test-data"]["Source"] == test_data and binds["/test-data"]["RW"]
assert not list(Path(test_data).iterdir()), "test-data mount must be fresh"
environment = details["Config"]["Env"]
assert not any(item.startswith(("GITHUB_", "ACTIONS_")) for item in environment)
assert not any(item.startswith("MIDAS_") and "TOKEN" in item for item in environment)
print("Backend container isolation policy verified before candidate code starts.")
PY

docker start "$container" >/dev/null
container_pid="$(docker inspect --format '{{.State.Pid}}' "$container")"
container_id="$(docker inspect --format '{{.Id}}' "$container")"
sudo python3 - "$container_pid" "$container_id" <<'PY'
import os
import sys
from pathlib import Path

pid, container_id = sys.argv[1:]
if not pid.isdecimal() or int(pid) <= 0:
    raise SystemExit("test container has no valid init PID")
memberships = Path(f"/proc/{pid}/cgroup").read_text().splitlines()
relative = next((line.split(":", 2)[2] for line in memberships if line.startswith("0::")), None)
if not relative or not relative.startswith("/") or ".." in Path(relative).parts:
    raise SystemExit("test container cgroup path is invalid")
if not any(container_id in component for component in Path(relative).parts):
    raise SystemExit("refusing to write a cgroup not uniquely owned by this container")
root = Path("/sys/fs/cgroup")
group = root / relative.lstrip("/")
if group.is_symlink() or not group.is_dir() or not group.resolve().is_relative_to(root.resolve()):
    raise SystemExit("test container cgroup escaped the cgroup hierarchy")
maximum = (group / "memory.max").read_text().strip()
swap = (group / "memory.swap.max").read_text().strip()
current = int((group / "memory.current").read_text().strip())
if maximum != str(11 * 1024**3) or swap != "0":
    raise SystemExit(f"unexpected test cgroup limits: max={maximum}, swap={swap}")
high = 10 * 1024**3
if current >= high:
    raise SystemExit("container is already too close to its high memory threshold")
high_file = group / "memory.high"
if high_file.is_symlink():
    raise SystemExit("test cgroup memory.high is a symlink")
fd = os.open(high_file, os.O_WRONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0))
with os.fdopen(fd, "w") as stream:
    stream.write(str(high))
if high_file.read_text().strip() != str(high):
    raise SystemExit("finite memory.high could not be established")
print(f"Test container cgroup bounded: memory.high={high} memory.max={maximum} memory.swap.max={swap}")
PY

test "$(docker exec "$container" cat /sys/fs/cgroup/memory.high)" = "$((10 * 1024 * 1024 * 1024))"
docker exec "$container" bash /control/run-backend-validation.sh
printf 'Backend test report: %s/backend.xml\n' "$test_data"
