#!/usr/bin/env python3
"""Build the exact immutable Veritas CI release from pinned repository files."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import midas_resource_preflight as preflight  # noqa: E402

ROLLBACK_REVISIONS = {
    "rollback/previous-finalized_source_analysis.py": (
        "d1ce072c520547b95c42a29b76e5776721bf4c1b",
        "packages/midas/veritas/finalized_source_analysis.py",
    ),
    "rollback/midas-veritas-source-analysis.service": (
        "28c63e6d1306364e5f38d50bc85364daa6134bce",
        "deploy/systemd/user/midas-veritas-source-analysis.service",
    ),
}
ROLLBACK_DROPIN = (
    b"[Service]\n"
    b"Environment=PYTHONPATH=/home/charlie/.local/share/midas-veritas/"
    b"frozen-runtime-overlay/packages:/home/charlie/midas-veritas/packages\n"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def git_blob(revision: str, path: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(REPO_ROOT), "show", f"{revision}:{path}"])


def source_bytes(relative: str, expected_sha256: str | None = None) -> bytes:
    source_map = {
        "bin/midas_resource_preflight.py": "scripts/midas_resource_preflight.py",
        "service/midas-veritas-source-analysis.service": (
            "deploy/systemd/user/midas-veritas-source-analysis.service"
        ),
    }
    path = source_map.get(relative, relative)
    candidates = [REPO_ROOT / path]
    if relative.startswith("packages/"):
        candidates.extend(
            REPO_ROOT / overlay / relative
            for overlay in (
                "deploy/runtime/veritas-gap-detail-v2-20261020",
                "deploy/runtime/veritas-gap-detail-v2-20261021",
            )
        )
    for candidate in candidates:
        if candidate.is_file():
            data = candidate.read_bytes()
            if expected_sha256 is None or sha256(data) == expected_sha256:
                return data
    raise SystemExit(f"could not locate pinned immutable release file {relative}")


def build(destination: Path, revision: str) -> dict[str, object]:
    if destination.exists() or destination.is_symlink():
        raise SystemExit(f"refusing to replace existing immutable release: {destination}")
    if sha256(ROLLBACK_DROPIN) != preflight.VERITAS_PRODUCTION_IMPORT_DROPIN_SHA256:
        raise SystemExit("rollback import-dropin fixture does not match the approved hash")
    destination.mkdir(parents=True, mode=0o700)

    expected_runtime = preflight.VERITAS_APPROVED_RUNTIME_CODE_FILES
    runtime_sources = {
        "finalized_source_analysis.py": "packages/midas/veritas/finalized_source_analysis.py",
        "scripts/veritas_source_analysis.py": "scripts/veritas_source_analysis.py",
        "economics.py": "packages/midas/veritas/economics.py",
        **{
            f"reality/{name}": f"packages/midas/reality/{name}"
            for name in (
                "execution_research.py",
                "reconstruction.py",
                "research_measurements.py",
                "research_schema.py",
                "shadow_campaign.py",
                "shadow_source.py",
                "shadow_worker.py",
                "storage.py",
            )
        },
    }
    payload: dict[str, bytes] = {}
    for path in (
        *preflight.VERITAS_APPROVED_PACKAGE_INIT_FILES,
        *preflight.VERITAS_APPROVED_RELEASE_DEPENDENCY_FILES,
        *runtime_sources.values(),
        "bin/midas_resource_preflight.py",
        "service/midas-veritas-source-analysis.service",
    ):
        expected = preflight.VERITAS_APPROVED_PACKAGE_INIT_FILES.get(
            path
        ) or preflight.VERITAS_APPROVED_RELEASE_DEPENDENCY_FILES.get(path)
        if path in runtime_sources.values():
            identity = next(key for key, value in runtime_sources.items() if value == path)
            expected = expected_runtime[identity]
        data = source_bytes(path, expected)
        if expected and sha256(data) != expected:
            raise SystemExit(f"pinned release source changed: {path}")
        payload[path] = data

    for release_path, (revision_id, source_path) in ROLLBACK_REVISIONS.items():
        payload[release_path] = git_blob(revision_id, source_path)
    payload["rollback/20-frozen-campaign-import.conf"] = ROLLBACK_DROPIN
    expected_rollback = {
        "rollback/previous-finalized_source_analysis.py": preflight.VERITAS_PRODUCTION_MODULE_SHA256,
        "rollback/midas-veritas-source-analysis.service": preflight.VERITAS_PRODUCTION_SERVICE_SHA256,
        "rollback/20-frozen-campaign-import.conf": preflight.VERITAS_PRODUCTION_IMPORT_DROPIN_SHA256,
    }
    for path, expected in expected_rollback.items():
        if sha256(payload[path]) != expected:
            raise SystemExit(f"rollback artifact does not match its verified identity: {path}")

    # Runtime paths in the release are package-relative; the import launcher and
    # service are installed at the paths validated by the service unit.
    files: dict[str, str] = {}
    for path, data in sorted(payload.items()):
        if path.startswith("packages/") or path.startswith("scripts/"):
            relative = path
        elif path.startswith("rollback/") or path.startswith("service/") or path.startswith("bin/"):
            relative = path
        else:
            raise SystemExit(f"unexpected release path: {path}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        target.write_bytes(data)
        files[relative] = sha256(data)

    runtime_digest = sha256(canonical(expected_runtime))
    manifest: dict[str, object] = {
        "format": "midas-veritas-guarded-release",
        "format_version": 1,
        "release_identity": preflight.VERITAS_RELEASE_ID,
        "source_revision": preflight.VERITAS_APPROVED_SOURCE_REVISION,
        "launcher_source_revision": revision,
        "release_source_revision": revision,
        "candidate_module_sha256": preflight.VERITAS_APPROVED_MODULE_SHA256,
        "wrapper_sha256": preflight.VERITAS_APPROVED_WRAPPER_SHA256,
        "rollback_module_sha256": preflight.VERITAS_PRODUCTION_MODULE_SHA256,
        "rollback_artifacts_sha256": expected_rollback,
        "campaign_sha256": preflight.VERITAS_CAMPAIGN_SHA256,
        "runtime_analysis_code_files": expected_runtime,
        "runtime_analysis_code_sha256": runtime_digest,
        "package_init_files_sha256": preflight.VERITAS_APPROVED_PACKAGE_INIT_FILES,
        "release_dependency_files_sha256": preflight.VERITAS_APPROVED_RELEASE_DEPENDENCY_FILES,
        "python_runtime": preflight.VERITAS_APPROVED_PYTHON_RUNTIME,
        "python_distribution_versions": preflight.VERITAS_APPROVED_DISTRIBUTION_VERSIONS,
        "launcher_sha256": files["bin/midas_resource_preflight.py"],
        "service_sha256": files["service/midas-veritas-source-analysis.service"],
        "files_sha256": files,
    }
    manifest_bytes = canonical(manifest) + b"\n"
    (destination / "RELEASE-MANIFEST.json").write_bytes(manifest_bytes)
    (destination / "RELEASE-MANIFEST.sha256").write_text(
        f"{sha256(manifest_bytes)}  RELEASE-MANIFEST.json\n", encoding="ascii"
    )
    for path in sorted(destination.rglob("*"), reverse=True):
        os.chmod(path, 0o555 if path.is_dir() else 0o444)
    os.chmod(destination, 0o555)
    verified = preflight.verify_veritas_release(
        destination,
        expected_release_identity=preflight.VERITAS_RELEASE_ID,
        expected_source_revision=preflight.VERITAS_APPROVED_SOURCE_REVISION,
        expected_module_sha256=preflight.VERITAS_APPROVED_MODULE_SHA256,
    )
    if not verified.get("passed") or verified.get("file_count") != 34:
        raise SystemExit("built release did not pass its exact manifest verification")
    return {"path": str(destination), "manifest_sha256": sha256(manifest_bytes), **verified}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--destination", type=Path, default=preflight.VERITAS_RELEASE_ROOT)
    args = parser.parse_args()
    result = build(args.destination, args.revision)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
