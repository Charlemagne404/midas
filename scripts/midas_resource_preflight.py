#!/usr/bin/env python3
"""Fail-closed admission and bounded execution for MIDAS operational work."""

from __future__ import annotations

import argparse
import ctypes
import errno
import fcntl
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import selectors
import shlex
import shutil
import signal
import socket
import stat
import subprocess
import sys
import sysconfig
import time
import uuid
from pathlib import Path
from typing import Any

MIB = 1024 * 1024
CGROUP_ROOT = Path("/sys/fs/cgroup")
ALLOW_ACTIVE_UNITS = {
    "midas-api.service",
    "midas-web.service",
    "midas-reality.service",
    "midas-reality-api.service",
    "midas-reality-web.service",
    # These oneshot wrappers hold the shared heavy-workload lock while
    # invoking this preflight for their own bounded Restic operation.
    "midas-local-backup.service",
    "midas-local-backup-prune.service",
    "midas-local-backup-verify.service",
}
CRITICAL_UNITS = ("midas-api.service", "midas-reality.service")
PROFILES: dict[str, dict[str, float | int]] = {
    "heavy": {
        "min_available_mib": 4096,
        "min_swap_free_mib": 256,
        "max_swap_activity_pages": 0,
        "protected_headroom_mib": 64,
        "memory_some_avg10": 10.0,
        "memory_some_avg60": 10.0,
        "memory_full_avg10": 0.5,
        "memory_full_avg60": 1.0,
        "user_memory_some_avg10": 20.0,
        "user_memory_some_avg60": 20.0,
        "user_memory_full_avg10": 1.0,
        "user_memory_full_avg60": 1.0,
        "cpu_some_avg10": 25.0,
        "cpu_some_avg60": 25.0,
        "io_some_avg10": 10.0,
        "io_some_avg60": 10.0,
        "io_full_avg10": 1.0,
        "io_full_avg60": 1.5,
    },
    "bounded-test": {
        "min_available_mib": 2048,
        "min_swap_free_mib": 0,
        "max_swap_activity_pages": 8,
        "protected_headroom_mib": 0,
        "memory_some_avg10": 15.0,
        "memory_some_avg60": 15.0,
        "memory_full_avg10": 1.0,
        "memory_full_avg60": 2.0,
        "user_memory_some_avg10": 30.0,
        "user_memory_some_avg60": 30.0,
        "user_memory_full_avg10": 2.0,
        "user_memory_full_avg60": 3.0,
        "cpu_some_avg10": 40.0,
        "cpu_some_avg60": 40.0,
        "io_some_avg10": 20.0,
        "io_some_avg60": 20.0,
        "io_full_avg10": 5.0,
        "io_full_avg60": 5.0,
    },
    # This profile admits only the fixed /usr/bin/true, /usr/bin/false, or
    # /usr/bin/sleep 1 probes. It is deliberately short and still requires
    # host headroom, low pressure, protected-service reserve, and no competing
    # MIDAS worker. It permits at most 64 pages (256 KiB) of swap movement in
    # its maximum five-second sample; PSI, free-RAM, and service-headroom gates
    # still reject real pressure. It is never suitable for research or work.
    "synthetic-validation": {
        "min_available_mib": 2048,
        "min_swap_free_mib": 0,
        "max_swap_activity_pages": 64,
        "protected_headroom_mib": 128,
        "memory_some_avg10": 15.0,
        "memory_some_avg60": 15.0,
        "memory_full_avg10": 0.5,
        "memory_full_avg60": 1.0,
        "user_memory_some_avg10": 20.0,
        "user_memory_some_avg60": 20.0,
        "user_memory_full_avg10": 1.0,
        "user_memory_full_avg60": 1.0,
        "cpu_some_avg10": 50.0,
        "cpu_some_avg60": 50.0,
        "io_some_avg10": 20.0,
        "io_some_avg60": 20.0,
        "io_full_avg10": 5.0,
        "io_full_avg60": 5.0,
    },
    # Large sequential backups can tolerate occupied but inactive swap. They
    # still require a 30-second pressure sample, protected-service headroom,
    # and tight memory, CPU, and I/O bounds.
    "backup": {
        "min_available_mib": 6144,
        "min_swap_free_mib": 0,
        "max_swap_activity_pages": 8,
        "protected_headroom_mib": 128,
        "memory_some_avg10": 8.0,
        "memory_some_avg60": 8.0,
        "memory_full_avg10": 0.25,
        "memory_full_avg60": 0.5,
        "user_memory_some_avg10": 15.0,
        "user_memory_some_avg60": 15.0,
        "user_memory_full_avg10": 1.0,
        "user_memory_full_avg60": 1.0,
        "cpu_some_avg10": 25.0,
        "cpu_some_avg60": 25.0,
        "io_some_avg10": 5.0,
        "io_some_avg60": 5.0,
        # Keep recent full-I/O stalls under 1% and sustained stalls under the
        # existing bounded heavy-work ceiling. Backup I/O also runs at idle
        # priority and IOWeight=10.
        "io_full_avg10": 1.0,
        "io_full_avg60": 1.5,
    },
    # Veritas source analysis is a single bounded batch under a 256 MiB
    # service limit. Occupied swap is not useful headroom for this workload;
    # require no swap movement during a full sample instead. Its I/O ceilings
    # match the existing heavy profile, with repeated samples and hysteresis;
    # the memory and protected-service limits remain stricter.
    "veritas": {
        "min_available_mib": 6144,
        "min_swap_free_mib": 0,
        "max_swap_activity_pages": 0,
        "protected_headroom_mib": 128,
        "memory_some_avg10": 8.0,
        "memory_some_avg60": 8.0,
        "memory_full_avg10": 0.25,
        "memory_full_avg60": 0.5,
        "user_memory_some_avg10": 15.0,
        "user_memory_some_avg60": 15.0,
        "user_memory_full_avg10": 0.5,
        "user_memory_full_avg60": 1.0,
        "cpu_some_avg10": 25.0,
        "cpu_some_avg60": 25.0,
        "io_some_avg10": 5.0,
        "io_some_avg60": 5.0,
        "io_full_avg10": 1.0,
        "io_full_avg60": 1.5,
    },
}

VERITAS_RUN_LIMITS = {
    "memory_high_mib": 192,
    "memory_max_mib": 256,
    "memory_budget_mib": 128,
    "cpu_quota_percent": 100,
    "timeout_seconds": 600,
}
VERITAS_IO_ADMISSION = {
    "consecutive_samples": 2,
    "hard_avg10": 3.0,
    "hard_avg60": 3.0,
    "sample_interval_seconds": 10.0,
}
VERITAS_IO_RUNTIME = {
    "poll_interval_seconds": 1.0,
    "cancel_avg10": 2.0,
    "cancel_avg60": 1.5,
    "hard_avg10": 3.0,
    "hard_avg60": 3.0,
    "consecutive_samples": 5,
}
VERITAS_RUNTIME_PRESSURE_CANCELLED = 76
SYNTHETIC_RUN_LIMITS = {
    "memory_high_mib": 32,
    "memory_max_mib": 64,
    # The allowlisted true/false/sleep processes need only a small worker
    # reserve. Keeping it below the inner Python launcher's own headroom avoids
    # making its cgroup preflight self-defeating.
    "memory_budget_mib": 8,
    "cpu_quota_percent": 10,
    "timeout_seconds": 10,
    "max_sample_seconds": 5,
    "tasks_max": 8,
}
SYNTHETIC_TEST_COMMANDS = {
    ("/usr/bin/true",): 0,
    ("/usr/bin/false",): 1,
    ("/usr/bin/sleep", "1"): 0,
}
SYNTHETIC_SECCOMP_ARCHES = {
    "x86_64": 0xC000003E,
    "aarch64": 0xC00000B7,
}
SYNTHETIC_NETWORK_SYSCALLS = {
    "x86_64": (41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 53, 54, 55, 288, 299, 307),
    "aarch64": (
        198,
        199,
        200,
        201,
        202,
        203,
        204,
        205,
        206,
        207,
        208,
        209,
        210,
        211,
        212,
        242,
        243,
        269,
    ),
}
SYNTHETIC_TEST_ROOT = Path("/var/tmp") / f"midas-guarded-synthetic-{os.getuid()}"
SYNTHETIC_RECEIPT_DIR = SYNTHETIC_TEST_ROOT / "receipts"
GUARDED_RECEIPT_VERSION = 1
GUARDED_RECEIPT_DIR = (
    Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state")))
    / "midas"
    / "guarded-executions"
)
GUARDED_RECEIPT_MAX_BYTES = 128 * 1024
GUARDED_RECEIPT_MAX_FILES = 256
GUARDED_RECEIPT_KEEP_COMPLETED = 128
GUARDED_RECEIPT_TEMP_MAX_AGE_SECONDS = 3600
RUNNER_DIAGNOSTIC_TAIL_BYTES = 2048
RUNNER_RESULT_MISSING = 77
VERITAS_SERVICE_ROOT = Path.home() / "midas-veritas"
VERITAS_OUTPUT_ROOT = VERITAS_SERVICE_ROOT / "data" / "veritas-observatory"
VERITAS_SERVICE_UNIT = "midas-veritas-source-analysis.service"
VERITAS_CI_SERVICE_UNIT = "midas-veritas-source-analysis-ci.service"
VERITAS_CI_TEST_MARKER = "midas-veritas-systemd-ci-v1"
VERITAS_CI_ROOT = Path.home() / "midas-veritas-ci"
VERITAS_RELEASE_ID = "veritas-guarded-streaming-683346e0-isolated-imports-v4"
VERITAS_RELEASE_ROOT = (
    Path.home() / ".local" / "share" / "midas-veritas" / "releases" / VERITAS_RELEASE_ID
)
VERITAS_RUNTIME_PYTHON = Path.home() / "midas" / ".venv" / "bin" / "python"
VERITAS_RUNTIME_SITE_PACKAGES = (
    VERITAS_RUNTIME_PYTHON.parent.parent
    / "lib"
    / f"python{sys.version_info.major}.{sys.version_info.minor}"
    / "site-packages"
)
VERITAS_APPROVED_SOURCE_REVISION = "5679d4d40715ed762b1efaee37fc541852e9d6f5"
VERITAS_APPROVED_MODULE_SHA256 = "683346e0f14a594528158676343dd1c63e5731fcb2c5beec9739abc96d1898ff"
VERITAS_APPROVED_WRAPPER_SHA256 = "5c912ed80fba851dc75fc6de19df34de3c8d5d3179b4865ffb79a78998291e59"
VERITAS_PRODUCTION_MODULE_SHA256 = (
    "e6304b6547dc5d285baab4aae3940b0fe7a6828712d995bb677aad582a44f016"
)
VERITAS_PRODUCTION_SERVICE_SHA256 = (
    "2da69ab1f132fb1f4ff85ce0f5526ddb7d302b1d8ea67dbba07edcc809d85406"
)
VERITAS_PRODUCTION_IMPORT_DROPIN_SHA256 = (
    "79298fb856ec80ae35124b52c349b6f97cc2f8bd4714b71bda1388c3fc37f896"
)
VERITAS_CAMPAIGN_SHA256 = "aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5"
VERITAS_LEGACY_CODE_SHA256 = "9f9e2249b49dd1cb10c11713aa2683567aa9cf0914c3ed2b08cf8e3fea25ebf8"
VERITAS_APPROVED_RUNTIME_CODE_FILES = {
    "finalized_source_analysis.py": VERITAS_APPROVED_MODULE_SHA256,
    "scripts/veritas_source_analysis.py": VERITAS_APPROVED_WRAPPER_SHA256,
    "economics.py": "0fc69b88d160acd3123bbff38ed6480d9ae9853b48429b3f739200d6cba5eda8",
    "reality/execution_research.py": "99aaf3d1f1d00a3440392f373db8b661c8420ab1bb4713fc9e4fe2340831e5c1",
    "reality/reconstruction.py": "ed7ca007f8fdb62c00aa25ebf4692e0c54eb0a9c0b06c9712e092a87c28c30cb",
    "reality/research_measurements.py": "35200c42beef6c169b7244d56d93b30229c1394217faf4dd072853814f05b084",
    "reality/research_schema.py": "fa31024164ae1e20b579403e79417c1eaa8fc2670d154153aae247546d8f9f33",
    "reality/shadow_campaign.py": "fbca040df77c90182fa7b94375590f89e95289b21e31a8990da390d1241c9aed",
    "reality/shadow_source.py": "6e0cb3811a8e32a81e9003a79de0ab778eccc28ff9e725f2163d58decf31b327",
    "reality/shadow_worker.py": "0b745947399dc33898bdba41df4f0b183ba87477f5dcddecb7ae2d26f29e3c6d",
    "reality/storage.py": "551966d10c2494dd6fcb50988bf32c26558ff6a02d6bd68617f8593b1f5ec3cc",
}
VERITAS_APPROVED_PACKAGE_INIT_FILES = {
    "packages/midas/__init__.py": "4032724b98ed267185b12b8ec78dd9bcb0423ab1c89a6f0dad99397fd51159d9",
    "packages/midas/reality/__init__.py": "4032724b98ed267185b12b8ec78dd9bcb0423ab1c89a6f0dad99397fd51159d9",
    "packages/midas/veritas/__init__.py": "3cf2b6c6f1a1a4c51c55d67b401b3b8bd5d521eaececb0111d3452f3a6d7e4a2",
}
VERITAS_APPROVED_RELEASE_DEPENDENCY_FILES = {
    "packages/midas/arbitrage/__init__.py": "4032724b98ed267185b12b8ec78dd9bcb0423ab1c89a6f0dad99397fd51159d9",
    "packages/midas/arbitrage/engine.py": "5b16c78fc4664b780d7bf899573f2bb15cce83f055fe573eea3e3ea353a29526",
    "packages/midas/core/__init__.py": "4032724b98ed267185b12b8ec78dd9bcb0423ab1c89a6f0dad99397fd51159d9",
    "packages/midas/core/models.py": "9fe2eb524ee305d20fb31df70a4239f2b6504efc67d6c16afc22090410b1c528",
    "packages/midas/economics/__init__.py": "4032724b98ed267185b12b8ec78dd9bcb0423ab1c89a6f0dad99397fd51159d9",
    "packages/midas/economics/attestation.py": "5f614a422158aab5052faecf8064b57c5e04cff0c289b78cc7feb453e1f29899",
    "packages/midas/economics/fees.py": "2735401e5988468582222a262a1e4f9fa28db2f1e549cf7492fb26fc85bdeb7a",
    "packages/midas/reality/foundry.py": "b0559c041e870196ef95fb17f9c0e6e39d541214e3a9b4f5c4e0c70c4e22ee62",
    "packages/midas/reality/model_features.py": "976a0b529ef28250ba6fba3be3b0c8d1c48039975a183b36a359cd1ff88b6634",
    "packages/midas/reality/model_fitting.py": "8f1aa262cc96430180e8d2357ec75ed5449cd940c5e956419a762f2f72302580",
    "packages/midas/reality/model_metrics.py": "a7221014903176b4b1b7927a001081c3d88403b1ca991c565ea40253c0b8a9ba",
    "packages/midas/reality/model_registry.py": "a1807cc5183a4612172ea8664b5df646de5c7f2940192757d018f7b0207ab3e5",
    "packages/midas/reality/shadow_policy.py": "f0a3b1920c7bb5c22ce9153dabe967be24d2210b6a8801808269734d13c3e0dc",
    "packages/midas/reality/shadow_store.py": "75e6c208013ee859a39d0463a12660b521d1c631af6517e1cfd5008a6c42ff00",
    "packages/midas/risk/engine.py": "6e91317dd0e1fb3ad1e1b601af5c753202947c6ae7953fb0a0af53b34e5ba8e6",
}
VERITAS_APPROVED_PYTHON_RUNTIME = {
    "implementation": "cpython",
    "version_major_minor": "3.12",
    "validated_patch_version": "3.12.3",
    "soabi": "cpython-312-x86_64-linux-gnu",
}
VERITAS_APPROVED_DISTRIBUTION_VERSIONS = {
    "annotated-types": "0.8.0",
    "joblib": "1.6.0",
    "numpy": "2.2.6",
    "pydantic": "2.14.0",
    "pydantic-core": "2.50.0",
    "scikit-learn": "1.7.2",
    "scipy": "1.18.1",
    "threadpoolctl": "3.7.0",
    "typing-extensions": "4.16.0",
    "typing-inspection": "0.4.4",
}
VERITAS_RUNTIME_ANALYSIS_CODE_SHA256 = (
    "4f173bb4b3c2d96e231e217bd0753c34b2acaad1a89c11dea096b7b4eb762999"
)
VERITAS_TIMER_UNITS = (
    "midas-veritas-source-analysis.timer",
    "midas-reality-capacity.timer",
)


class AdmissionError(RuntimeError):
    pass


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def verify_veritas_release(
    release_root: Path,
    *,
    expected_release_identity: str,
    expected_source_revision: str,
    expected_module_sha256: str,
) -> dict[str, Any]:
    """Verify the immutable, minimal release selected for a Veritas invocation."""
    root = Path(release_root)
    if root.is_symlink() or not root.is_dir():
        raise AdmissionError("Veritas release root is missing, non-directory, or a symlink")
    root = root.resolve(strict=True)
    if stat.S_IMODE(root.stat().st_mode) & 0o222:
        raise AdmissionError("Veritas release root is writable")

    manifest_path = root / "RELEASE-MANIFEST.json"
    digest_path = root / "RELEASE-MANIFEST.sha256"
    for path in (manifest_path, digest_path):
        if path.is_symlink() or not path.is_file():
            raise AdmissionError(f"Veritas release metadata is missing or unsafe: {path.name}")
        info = path.stat()
        if info.st_uid != os.getuid() or info.st_nlink != 1:
            raise AdmissionError(f"Veritas release metadata ownership is unsafe: {path.name}")
        if stat.S_IMODE(info.st_mode) & 0o222:
            raise AdmissionError(f"Veritas release metadata is writable: {path.name}")
        if info.st_size > 256 * 1024:
            raise AdmissionError(f"Veritas release metadata is oversized: {path.name}")

    manifest_bytes = manifest_path.read_bytes()
    manifest_sha256 = _sha256_bytes(manifest_bytes)
    expected_sidecar = f"{manifest_sha256}  RELEASE-MANIFEST.json\n"
    if digest_path.read_text(encoding="ascii") != expected_sidecar:
        raise AdmissionError("Veritas release manifest checksum does not match its sidecar")
    try:
        manifest = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AdmissionError("Veritas release manifest is invalid JSON") from error
    if not isinstance(manifest, dict) or manifest.get("format") != "midas-veritas-guarded-release":
        raise AdmissionError("Veritas release manifest has an unsupported format")
    if manifest.get("format_version") != 1:
        raise AdmissionError("Veritas release manifest version is unsupported")
    if manifest.get("release_identity") != expected_release_identity:
        raise AdmissionError("Veritas release identity differs from the service pin")
    if manifest.get("source_revision") != expected_source_revision:
        raise AdmissionError("Veritas source revision differs from the service pin")
    if manifest.get("candidate_module_sha256") != expected_module_sha256:
        raise AdmissionError("Veritas module identity differs from the service pin")
    if manifest.get("wrapper_sha256") != VERITAS_APPROVED_WRAPPER_SHA256:
        raise AdmissionError("Veritas wrapper identity differs from the validated package")
    if expected_module_sha256 != VERITAS_APPROVED_MODULE_SHA256:
        raise AdmissionError("the requested Veritas module is not the approved streaming release")
    if expected_source_revision != VERITAS_APPROVED_SOURCE_REVISION:
        raise AdmissionError("the requested Veritas source revision is not approved")
    if expected_release_identity != VERITAS_RELEASE_ID:
        raise AdmissionError("the requested Veritas release identity is not approved")

    files = manifest.get("files_sha256")
    if not isinstance(files, dict) or not files:
        raise AdmissionError("Veritas release manifest has no file hash inventory")
    expected_runtime_code = manifest.get("runtime_analysis_code_files")
    if expected_runtime_code != VERITAS_APPROVED_RUNTIME_CODE_FILES:
        raise AdmissionError("Veritas runtime dependency identities differ from the tested set")
    runtime_digest = _sha256_bytes(_canonical_json(expected_runtime_code))
    if (
        runtime_digest != VERITAS_RUNTIME_ANALYSIS_CODE_SHA256
        or manifest.get("runtime_analysis_code_sha256") != runtime_digest
    ):
        raise AdmissionError("Veritas runtime analysis identity is inconsistent")
    if manifest.get("package_init_files_sha256") != VERITAS_APPROVED_PACKAGE_INIT_FILES:
        raise AdmissionError(
            "Veritas package initializers differ from the tested production overlay"
        )
    release_dependencies = manifest.get("release_dependency_files_sha256")
    if release_dependencies != VERITAS_APPROVED_RELEASE_DEPENDENCY_FILES:
        raise AdmissionError("Veritas transitive runtime dependency identities are unapproved")
    if any(files.get(path) != digest for path, digest in release_dependencies.items()):
        raise AdmissionError("Veritas transitive runtime dependency hash mismatch")
    python_runtime = manifest.get("python_runtime")
    if python_runtime != VERITAS_APPROVED_PYTHON_RUNTIME:
        raise AdmissionError(
            "Veritas Python runtime identity differs from the validated environment"
        )
    if (
        sys.implementation.name != python_runtime["implementation"]
        or f"{sys.version_info.major}.{sys.version_info.minor}"
        != python_runtime["version_major_minor"]
        or f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        != python_runtime["validated_patch_version"]
        or sysconfig.get_config_var("SOABI") != python_runtime["soabi"]
    ):
        raise AdmissionError("Veritas Python interpreter or ABI differs from the validated runtime")
    distribution_versions = manifest.get("python_distribution_versions")
    if distribution_versions != VERITAS_APPROVED_DISTRIBUTION_VERSIONS:
        raise AdmissionError("Veritas Python distribution identities are unapproved")
    try:
        installed_distributions = {
            name: importlib.metadata.version(name) for name in distribution_versions
        }
    except importlib.metadata.PackageNotFoundError as error:
        raise AdmissionError("A required Veritas runtime distribution is missing") from error
    if installed_distributions != distribution_versions:
        raise AdmissionError(
            "Installed Veritas runtime distribution versions differ from the release"
        )

    runtime_paths = {
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
    for identity, relative in runtime_paths.items():
        if files.get(relative) != expected_runtime_code[identity]:
            raise AdmissionError(f"Veritas release dependency hash mismatch: {identity}")
    if any(
        files.get(path) != digest for path, digest in VERITAS_APPROVED_PACKAGE_INIT_FILES.items()
    ):
        raise AdmissionError("Veritas package initializer file hash mismatch")
    if files.get("bin/midas_resource_preflight.py") != manifest.get("launcher_sha256"):
        raise AdmissionError("Veritas guarded launcher identity is missing from the manifest")
    if files.get("service/midas-veritas-source-analysis.service") != manifest.get("service_sha256"):
        raise AdmissionError("Veritas service integration identity is missing from the manifest")
    if manifest.get("rollback_module_sha256") != VERITAS_PRODUCTION_MODULE_SHA256:
        raise AdmissionError("Veritas rollback identity differs from the current production module")
    rollback_files = {
        "rollback/previous-finalized_source_analysis.py": VERITAS_PRODUCTION_MODULE_SHA256,
        "rollback/midas-veritas-source-analysis.service": VERITAS_PRODUCTION_SERVICE_SHA256,
        "rollback/20-frozen-campaign-import.conf": VERITAS_PRODUCTION_IMPORT_DROPIN_SHA256,
    }
    if manifest.get("rollback_artifacts_sha256") != rollback_files:
        raise AdmissionError(
            "Veritas release rollback artifacts differ from the verified production set"
        )
    if any(files.get(path) != digest for path, digest in rollback_files.items()):
        raise AdmissionError("Veritas release is missing an exact rollback artifact")
    if manifest.get("campaign_sha256") != VERITAS_CAMPAIGN_SHA256:
        raise AdmissionError("Veritas campaign identity differs from the approved campaign")
    launcher_revision = manifest.get("launcher_source_revision")
    if not isinstance(launcher_revision, str) or not re.fullmatch(
        r"[0-9a-f]{40}", launcher_revision
    ):
        raise AdmissionError(
            "Veritas release does not contain the validated guarded launcher revision"
        )
    release_revision = manifest.get("release_source_revision")
    if not isinstance(release_revision, str) or not re.fullmatch(r"[0-9a-f]{40}", release_revision):
        raise AdmissionError("Veritas release source revision is missing or malformed")
    if release_revision != launcher_revision:
        raise AdmissionError("Veritas release and guarded launcher revisions differ")

    actual_files: set[str] = set()
    for directory, child_dirs, child_files in os.walk(root, topdown=True, followlinks=False):
        directory_path = Path(directory)
        if stat.S_IMODE(directory_path.stat().st_mode) & 0o222:
            raise AdmissionError(f"Veritas release directory is writable: {directory_path}")
        for name in child_dirs:
            child = directory_path / name
            if child.is_symlink() or not child.is_dir():
                raise AdmissionError(f"Veritas release contains an unsafe directory: {child}")
        for name in child_files:
            path = directory_path / name
            relative = path.relative_to(root).as_posix()
            if relative in {"RELEASE-MANIFEST.json", "RELEASE-MANIFEST.sha256"}:
                continue
            if path.is_symlink() or not path.is_file():
                raise AdmissionError(f"Veritas release contains an unsafe file: {relative}")
            info = path.stat()
            if info.st_uid != os.getuid() or info.st_nlink != 1:
                raise AdmissionError(f"Veritas release file ownership is unsafe: {relative}")
            if stat.S_IMODE(info.st_mode) & 0o222:
                raise AdmissionError(f"Veritas release file is writable: {relative}")
            actual_files.add(relative)
            expected = files.get(relative)
            if not isinstance(expected, str) or _sha256_bytes(path.read_bytes()) != expected:
                raise AdmissionError(f"Veritas release file hash mismatch: {relative}")
    if actual_files != set(files):
        raise AdmissionError("Veritas release file set differs from the immutable manifest")
    if len(actual_files) != len(files):
        raise AdmissionError("Veritas release manifest contains duplicate file paths")
    service_path = root / "service" / "midas-veritas-source-analysis.service"
    service_text = service_path.read_text(encoding="utf-8")
    service_lines = [line.strip() for line in service_text.splitlines() if line.strip()]
    exec_starts = [
        line.partition("=")[2] for line in service_lines if line.startswith("ExecStart=")
    ]
    if len(exec_starts) != 1:
        raise AdmissionError("Veritas service must have exactly one execution owner")
    if any(
        line.startswith(("ExecStartPre=", "ExecStartPost=", "ExecStop=", "ExecStopPost="))
        for line in service_lines
    ):
        raise AdmissionError("Veritas service contains an alternate execution path")
    expected_execstart = [
        part.replace(str(Path.home()), "%h") for part in _expected_veritas_service_execstart()
    ]
    try:
        packaged_execstart = shlex.split(exec_starts[0])
    except ValueError as error:
        raise AdmissionError("Packaged Veritas service ExecStart is malformed") from error
    if packaged_execstart != expected_execstart:
        raise AdmissionError("Packaged Veritas service does not invoke the pinned guarded launcher")
    for required in (
        "Type=oneshot",
        f"--release-identity {VERITAS_RELEASE_ID}",
        f"--source-revision {VERITAS_APPROVED_SOURCE_REVISION}",
        f"--expected-module-sha256 {VERITAS_APPROVED_MODULE_SHA256}",
        "--profile veritas",
        f"--release-root %h/.local/share/midas-veritas/releases/{VERITAS_RELEASE_ID}",
        f"--expected-module-sha256 {VERITAS_APPROVED_MODULE_SHA256}",
        "Restart=no",
        "KillMode=control-group",
        "UnsetEnvironment=PYTHONPATH",
        "ProtectSystem=strict",
        "ProtectHome=read-only",
        "NoNewPrivileges=true",
    ):
        if required not in service_text:
            raise AdmissionError(f"Veritas service unit does not pin {required}")
    return {
        "passed": True,
        "release_identity": expected_release_identity,
        "source_revision": expected_source_revision,
        "manifest_sha256": manifest_sha256,
        "module_sha256": expected_module_sha256,
        "wrapper_sha256": VERITAS_APPROVED_WRAPPER_SHA256,
        "launcher_sha256": manifest["launcher_sha256"],
        "service_sha256": manifest["service_sha256"],
        "runtime_analysis_code_sha256": runtime_digest,
        "runtime_analysis_code_files": expected_runtime_code,
        "release_dependency_files_sha256": release_dependencies,
        "python_runtime": python_runtime,
        "python_distribution_versions": distribution_versions,
        "file_count": len(actual_files),
    }


def _veritas_worker_command(
    release_root: Path, *, output_root: Path = VERITAS_OUTPUT_ROOT
) -> list[str]:
    return [
        str(VERITAS_RUNTIME_PYTHON),
        "-S",
        str(release_root / "scripts" / "veritas_source_analysis.py"),
        "--root",
        str(output_root),
        "--max-segments",
        "128",
        "--max-source-mib",
        "32",
    ]


def _validate_veritas_worker_command(
    command: list[str],
    release_root: Path,
    expected_module_sha256: str,
    *,
    output_root: Path = VERITAS_OUTPUT_ROOT,
) -> dict[str, Any]:
    if expected_module_sha256 != VERITAS_APPROVED_MODULE_SHA256:
        raise AdmissionError("Veritas invocation module hash is not the approved streaming build")
    if Path(release_root) != VERITAS_RELEASE_ROOT:
        raise AdmissionError("Veritas invocation selected an unapproved release path")
    expected = _veritas_worker_command(release_root, output_root=output_root)
    if command != expected:
        raise AdmissionError(
            "Veritas worker command differs from the fixed bounded release command"
        )
    return verify_veritas_release(
        release_root,
        expected_release_identity=VERITAS_RELEASE_ID,
        expected_source_revision=VERITAS_APPROVED_SOURCE_REVISION,
        expected_module_sha256=expected_module_sha256,
    )


def _validate_veritas_run_limits(args: argparse.Namespace) -> None:
    if (
        args.memory_high_mib > VERITAS_RUN_LIMITS["memory_high_mib"]
        or args.memory_max_mib != VERITAS_RUN_LIMITS["memory_max_mib"]
        or args.memory_budget_mib > VERITAS_RUN_LIMITS["memory_budget_mib"]
        or args.cpu_quota_percent > VERITAS_RUN_LIMITS["cpu_quota_percent"]
        or args.timeout_seconds > VERITAS_RUN_LIMITS["timeout_seconds"]
        or args.sample_seconds < 30
    ):
        raise AdmissionError(
            "Veritas service must stay within MemoryHigh=192 MiB, MemoryMax=256 MiB, "
            "a 128 MiB task budget, CPUQuota=100%, a 600-second timeout, and a "
            "30-second admission sample"
        )


def verify_veritas_checkpoint(
    root: Path,
    release: dict[str, Any],
    *,
    expected_campaign_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate the sealed checkpoint identity before a worker can migrate or resume it."""
    expected_campaign_sha256 = expected_campaign_sha256 or VERITAS_CAMPAIGN_SHA256

    def read_state(name: str) -> dict[str, Any] | None:
        path = root / name
        if not path.exists() and not path.is_symlink():
            return None
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 24 * MIB:
            raise AdmissionError(f"Veritas checkpoint is missing or unsafe: {name}")
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AdmissionError(f"Veritas checkpoint is unreadable: {name}") from error
        if not isinstance(state, dict):
            raise AdmissionError(f"Veritas checkpoint is not an object: {name}")
        stored_digest = state.get("state_sha256")
        body = {key: value for key, value in state.items() if key != "state_sha256"}
        if (
            not isinstance(stored_digest, str)
            or _sha256_bytes(_canonical_json(body)) != stored_digest
        ):
            raise AdmissionError(f"Veritas checkpoint seal is invalid: {name}")
        return state

    legacy = read_state("source-analysis-state-v1.json")
    current = read_state("source-analysis-state-v2.json")
    if legacy is None and current is None:
        raise AdmissionError("Veritas checkpoint is absent; refusing to initialize research state")

    def common(state: dict[str, Any], *, schema: int, code_sha256: str) -> None:
        if (
            state.get("schema_version") != schema
            or state.get("analysis_version") != "veritas-finalized-reality-source-analysis-v1"
            or state.get("campaign_sha256") != expected_campaign_sha256
            or state.get("analysis_code_sha256") != code_sha256
        ):
            raise AdmissionError(f"Veritas schema-{schema} checkpoint is incompatible")
        for field in ("processed_segment_count", "last_ordinal", "processed_source_bytes"):
            value = state.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise AdmissionError(f"Veritas checkpoint cursor field is invalid: {field}")
        for field in ("last_event_sha256", "prefix_catalog_sha256"):
            value = state.get(field)
            if value is not None and (
                not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
            ):
                raise AdmissionError(f"Veritas checkpoint digest is invalid: {field}")

    chosen: dict[str, Any] | None
    if legacy is not None:
        common(legacy, schema=1, code_sha256=VERITAS_LEGACY_CODE_SHA256)
        legacy_files = legacy.get("analysis_code_files")
        if (
            not isinstance(legacy_files, dict)
            or _sha256_bytes(_canonical_json(legacy_files)) != VERITAS_LEGACY_CODE_SHA256
        ):
            raise AdmissionError("Veritas legacy runtime provenance is invalid")
    if current is not None:
        common(current, schema=2, code_sha256=release["runtime_analysis_code_sha256"])
        if current.get("analysis_code_files") != release["runtime_analysis_code_files"]:
            raise AdmissionError(
                "Veritas v2 checkpoint dependency provenance differs from the release"
            )
        migration = current.get("migration")
        if not isinstance(migration, dict) or migration.get("from_state_schema_version") != 1:
            raise AdmissionError("Veritas v2 checkpoint has no supported v1 migration lineage")
        if migration.get("to_analysis_code_sha256") != release["runtime_analysis_code_sha256"]:
            raise AdmissionError("Veritas migration provenance targets different runtime code")
        if legacy is not None and (
            migration.get("from_state_sha256") != legacy.get("state_sha256")
            or migration.get("from_processed_segment_count")
            != legacy.get("processed_segment_count")
        ):
            raise AdmissionError("Veritas v2 migration lineage differs from the preserved v1 state")
        chosen = current
    else:
        chosen = legacy
    assert chosen is not None
    return {
        "passed": True,
        "schema_version": chosen["schema_version"],
        "state_sha256": chosen["state_sha256"],
        "campaign_sha256": chosen["campaign_sha256"],
        "analysis_code_sha256": chosen["analysis_code_sha256"],
        "processed_segment_count": chosen["processed_segment_count"],
        "last_ordinal": chosen["last_ordinal"],
        "processed_source_bytes": chosen["processed_source_bytes"],
        "last_event_sha256": chosen.get("last_event_sha256"),
        "prefix_catalog_sha256": chosen.get("prefix_catalog_sha256"),
        "legacy_state_sha256": legacy.get("state_sha256") if legacy else None,
    }


def verify_veritas_post_execution_state(
    root: Path,
    release: dict[str, Any],
    checkpoint_before: dict[str, Any],
    *,
    expected_campaign_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate the committed v2 checkpoint and bounded summary before reporting success."""
    expected_campaign_sha256 = expected_campaign_sha256 or VERITAS_CAMPAIGN_SHA256
    checkpoint = verify_veritas_checkpoint(
        root, release, expected_campaign_sha256=expected_campaign_sha256
    )
    if checkpoint["schema_version"] != 2:
        raise AdmissionError("successful Veritas execution did not produce a v2 checkpoint")
    if checkpoint["campaign_sha256"] != checkpoint_before["campaign_sha256"]:
        raise AdmissionError("Veritas campaign identity changed during execution")
    if checkpoint["analysis_code_sha256"] != release["runtime_analysis_code_sha256"]:
        raise AdmissionError("Veritas checkpoint provenance does not match the selected release")

    monotonic_fields = (
        "processed_segment_count",
        "last_ordinal",
        "processed_source_bytes",
    )
    for field in monotonic_fields:
        if checkpoint[field] < checkpoint_before[field]:
            raise AdmissionError(f"Veritas checkpoint cursor regressed: {field}")

    summary_path = root / "source-research-summary.json"
    if (
        summary_path.is_symlink()
        or not summary_path.is_file()
        or summary_path.stat().st_size > 4 * MIB
    ):
        raise AdmissionError("Veritas post-execution summary is missing or unsafe")
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AdmissionError("Veritas post-execution summary is unreadable") from error
    if not isinstance(summary, dict):
        raise AdmissionError("Veritas post-execution summary is not an object")
    if (
        summary.get("schema_version") != 1
        or summary.get("analysis_version") != "veritas-finalized-reality-source-analysis-v1"
        or summary.get("active_segment_read") is not False
        or summary.get("status") not in {"current", "catching_up"}
    ):
        raise AdmissionError("Veritas post-execution summary has incompatible semantics")
    summary_digest = summary.get("summary_sha256")
    summary_body = {key: value for key, value in summary.items() if key != "summary_sha256"}
    if (
        not isinstance(summary_digest, str)
        or _sha256_bytes(_canonical_json(summary_body)) != summary_digest
    ):
        raise AdmissionError("Veritas post-execution summary seal is invalid")
    for field in (
        "processed_segment_count",
        "processed_source_bytes",
        "last_processed_ordinal",
    ):
        value = summary.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise AdmissionError(f"Veritas summary cursor field is invalid: {field}")
    for field in (
        "campaign_sha256",
        "analysis_code_sha256",
        "processed_segment_count",
        "processed_source_bytes",
        "prefix_catalog_sha256",
    ):
        if summary.get(field) != checkpoint[field]:
            raise AdmissionError(f"Veritas summary and checkpoint disagree: {field}")
    if summary["last_processed_ordinal"] != checkpoint["last_ordinal"]:
        raise AdmissionError("Veritas summary and checkpoint disagree: last ordinal")

    batch_count = summary.get("batch_processed_segment_count")
    batch_bytes = summary.get("batch_processed_source_bytes")
    if (
        not isinstance(batch_count, int)
        or isinstance(batch_count, bool)
        or not 0 <= batch_count <= 128
        or not isinstance(batch_bytes, int)
        or isinstance(batch_bytes, bool)
        or not 0 <= batch_bytes <= 32 * MIB
        or checkpoint["processed_segment_count"] - checkpoint_before["processed_segment_count"]
        != batch_count
        or checkpoint["processed_source_bytes"] - checkpoint_before["processed_source_bytes"]
        != batch_bytes
    ):
        raise AdmissionError("Veritas committed progress exceeds or differs from the bounded batch")
    if batch_count == 0:
        for field in ("last_ordinal", "last_event_sha256", "prefix_catalog_sha256"):
            if checkpoint[field] != checkpoint_before[field]:
                raise AdmissionError(
                    f"Veritas state changed without committed batch progress: {field}"
                )
    elif (
        checkpoint["last_ordinal"] <= checkpoint_before["last_ordinal"]
        or checkpoint["last_event_sha256"] == checkpoint_before["last_event_sha256"]
        or checkpoint["prefix_catalog_sha256"] == checkpoint_before["prefix_catalog_sha256"]
    ):
        raise AdmissionError(
            "Veritas committed progress lacks event and catalog cursor advancement"
        )

    return {
        **checkpoint,
        "summary_sha256": summary_digest,
        "batch_processed_segment_count": batch_count,
        "batch_processed_source_bytes": batch_bytes,
        "status": summary.get("status"),
        "readiness": summary.get("readiness"),
    }


class GuardedExecutionInterrupted(Exception):
    def __init__(self, signum: int) -> None:
        super().__init__(f"guarded execution interrupted by signal {signum}")
        self.signum = signum


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _prepare_receipt_directory(path: Path) -> Path:
    path = path.expanduser()
    if path.is_symlink():
        raise AdmissionError(f"execution receipt directory must not be a symlink: {path}")
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = path.stat(follow_symlinks=False)
    except OSError as error:
        raise AdmissionError(f"cannot prepare execution receipt directory: {error}") from error
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise AdmissionError("execution receipt directory must be owned by the current user")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise AdmissionError("execution receipt directory permissions must be 0700 or stricter")
    return path.absolute()


def _atomic_json_write(path: Path, payload: dict[str, Any], *, mode: int = 0o600) -> None:
    encoded = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if len(encoded) > GUARDED_RECEIPT_MAX_BYTES:
        raise AdmissionError("execution receipt exceeded its size bound")
    if path.is_symlink() or not path.parent.is_dir():
        raise AdmissionError("execution receipt target or parent is missing or unsafe")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(temporary, flags, mode)
    try:
        try:
            os.fchmod(descriptor, mode)
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _read_bounded_json(path: Path, *, maximum: int = GUARDED_RECEIPT_MAX_BYTES) -> dict[str, Any]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
            raise AdmissionError(
                f"execution status file is not a bounded regular file: {path.name}"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read(maximum + 1)
    finally:
        os.close(descriptor)
    if len(raw) > maximum:
        raise AdmissionError(f"execution status file exceeded its size bound: {path.name}")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise AdmissionError(f"execution status file has an invalid shape: {path.name}")
    return value


def _command_identity(command: list[str]) -> dict[str, Any]:
    executable = Path(command[0]).name if command else ""
    argument_shape = [
        argument.partition("=")[0] if argument.startswith("-") else "<value>"
        for argument in command[1:]
    ]
    encoded = json.dumps(
        [executable, argument_shape], separators=(",", ":"), ensure_ascii=True
    ).encode()
    return {
        "executable_name": executable[:128],
        "argument_count": len(command),
        "argument_shape_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _synthetic_expected_exit(command: list[str]) -> int:
    expected = SYNTHETIC_TEST_COMMANDS.get(tuple(command))
    if expected is None:
        raise AdmissionError(
            "synthetic-validation accepts only /usr/bin/true, /usr/bin/false, or /usr/bin/sleep 1"
        )
    try:
        resolved = Path(command[0]).resolve(strict=True)
        metadata = resolved.stat()
    except OSError as error:
        raise AdmissionError(f"synthetic validation executable is unavailable: {error}") from error
    if (
        not resolved.is_file()
        or metadata.st_uid != 0
        or metadata.st_mode & 0o022
        or not os.access(resolved, os.X_OK)
    ):
        raise AdmissionError("synthetic validation executable is not a trusted root-owned binary")
    return expected


def _require_host_ip_socket_support() -> None:
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            candidate = socket.socket(family, socket.SOCK_STREAM)
        except OSError as error:
            raise AdmissionError(
                f"cannot prove systemd blocks IP sockets because family {family} is unavailable"
            ) from error
        candidate.close()


def _prepare_synthetic_test_root() -> Path:
    root = SYNTHETIC_TEST_ROOT
    if root.parent != Path("/var/tmp") or root.parent.is_symlink() or not root.parent.is_dir():
        raise AdmissionError("synthetic validation root must be directly under a safe /var/tmp")
    if root.is_symlink():
        raise AdmissionError("synthetic validation root must not be a symlink")
    try:
        root.mkdir(mode=0o700, exist_ok=True)
        metadata = root.stat(follow_symlinks=False)
    except OSError as error:
        raise AdmissionError(f"cannot prepare synthetic validation root: {error}") from error
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise AdmissionError("synthetic validation root must be user-owned with mode 0700")
    return root


def _validate_synthetic_limits(args: argparse.Namespace, command: list[str]) -> int:
    expected_exit = _synthetic_expected_exit(command)
    _require_host_ip_socket_support()
    if (
        args.memory_high_mib != SYNTHETIC_RUN_LIMITS["memory_high_mib"]
        or args.memory_max_mib != SYNTHETIC_RUN_LIMITS["memory_max_mib"]
        or args.memory_budget_mib > SYNTHETIC_RUN_LIMITS["memory_budget_mib"]
        or args.cpu_quota_percent != SYNTHETIC_RUN_LIMITS["cpu_quota_percent"]
        or not 0 < args.timeout_seconds <= SYNTHETIC_RUN_LIMITS["timeout_seconds"]
        or not 1 <= args.sample_seconds <= SYNTHETIC_RUN_LIMITS["max_sample_seconds"]
        or args.termination_grace_seconds < 0
        or args.termination_grace_seconds > 1
        or args.storage_required_mib != 0
        or args.storage_reserve_mib != 0
    ):
        raise AdmissionError("synthetic-validation limits exceed its fixed short-run profile")
    root = _prepare_synthetic_test_root()
    try:
        launcher_path = Path(__file__).resolve(strict=True)
        launcher_stat = launcher_path.stat()
    except OSError as error:
        raise AdmissionError(f"synthetic launcher identity is unavailable: {error}") from error
    if (
        not launcher_path.is_relative_to(root.resolve())
        or launcher_stat.st_uid != os.getuid()
        or launcher_stat.st_mode & 0o222
        or not stat.S_ISREG(launcher_stat.st_mode)
    ):
        raise AdmissionError("synthetic-validation must use its private staged launcher copy")
    paths = [Path(path).resolve() for path in args.storage_path]
    if paths != [root.resolve()]:
        raise AdmissionError(
            "synthetic-validation storage may only reference its private test root"
        )
    if args.memory_budget_mib <= 0:
        raise AdmissionError("synthetic-validation memory budget must be positive")
    return expected_exit


def _compact_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "sampled_at_utc",
        "decision",
        "blocking_reasons",
        "host_memory",
        "pressure",
        "pressure_samples",
        "protected_service_cgroups",
        "user_manager_cgroup",
        "active_midas_worker_services",
        "storage",
        "task_cgroup",
        "planned_cgroup",
    )
    return {key: evidence[key] for key in keys if key in evidence}


def _new_execution_receipt(
    args: argparse.Namespace, command: list[str], receipt_dir: Path
) -> tuple[dict[str, Any], Path, Path]:
    _prune_execution_receipts(receipt_dir, reserve_slot=True)
    invocation_id = uuid.uuid4().hex
    unit_label = "veritas" if args.profile == "veritas" else args.label
    safe_label = re.sub(r"[^a-zA-Z0-9_-]+", "-", unit_label).strip("-")[:24] or "task"
    unit_type = "service" if args.profile in {"veritas", "synthetic-validation"} else "scope"
    unit_prefix = (
        "midas-synthetic-validation" if args.profile == "synthetic-validation" else "midas-heavy"
    )
    unit = f"{unit_prefix}-{safe_label}-{invocation_id[:12]}.{unit_type}"
    status_dir = receipt_dir / f"{invocation_id}.control"
    status_dir.mkdir(mode=0o700, exist_ok=False)
    os.chmod(status_dir, 0o700)
    receipt_path = receipt_dir / f"{invocation_id}.json"
    status_path = status_dir / "inner-status.json"
    receipt: dict[str, Any] = {
        "format": "midas-guarded-execution-receipt",
        "format_version": GUARDED_RECEIPT_VERSION,
        "invocation_id": invocation_id,
        "created_at_utc": _utc_now(),
        "updated_at_utc": _utc_now(),
        "completed_at_utc": None,
        "phase": "created",
        "final_classification": "indeterminate",
        "source_revision": args.source_revision or None,
        "release_identity": args.release_identity or None,
        "profile": args.profile,
        "execution_scope": (
            "isolated_systemd_ci_synthetic_research_fixture"
            if getattr(args, "ci_test_context", None)
            else (
                "disposable_synthetic_validation"
                if args.profile == "synthetic-validation"
                else "bounded_operational_work"
            )
        ),
        "production_admission": (
            args.profile != "synthetic-validation"
            and not bool(getattr(args, "ci_test_context", None))
        ),
        "command_identity": _command_identity(command),
        "resource_limits": {
            "memory_high_mib": args.memory_high_mib,
            "memory_max_mib": args.memory_max_mib,
            "memory_budget_mib": args.memory_budget_mib,
            "memory_swap_max_bytes": 0
            if args.profile in {"veritas", "synthetic-validation"}
            else None,
            "cpu_quota_percent": args.cpu_quota_percent,
            "timeout_seconds": args.timeout_seconds,
            "runtime_max_seconds": args.timeout_seconds,
            "io_weight": 10,
            "tasks_max": (
                SYNTHETIC_RUN_LIMITS["tasks_max"]
                if args.profile == "synthetic-validation"
                else None
            ),
        },
        "outer_admission": {"decision": "pending"},
        "inner_admission": {"decision": "pending"},
        "transient_unit": {
            "name": unit,
            "type": unit_type,
            "invocation_id": None,
            "last_observed_state": "not_requested",
        },
        "worker": {"start_confirmed": False, "start_observed_at_utc": None},
        "inner_status_record": None,
        "watchdog_interventions": [],
        "cancellation_results": [],
        "cgroup_metrics": {},
        "result": {
            "final_classification": "indeterminate",
            "runner_exit_code": None,
            "worker_exit_code": None,
            "termination_signal": None,
        },
        "log_references": {
            "journal_unit": f"journalctl --user --unit={unit}",
            "journal_invocation": None,
        },
        "artifacts": {
            "receipt": str(receipt_path),
            "inner_status": str(status_path),
            "inner_status_retained": True,
        },
    }
    if getattr(args, "ci_test_context", None):
        receipt["validation_mode"] = "isolated_systemd_ci"
    try:
        _atomic_json_write(receipt_path, receipt)
    except (OSError, AdmissionError):
        try:
            shutil.rmtree(status_dir)
        except OSError:
            pass
        raise
    _prune_execution_receipts(receipt_dir)
    return receipt, receipt_path, status_path


def _update_execution_receipt(
    receipt: dict[str, Any], path: Path, *, phase: str, **values: Any
) -> None:
    receipt["phase"] = phase
    receipt["updated_at_utc"] = _utc_now()
    receipt.update(values)
    _atomic_json_write(path, receipt)


def _finish_execution_receipt(
    receipt: dict[str, Any],
    path: Path,
    *,
    classification: str,
    exit_code: int | None,
    termination_signal: int | None = None,
    detail: str | None = None,
) -> None:
    result = dict(receipt.get("result", {}))
    result.update(
        final_classification=classification,
        runner_exit_code=exit_code,
        termination_signal=termination_signal,
    )
    if detail:
        result["detail"] = detail[:512]
    receipt["result"] = result
    receipt["final_classification"] = classification
    receipt["phase"] = "completed"
    receipt["updated_at_utc"] = _utc_now()
    receipt["completed_at_utc"] = receipt["updated_at_utc"]
    _atomic_json_write(path, receipt)
    _prune_execution_receipts(path.parent)


def _try_finish_execution_receipt(
    receipt: dict[str, Any],
    path: Path,
    *,
    classification: str,
    exit_code: int | None,
    termination_signal: int | None = None,
    detail: str | None = None,
) -> bool:
    try:
        _finish_execution_receipt(
            receipt,
            path,
            classification=classification,
            exit_code=exit_code,
            termination_signal=termination_signal,
            detail=detail,
        )
        return True
    except (OSError, AdmissionError) as error:
        result = dict(receipt.get("result", {}))
        result.update(
            final_classification="indeterminate",
            runner_exit_code=RUNNER_RESULT_MISSING,
            termination_signal=None,
            detail=f"final receipt persistence failed: {_safe_diagnostic(str(error))}"[:512],
        )
        receipt["result"] = result
        receipt["final_classification"] = "indeterminate"
        receipt["phase"] = "finalization_failed"
        receipt["completed_at_utc"] = None
        receipt["updated_at_utc"] = _utc_now()
        try:
            _atomic_json_write(path, receipt)
        except (OSError, AdmissionError):
            pass
        return False


def _remove_receipt_control_directory(directory: Path, receipt: dict[str, Any]) -> None:
    invocation_id = receipt.get("invocation_id")
    artifacts = receipt.get("artifacts")
    status_value = artifacts.get("inner_status") if isinstance(artifacts, dict) else None
    if not isinstance(invocation_id, str) or not re.fullmatch(r"[0-9a-f]{32}", invocation_id):
        return
    if not isinstance(status_value, str):
        return
    status_path = Path(status_value)
    control_dir = directory / f"{invocation_id}.control"
    if (
        status_path.name != "inner-status.json"
        or status_path.parent != control_dir
        or control_dir.is_symlink()
    ):
        return
    try:
        shutil.rmtree(control_dir)
    except OSError:
        pass


def _prune_execution_receipts(directory: Path, *, reserve_slot: bool = False) -> None:
    receipts: list[tuple[float, Path, bool]] = []
    opaque_count = 0
    stale_before = time.time() - GUARDED_RECEIPT_TEMP_MAX_AGE_SECONDS
    for path in directory.glob(".*.json.*.*.tmp"):
        try:
            info = path.stat(follow_symlinks=False)
            if (
                stat.S_ISREG(info.st_mode)
                and info.st_uid == os.getuid()
                and info.st_mtime < stale_before
            ):
                path.unlink()
        except OSError:
            pass
    for path in directory.glob("*.json"):
        try:
            info = path.stat(follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_size > GUARDED_RECEIPT_MAX_BYTES:
                opaque_count += 1
                continue
            value = _read_bounded_json(path)
            is_completed = value.get("final_classification") not in {None, "indeterminate"}
            receipts.append((info.st_mtime, path, is_completed))
        except (OSError, ValueError, AdmissionError, json.JSONDecodeError):
            opaque_count += 1
            continue
    completed_receipts = sorted((row for row in receipts if row[2]), reverse=True)
    removed_receipts = 0
    for _mtime, path, _done in completed_receipts[GUARDED_RECEIPT_KEEP_COMPLETED:]:
        try:
            value = _read_bounded_json(path)
            path.unlink()
        except OSError:
            pass
        except (ValueError, AdmissionError, json.JSONDecodeError):
            continue
        else:
            removed_receipts += 1
            _remove_receipt_control_directory(directory, value)
    retained_count = len(receipts) - removed_receipts + opaque_count
    if reserve_slot and retained_count >= GUARDED_RECEIPT_MAX_FILES:
        raise AdmissionError(
            "guarded execution receipt capacity is full; review indeterminate receipts"
        )


def _write_inner_status(
    path: Path,
    invocation_id: str,
    *,
    phase: str,
    decision: str | None = None,
    evidence: dict[str, Any] | None = None,
    **values: Any,
) -> None:
    status: dict[str, Any] = {
        "format": "midas-guarded-inner-status",
        "format_version": GUARDED_RECEIPT_VERSION,
        "invocation_id": invocation_id,
        "updated_at_utc": _utc_now(),
        "phase": phase,
    }
    if decision:
        status["decision"] = decision
    if evidence is not None:
        status["admission_evidence"] = _compact_evidence(evidence)
    status.update(values)
    _atomic_json_write(path, status)


def _read_inner_status(path: Path, invocation_id: str) -> dict[str, Any] | None:
    try:
        value = _read_bounded_json(path)
    except (OSError, ValueError, AdmissionError, json.JSONDecodeError):
        return None
    if (
        value.get("format") != "midas-guarded-inner-status"
        or value.get("format_version") != GUARDED_RECEIPT_VERSION
        or value.get("invocation_id") != invocation_id
    ):
        return None
    return value


def parse_meminfo(text: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in text.splitlines():
        match = re.fullmatch(r"([A-Za-z_()]+):\s+(\d+)\s+kB", line)
        if match:
            result[match.group(1)] = int(match.group(2)) * 1024
    required = {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}
    missing = required - result.keys()
    if missing:
        raise AdmissionError(f"missing /proc/meminfo values: {', '.join(sorted(missing))}")
    return result


def parse_psi(text: str) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        values: dict[str, float] = {}
        for field in parts[1:]:
            key, sep, value = field.partition("=")
            if sep and key.startswith("avg"):
                number = float(value)
                if not math.isfinite(number) or number < 0:
                    raise AdmissionError("PSI average is not finite and nonnegative")
                values[key] = number
        result[parts[0]] = values
    return result


def parse_vmstat(text: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in text.splitlines():
        key, _, value = line.partition(" ")
        if key in {"pswpin", "pswpout"}:
            result[key] = int(value)
    if set(result) != {"pswpin", "pswpout"}:
        raise AdmissionError("swap activity counters are missing from /proc/vmstat")
    return result


def _systemctl(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            ["systemctl", "--user", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AdmissionError(f"systemd user-manager inspection failed: {error}") from error
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise AdmissionError(f"systemd user-manager inspection failed: {detail}")
    return result


UNIT_RECEIPT_PROPERTIES = (
    "LoadState",
    "Transient",
    "FragmentPath",
    "ActiveState",
    "SubState",
    "Result",
    "InvocationID",
    "MainPID",
    "ControlPID",
    "ExecMainCode",
    "ExecMainStatus",
    "ExecMainStartTimestamp",
    "ExecMainExitTimestamp",
    "ActiveEnterTimestamp",
    "InactiveEnterTimestamp",
    "ControlGroup",
    "MemoryHigh",
    "MemoryMax",
    "MemorySwapMax",
    "CPUQuotaPerSecUSec",
    "Nice",
    "IOSchedulingClass",
    "IOWeight",
    "RuntimeMaxUSec",
    "TasksMax",
    "NoNewPrivileges",
    "RestrictAddressFamilies",
    "SystemCallArchitectures",
    "KillMode",
    "Restart",
)


def _unit_snapshot(unit: str) -> dict[str, str] | None:
    args = ["show", unit]
    for prop in UNIT_RECEIPT_PROPERTIES:
        args.extend(("-p", prop))
    try:
        result = _systemctl(*args, check=False)
    except AdmissionError:
        return None
    if result.returncode != 0:
        return None
    props = _properties(result.stdout)
    return props if props.get("LoadState") not in {None, "not-found"} else None


def _unit_snapshot_after_wait(unit: str) -> dict[str, str] | None:
    args = ["show", unit]
    for prop in UNIT_RECEIPT_PROPERTIES:
        args.extend(("-p", prop))
    try:
        result = _systemctl(*args, check=False)
    except AdmissionError:
        return None
    if result.returncode != 0:
        return None
    return _properties(result.stdout)


def _wait_for_transient_unit_cleanup(unit: str, timeout_seconds: float = 3.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last: dict[str, str] = {}
    while True:
        try:
            result = _systemctl(
                "show",
                unit,
                "-p",
                "LoadState",
                "-p",
                "ActiveState",
                "-p",
                "MainPID",
                "-p",
                "ControlPID",
                "--no-pager",
                check=False,
            )
        except AdmissionError as error:
            return {"confirmed": False, "reason": _safe_diagnostic(str(error))}
        last = _properties(result.stdout) if result.returncode == 0 else {}
        if last.get("LoadState") == "not-found":
            return {"confirmed": True, "unit_absent": True, "last_properties": last}
        active = last.get("ActiveState") in {"active", "activating", "reloading"}
        pids = (last.get("MainPID", "0"), last.get("ControlPID", "0"))
        if not active and all(pid in {"", "0", "n/a"} for pid in pids):
            if last.get("ActiveState") == "failed":
                _systemctl("reset-failed", unit, check=False)
            elif last.get("LoadState") not in {None, "loaded"}:
                return {
                    "confirmed": False,
                    "unit_absent": False,
                    "last_properties": last,
                    "reason": "unexpected transient unit state",
                }
        if time.monotonic() >= deadline:
            return {
                "confirmed": False,
                "unit_absent": False,
                "last_properties": last,
                "reason": "transient unit remained loaded or active after collection",
            }
        time.sleep(0.1)


def _cgroup_execution_metrics(
    path: Path | None = None, *, allow_missing_io_weight: bool = False
) -> dict[str, Any]:
    try:
        cgroup = path or _current_cgroup()
        resolved = cgroup.resolve(strict=True)
        if not resolved.is_relative_to(CGROUP_ROOT.resolve()):
            raise AdmissionError("execution cgroup escaped the cgroup v2 root")
        memory = _cgroup_memory(resolved)
        peak = (resolved / "memory.peak").read_text(encoding="ascii").strip()
        cpu_values = {
            key: int(value)
            for key, value in (
                line.split() for line in (resolved / "cpu.stat").read_text().splitlines()
            )
            if key in {"usage_usec", "user_usec", "system_usec", "nr_throttled", "throttled_usec"}
        }
        try:
            io_weight = (resolved / "io.weight").read_text(encoding="ascii").strip()
        except FileNotFoundError:
            if not allow_missing_io_weight:
                raise
            io_weight = None
        limits = {
            name: (resolved / name).read_text(encoding="ascii").strip()
            for name in (
                "memory.high",
                "memory.max",
                "memory.swap.max",
                "cpu.max",
                "pids.max",
            )
        }
        return {
            "available": True,
            "cgroup": str(resolved),
            "memory_peak_bytes": int(peak),
            "memory": memory,
            "cpu": cpu_values,
            "io_weight": io_weight[:256] if io_weight is not None else None,
            "io_weight_enforced": io_weight is not None,
            "limits": limits,
        }
    except (OSError, ValueError, AdmissionError) as error:
        return {"available": False, "error": str(error)[:512]}


class _RunnerOutput:
    """Drain only systemd-run client diagnostics; worker output stays in journald."""

    def __init__(self, process: subprocess.Popen[bytes], command: list[str]) -> None:
        self.process = process
        self.command = command
        self.selector = selectors.DefaultSelector()
        self.streams: dict[int, dict[str, Any]] = {}
        for name, stream in (
            ("stdout", getattr(process, "stdout", None)),
            ("stderr", getattr(process, "stderr", None)),
        ):
            if stream is None:
                continue
            os.set_blocking(stream.fileno(), False)
            state = {"name": name, "stream": stream, "size": 0, "tail": bytearray()}
            self.streams[stream.fileno()] = state
            self.selector.register(stream, selectors.EVENT_READ, state)

    def drain(self) -> None:
        for key, _mask in self.selector.select(timeout=0):
            state = key.data
            while True:
                try:
                    chunk = os.read(key.fd, 8192)
                except BlockingIOError:
                    break
                except OSError:
                    chunk = b""
                if not chunk:
                    try:
                        self.selector.unregister(key.fileobj)
                    except (KeyError, ValueError):
                        pass
                    break
                state["size"] += len(chunk)
                state["tail"].extend(chunk)
                if len(state["tail"]) > RUNNER_DIAGNOSTIC_TAIL_BYTES:
                    del state["tail"][:-RUNNER_DIAGNOSTIC_TAIL_BYTES]

    def summary(self) -> dict[str, Any]:
        self.drain()
        result: dict[str, Any] = {}
        for name, state in ((item["name"], item) for item in self.streams.values()):
            tail = bytes(state["tail"]).decode("utf-8", errors="replace")
            for argument in sorted(self.command, key=len, reverse=True):
                if len(argument) >= 4:
                    tail = tail.replace(argument, "<redacted-argument>")
            lowered = tail.lower()
            if not tail:
                diagnostic_type = "none"
            elif "failed to connect to bus" in lowered or "no medium found" in lowered:
                diagnostic_type = "systemd_bus_unavailable"
            elif "failed to drop capabilities" in lowered:
                diagnostic_type = "systemd_sandbox_setup_failed"
            elif "permission denied" in lowered or "access denied" in lowered:
                diagnostic_type = "systemd_permission_denied"
            elif "failed to start" in lowered:
                diagnostic_type = "systemd_unit_start_failed"
            elif "unknown assignment" in lowered or "invalid property" in lowered:
                diagnostic_type = "systemd_property_rejected"
            elif "timed out" in lowered or "timeout" in lowered:
                diagnostic_type = "systemd_client_timeout"
            else:
                diagnostic_type = "unclassified_client_diagnostic"
            result[name] = {
                "bytes": state["size"],
                "diagnostic_type": diagnostic_type,
            }
        return result

    def close(self) -> None:
        for state in self.streams.values():
            try:
                state["stream"].close()
            except OSError:
                pass
        self.selector.close()


def _terminate_worker(process: subprocess.Popen[bytes], grace_seconds: float) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=grace_seconds)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=1)


def _supervise_veritas_worker(
    command: list[str],
    *,
    status_path: Path,
    invocation_id: str,
    execution_context: dict[str, Any] | None = None,
    timeout_seconds: float,
    termination_grace_seconds: float,
) -> int:
    execution_context = execution_context or {}
    started = time.monotonic()
    started_at = _utc_now()
    try:
        _write_inner_status(
            status_path,
            invocation_id,
            phase="worker_start_requested",
            decision="ADMIT",
            worker_start_requested_at_utc=started_at,
            worker_executable=Path(command[0]).name if command else None,
            execution_context=execution_context,
        )
    except (OSError, AdmissionError) as error:
        print(
            json.dumps(
                {
                    "decision": "INDETERMINATE",
                    "reason": "worker_start_receipt_unavailable",
                    "detail": str(error)[:512],
                }
            ),
            file=sys.stderr,
        )
        return RUNNER_RESULT_MISSING
    try:
        release_root = (
            Path(command[2]).parent.parent
            if len(command) > 2
            and command[1] == "-S"
            and Path(command[2]).name == "veritas_source_analysis.py"
            else VERITAS_RELEASE_ROOT
        )
        worker_environment = {
            "PATH": f"{VERITAS_RUNTIME_PYTHON.parent}:/usr/bin:/bin",
            "HOME": str(Path.home()),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONPATH": f"{release_root / 'packages'}:{VERITAS_RUNTIME_SITE_PACKAGES}",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
        if runtime_dir:
            worker_environment["XDG_RUNTIME_DIR"] = runtime_dir
        ci_context = execution_context.get("ci_test")
        if isinstance(ci_context, dict):
            worker_environment.update(_veritas_ci_worker_environment(ci_context))
        worker = subprocess.Popen(command, env=worker_environment, start_new_session=True)
    except OSError as error:
        _write_inner_status(
            status_path,
            invocation_id,
            phase="worker_start_failed",
            decision="ADMIT",
            worker_error=f"{type(error).__name__}: {error}"[:512],
            worker_started_at_utc=started_at,
            execution_context=execution_context,
        )
        return 127

    try:
        _write_inner_status(
            status_path,
            invocation_id,
            phase="worker_running",
            decision="ADMIT",
            worker_pid=worker.pid,
            worker_started_at_utc=started_at,
            cgroup_metrics=_cgroup_execution_metrics(),
            execution_context=execution_context,
        )
    except (OSError, AdmissionError) as error:
        _terminate_worker(worker, termination_grace_seconds)
        print(
            json.dumps(
                {
                    "decision": "INDETERMINATE",
                    "reason": "worker_start_confirmation_not_durable",
                    "detail": str(error)[:512],
                }
            ),
            file=sys.stderr,
        )
        return RUNNER_RESULT_MISSING
    deadline = started + timeout_seconds
    samples: list[dict[str, float]] = []
    intervention: dict[str, Any] | None = None
    while True:
        return_code = worker.poll()
        if return_code is not None:
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            intervention = {"kind": "timeout", "at_utc": _utc_now()}
            _terminate_worker(worker, termination_grace_seconds)
            return_code = 124
            break
        try:
            sample = _read_veritas_runtime_io_pressure()
        except AdmissionError as error:
            intervention = {
                "kind": "runtime_io_pressure_unavailable",
                "detail": str(error)[:512],
                "at_utc": _utc_now(),
            }
            _terminate_worker(worker, termination_grace_seconds)
            return_code = VERITAS_RUNTIME_PRESSURE_CANCELLED
            break
        samples = (samples + [sample])[-int(VERITAS_IO_RUNTIME["consecutive_samples"]) :]
        reason = veritas_runtime_io_cancel_reason(samples)
        if reason:
            intervention = {"kind": reason, "at_utc": _utc_now(), "samples": samples}
            _terminate_worker(worker, termination_grace_seconds)
            return_code = VERITAS_RUNTIME_PRESSURE_CANCELLED
            break
        time.sleep(min(float(VERITAS_IO_RUNTIME["poll_interval_seconds"]), remaining))

    worker_signal = -return_code if return_code < 0 else None
    final_code = return_code
    if worker_signal is not None:
        final_code = 128 + worker_signal
    try:
        _write_inner_status(
            status_path,
            invocation_id,
            phase="worker_finished",
            decision="ADMIT",
            worker_pid=worker.pid,
            worker_started_at_utc=started_at,
            worker_completed_at_utc=_utc_now(),
            worker_runtime_seconds=round(time.monotonic() - started, 3),
            worker_exit_code=None if worker_signal is not None else return_code,
            worker_signal=worker_signal,
            watchdog_intervention=intervention,
            recent_io_pressure=samples,
            cgroup_metrics=_cgroup_execution_metrics(),
            execution_context=execution_context,
        )
    except (OSError, AdmissionError) as error:
        print(
            json.dumps(
                {
                    "decision": "INDETERMINATE",
                    "reason": "inner_result_not_durable",
                    "detail": str(error)[:512],
                }
            ),
            file=sys.stderr,
        )
        return RUNNER_RESULT_MISSING
    return final_code


def _properties(output: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in output.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            values[key] = value
    return values


def _read_service_cgroup(unit: str) -> dict[str, Any]:
    result = _systemctl(
        "show",
        unit,
        "-p",
        "ActiveState",
        "-p",
        "ControlGroup",
        "-p",
        "MemoryCurrent",
        "-p",
        "MemoryHigh",
        "-p",
        "MemoryMax",
        "-p",
        "MemoryEvents",
    )
    props = _properties(result.stdout)
    if props.get("ActiveState") != "active":
        raise AdmissionError(f"required protected service {unit} is not active")
    cg = props.get("ControlGroup", "").strip("/")
    if not cg:
        raise AdmissionError(f"required protected service {unit} has no cgroup")
    cgroup = _cgroup_memory(CGROUP_ROOT / cg)
    if cgroup["memory_headroom_bytes"] is None:
        raise AdmissionError(f"required protected service {unit} has no measurable memory limit")
    return {
        "unit": unit,
        "cgroup": f"/{cg}",
        **cgroup,
    }


def _finite_limit(value: str) -> int | None:
    if not value or value in {"infinity", "max", "[not set]"}:
        return None
    try:
        number = int(value)
    except ValueError:
        return None
    return number if number >= 0 else None


def _active_midas_workers(
    *,
    allow_current_veritas_service: bool = False,
    allow_current_synthetic_service: bool = False,
    invocation_id: str | None = None,
    veritas_parent_invocation_id: str | None = None,
    veritas_parent_unit: str | None = None,
) -> list[str]:
    result = _systemctl(
        "list-units",
        "--type=service",
        "--state=running",
        "--no-legend",
        "--no-pager",
        "midas-*.service",
    )
    active: list[str] = []
    current_unit = _current_veritas_service_unit() if allow_current_veritas_service else None
    allowed_parent_unit = (
        (veritas_parent_unit or VERITAS_SERVICE_UNIT)
        if allow_current_veritas_service
        and isinstance(veritas_parent_invocation_id, str)
        and re.fullmatch(r"[0-9a-f]{32}", veritas_parent_invocation_id)
        else None
    )
    if allow_current_synthetic_service and invocation_id:
        cgroup = _current_cgroup()
        expected_suffix = f"-{invocation_id[:12]}.service"
        candidates = [
            part
            for part in cgroup.parts
            if part.startswith("midas-synthetic-validation-") and part.endswith(expected_suffix)
        ]
        if len(candidates) == 1:
            current_unit = candidates[0]
    for line in result.stdout.splitlines():
        fields = line.split()
        if (
            fields
            and fields[0].startswith("midas-")
            and fields[0] not in ALLOW_ACTIVE_UNITS
            and fields[0] != current_unit
            and fields[0] != allowed_parent_unit
        ):
            active.append(fields[0])
    return active


def _validate_synthetic_unit_context(
    invocation_id: str, status_dir: Path
) -> tuple[str, dict[str, str], dict[str, Any]]:
    if not re.fullmatch(r"[0-9a-f]{32}", invocation_id):
        raise AdmissionError("synthetic invocation id is invalid")
    if status_dir.resolve() != (SYNTHETIC_RECEIPT_DIR / f"{invocation_id}.control").resolve():
        raise AdmissionError("synthetic status must remain inside its dedicated receipt directory")
    cgroup = _current_cgroup().resolve(strict=True)
    matches = [
        part
        for part in cgroup.parts
        if re.fullmatch(
            rf"midas-synthetic-validation-[a-zA-Z0-9_-]+-{invocation_id[:12]}\.service",
            part,
        )
    ]
    if len(matches) != 1:
        raise AdmissionError("synthetic execution must run in its matching transient service")
    unit = matches[0]
    properties = _properties(
        _systemctl(
            "show",
            unit,
            "-p",
            "LoadState",
            "-p",
            "Transient",
            "-p",
            "ActiveState",
            "-p",
            "InvocationID",
            "-p",
            "ControlGroup",
            "-p",
            "MemoryHigh",
            "-p",
            "MemoryMax",
            "-p",
            "MemorySwapMax",
            "-p",
            "CPUQuotaPerSecUSec",
            "-p",
            "Nice",
            "-p",
            "IOSchedulingClass",
            "-p",
            "IOWeight",
            "-p",
            "TasksMax",
            "-p",
            "RuntimeMaxUSec",
            "-p",
            "TimeoutStartUSec",
            "-p",
            "NoNewPrivileges",
            "-p",
            "RestrictAddressFamilies",
            "-p",
            "KillMode",
            "-p",
            "Restart",
            "-p",
            "SystemCallArchitectures",
        ).stdout
    )
    expected = {
        "LoadState": "loaded",
        "Transient": "yes",
        "ActiveState": "active",
        "ControlGroup": "/" + str(cgroup.relative_to(CGROUP_ROOT.resolve())),
        "MemoryHigh": str(SYNTHETIC_RUN_LIMITS["memory_high_mib"] * MIB),
        "MemoryMax": str(SYNTHETIC_RUN_LIMITS["memory_max_mib"] * MIB),
        "MemorySwapMax": "0",
        "CPUQuotaPerSecUSec": "100ms",
        "Nice": "19",
        "IOSchedulingClass": "3",
        "IOWeight": "10",
        "TasksMax": str(SYNTHETIC_RUN_LIMITS["tasks_max"]),
        "RuntimeMaxUSec": "10s",
        "TimeoutStartUSec": "10s",
        "NoNewPrivileges": "yes",
        "RestrictAddressFamilies": "AF_UNIX",
        "KillMode": "control-group",
        "Restart": "no",
        "SystemCallArchitectures": "native",
    }
    mismatches = [
        f"{name}={properties.get(name)!r} (expected {value!r})"
        for name, value in expected.items()
        if properties.get(name) != value
    ]
    if not re.fullmatch(r"[0-9a-f]{32}", properties.get("InvocationID", "")):
        mismatches.append("InvocationID is missing or malformed")
    if properties.get("InvocationID") == invocation_id:
        mismatches.append("systemd unit invocation id unexpectedly equals launcher id")

    metrics = _cgroup_execution_metrics(cgroup, allow_missing_io_weight=True)
    limits = metrics.get("limits", {}) if metrics.get("available") else {}
    expected_cgroup_limits = {
        "memory.high": str(SYNTHETIC_RUN_LIMITS["memory_high_mib"] * MIB),
        "memory.max": str(SYNTHETIC_RUN_LIMITS["memory_max_mib"] * MIB),
        "memory.swap.max": "0",
        "cpu.max": "10000 100000",
        "pids.max": str(SYNTHETIC_RUN_LIMITS["tasks_max"]),
    }
    for name, value in expected_cgroup_limits.items():
        if limits.get(name) != value:
            mismatches.append(f"cgroup {name}={limits.get(name)!r} (expected {value!r})")
    if not metrics.get("available"):
        mismatches.append("cgroup metrics are unavailable")
    metrics["io_weight_note"] = (
        "cgroup io controller is not delegated; worker remains fixed and tiny, "
        "systemd IOSchedulingClass=idle and host I/O admission remain required"
        if not metrics.get("io_weight_enforced")
        else "cgroup io.weight was available"
    )
    metrics["network_isolation"] = {
        "restricted": False,
        "mechanism": "worker seccomp filter pending before exec",
    }
    if mismatches:
        raise AdmissionError(
            "synthetic unit isolation or limits were not verified: " + "; ".join(mismatches)
        )
    return unit, properties, metrics


def _close_unexpected_worker_fds() -> int:
    """Keep only standard streams so a worker cannot inherit a network socket."""
    try:
        descriptors = [int(name) for name in os.listdir("/proc/self/fd")]
    except (OSError, ValueError) as error:
        raise AdmissionError(f"cannot enumerate inherited worker descriptors: {error}") from error
    closed = 0
    for descriptor in descriptors:
        if descriptor <= 2:
            continue
        try:
            os.close(descriptor)
        except OSError as error:
            if error.errno != errno.EBADF:
                raise AdmissionError(f"cannot close inherited descriptor {descriptor}") from error
        else:
            closed += 1
    return closed


def _install_synthetic_network_filter() -> dict[str, Any]:
    """Deny socket and network syscalls before execing an allowlisted test worker."""
    machine = platform.machine().lower()
    arch = {"amd64": "x86_64", "arm64": "aarch64"}.get(machine, machine)
    audit_arch = SYNTHETIC_SECCOMP_ARCHES.get(arch)
    syscalls = SYNTHETIC_NETWORK_SYSCALLS.get(arch)
    if audit_arch is None or syscalls is None:
        raise AdmissionError(f"synthetic network seccomp is not configured for {machine}")

    class SockFilter(ctypes.Structure):
        _fields_ = [
            ("code", ctypes.c_ushort),
            ("jt", ctypes.c_ubyte),
            ("jf", ctypes.c_ubyte),
            ("k", ctypes.c_uint32),
        ]

    class SockFprog(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.POINTER(SockFilter))]

    # Check the native audit architecture, then return EPERM for every syscall
    # that can create, connect, or exchange data through a socket.
    instructions = [
        SockFilter(0x20, 0, 0, 4),
        SockFilter(0x15, 1, 0, audit_arch),
        SockFilter(0x06, 0, 0, 0x80000000),
        SockFilter(0x20, 0, 0, 0),
    ]
    instructions.extend(
        instruction
        for number in syscalls
        for instruction in (
            SockFilter(0x15, 0, 1, number),
            SockFilter(0x06, 0, 0, 0x00050000 | errno.EPERM),
        )
    )
    instructions.append(SockFilter(0x06, 0, 0, 0x7FFF0000))
    program_array = (SockFilter * len(instructions))(*instructions)
    program = SockFprog(len(instructions), program_array)
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    libc.prctl.restype = ctypes.c_int
    # PR_SET_SECCOMP=22, SECCOMP_MODE_FILTER=2. NoNewPrivileges is verified
    # before Landlock is enabled, and both restrictions survive execve.
    if libc.prctl(22, 2, ctypes.byref(program), 0, 0) != 0:
        error = ctypes.get_errno()
        raise AdmissionError(f"cannot install worker network seccomp filter: {os.strerror(error)}")
    mode = libc.prctl(21, 0, None, 0, 0)  # PR_GET_SECCOMP
    if mode != 2:
        raise AdmissionError("worker seccomp filter mode could not be verified")

    probe = {"restricted": True, "mechanism": "seccomp-bpf", "mode": mode, "probes": {}}
    for name, family in (
        ("AF_INET", socket.AF_INET),
        ("AF_INET6", socket.AF_INET6),
        ("AF_UNIX", socket.AF_UNIX),
    ):
        try:
            candidate = socket.socket(family, socket.SOCK_STREAM)
        except OSError as error:
            denied = error.errno == errno.EPERM
            probe["probes"][name] = "denied" if denied else f"unverified_errno_{error.errno}"
            probe["restricted"] = probe["restricted"] and denied
        else:
            candidate.close()
            probe["probes"][name] = "created"
            probe["restricted"] = False
    return probe


def _landlock_syscall_numbers() -> tuple[int, int, int]:
    if platform.machine().lower() in {"x86_64", "amd64", "aarch64", "arm64", "riscv64"}:
        return 444, 445, 446
    raise AdmissionError("Landlock syscall numbers are not defined for this architecture")


def _apply_synthetic_filesystem_isolation(status_dir: Path) -> dict[str, Any]:
    """Confine the synthetic worker to immutable system binaries and its receipt dir."""
    if platform.machine().lower() not in {"x86_64", "amd64", "aarch64", "arm64", "riscv64"}:
        raise AdmissionError("Landlock is not configured for this architecture")
    if status_dir.is_symlink() or not status_dir.is_dir():
        raise AdmissionError("synthetic status directory is missing or unsafe")
    if (
        Path("/proc/self/status")
        .read_text(encoding="ascii")
        .split("NoNewPrivs:", 1)[1]
        .splitlines()[0]
        .strip()
        != "1"
    ):
        raise AdmissionError("systemd NoNewPrivileges is not active in the worker")

    writable_path = str(status_dir.resolve(strict=True))
    libc = ctypes.CDLL(None, use_errno=True)
    create_ruleset, add_rule, restrict_self = _landlock_syscall_numbers()

    class RulesetAttr(ctypes.Structure):
        _fields_ = [("handled_access_fs", ctypes.c_uint64)]

    class PathBeneathAttr(ctypes.Structure):
        _fields_ = [
            ("allowed_access", ctypes.c_uint64),
            ("parent_fd", ctypes.c_int),
            ("reserved", ctypes.c_uint32),
        ]

    abi = libc.syscall(create_ruleset, None, 0, 1)
    if abi < 1:
        error = ctypes.get_errno()
        raise AdmissionError(f"Landlock ABI query failed: {os.strerror(error)}")
    rights = {
        "execute": 1 << 0,
        "write_file": 1 << 1,
        "read_file": 1 << 2,
        "read_dir": 1 << 3,
        "remove_dir": 1 << 4,
        "remove_file": 1 << 5,
        "make_char": 1 << 6,
        "make_dir": 1 << 7,
        "make_reg": 1 << 8,
        "make_sock": 1 << 9,
        "make_fifo": 1 << 10,
        "make_block": 1 << 11,
        "make_sym": 1 << 12,
    }
    if abi >= 2:
        rights["refer"] = 1 << 13
    if abi >= 3:
        rights["truncate"] = 1 << 14
    if abi >= 5:
        rights["ioctl_dev"] = 1 << 15
    handled = sum(rights.values())
    ruleset_fd = -1
    path_fds: list[int] = []
    try:
        attr = RulesetAttr(handled)
        ruleset_fd = libc.syscall(create_ruleset, ctypes.byref(attr), ctypes.sizeof(attr), 0)
        if ruleset_fd < 0:
            error = ctypes.get_errno()
            raise AdmissionError(f"Landlock ruleset creation failed: {os.strerror(error)}")
        readonly = rights["execute"] | rights["read_file"] | rights["read_dir"]
        access_rules = [(Path("/usr"), readonly)]
        access_rules.extend(
            (path, readonly) for path in (Path("/lib"), Path("/lib64")) if path.exists()
        )
        status_access = (
            rights["read_file"]
            | rights["read_dir"]
            | rights["write_file"]
            | rights["make_reg"]
            | rights["remove_file"]
            | rights.get("refer", 0)
            | rights.get("truncate", 0)
        )
        access_rules.append((status_dir.resolve(strict=True), status_access))
        for loader_file in (Path("/etc/ld.so.cache"), Path("/etc/ld.so.preload")):
            if loader_file.is_file():
                info = loader_file.stat()
                if info.st_uid != 0 or info.st_mode & 0o022:
                    raise AdmissionError(f"dynamic loader metadata is not trusted: {loader_file}")
                access_rules.append((loader_file.resolve(strict=True), rights["read_file"]))
        added: set[tuple[str, int]] = set()
        for path, allowed in access_rules:
            resolved = path.resolve(strict=True)
            metadata = resolved.stat()
            if str(resolved) != writable_path and (
                metadata.st_uid != 0 or metadata.st_mode & 0o022
            ):
                raise AdmissionError(
                    f"synthetic system path is not root-owned and immutable: {resolved}"
                )
            key = (str(resolved), allowed)
            if key in added:
                continue
            added.add(key)
            fd = os.open(resolved, getattr(os, "O_PATH", os.O_RDONLY) | os.O_CLOEXEC)
            path_fds.append(fd)
            path_attr = PathBeneathAttr(allowed, fd, 0)
            if libc.syscall(add_rule, ruleset_fd, 1, ctypes.byref(path_attr), 0) < 0:
                error = ctypes.get_errno()
                raise AdmissionError(f"Landlock path rule failed: {os.strerror(error)}")
        if libc.prctl(38, 1, 0, 0, 0) != 0:
            error = ctypes.get_errno()
            raise AdmissionError(f"setting no_new_privs for Landlock failed: {os.strerror(error)}")
        if libc.syscall(restrict_self, ruleset_fd, 0) < 0:
            error = ctypes.get_errno()
            raise AdmissionError(f"Landlock restriction failed: {os.strerror(error)}")
    finally:
        for fd in path_fds:
            os.close(fd)
        if ruleset_fd >= 0:
            os.close(ruleset_fd)

    denied_paths = []
    for path in (Path.home(), Path("/mnt"), Path("/var/tmp")):
        try:
            fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        except OSError as error:
            if error.errno not in {errno.EACCES, errno.EPERM}:
                raise AdmissionError(
                    f"Landlock could not verify protected path {path}: {error}"
                ) from error
            denied_paths.append(str(path))
        else:
            os.close(fd)
            raise AdmissionError(f"Landlock left protected path accessible: {path}")
    probe_path = status_dir / f".landlock-probe-{os.getpid()}-{uuid.uuid4().hex}"
    descriptor = os.open(
        probe_path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    os.close(descriptor)
    probe_path.unlink()
    return {
        "enforced": True,
        "abi": int(abi),
        "writable_path": writable_path,
        "denied_paths": denied_paths,
    }


def _current_cgroup() -> Path:
    lines = Path("/proc/self/cgroup").read_text(encoding="utf-8").splitlines()
    unified = next((line.split(":", 2)[2] for line in lines if line.startswith("0::")), None)
    if unified is None:
        raise AdmissionError("the process is not in a readable cgroup v2 hierarchy")
    normalized = Path(unified.lstrip("/"))
    if ".." in normalized.parts:
        raise AdmissionError("unsafe process cgroup path")
    path = CGROUP_ROOT / normalized
    if not path.is_dir():
        raise AdmissionError(f"process cgroup does not exist: {path}")
    return path


def _veritas_ci_test_context(
    *, unit_name: str | None = None, invocation_id: str | None = None
) -> dict[str, str] | None:
    """Return synthetic campaign inputs only for the dedicated disposable CI unit."""
    marker = os.environ.get("MIDAS_VERITAS_CI_TEST")
    has_ci_environment = any(key.startswith("MIDAS_VERITAS_CI_") for key in os.environ)
    if marker is None and not has_ci_environment:
        if unit_name == VERITAS_CI_SERVICE_UNIT:
            raise AdmissionError("the Veritas CI service is missing its test-only environment")
        return None
    if marker != VERITAS_CI_TEST_MARKER:
        raise AdmissionError("Veritas CI environment is incomplete or unrecognized")
    if unit_name is None:
        current = _current_cgroup()
        matches = [part for part in current.parts if part == VERITAS_CI_SERVICE_UNIT]
        if len(matches) == 1:
            unit_name = matches[0]
        else:
            unit_name = os.environ.get("MIDAS_VERITAS_CI_PARENT_UNIT")
    if unit_name != VERITAS_CI_SERVICE_UNIT:
        raise AdmissionError("synthetic Veritas inputs are restricted to the disposable CI unit")
    invocation_id = (
        invocation_id
        or os.environ.get("MIDAS_VERITAS_CI_PARENT_INVOCATION_ID")
        or os.environ.get("INVOCATION_ID")
    )
    if not isinstance(invocation_id, str) or not re.fullmatch(r"[0-9a-f]{32}", invocation_id):
        raise AdmissionError("Veritas CI parent invocation identity is missing")
    service = _properties(
        _systemctl(
            "show",
            unit_name,
            "-p",
            "ActiveState",
            "-p",
            "InvocationID",
            "-p",
            "Environment",
        ).stdout
    )
    if (
        service.get("ActiveState") not in {"active", "activating"}
        or service.get("InvocationID") != invocation_id
    ):
        raise AdmissionError("Veritas CI parent service invocation could not be verified")
    configured: dict[str, str] = {}
    try:
        for item in shlex.split(service.get("Environment", "")):
            key, separator, value = item.partition("=")
            if separator:
                configured[key] = value
    except ValueError as error:
        raise AdmissionError("Veritas CI service environment is malformed") from error
    required = {
        "MIDAS_VERITAS_CI_TEST": VERITAS_CI_TEST_MARKER,
        "MIDAS_VERITAS_CI_CAMPAIGN_PATH": str(VERITAS_CI_ROOT / "campaign" / "campaign.json"),
        "MIDAS_VERITAS_CI_SOURCE_ROOT": str(VERITAS_CI_ROOT / "raw"),
        "MIDAS_VERITAS_CI_PSI_FILE": str(VERITAS_CI_ROOT / "pressure" / "io"),
    }
    ci_environment_keys = {
        "MIDAS_VERITAS_CI_TEST",
        "MIDAS_VERITAS_CI_CAMPAIGN_PATH",
        "MIDAS_VERITAS_CI_CAMPAIGN_SHA256",
        "MIDAS_VERITAS_CI_CAMPAIGN_ID",
        "MIDAS_VERITAS_CI_SOURCE_ROOT",
        "MIDAS_VERITAS_CI_PSI_FILE",
        "MIDAS_VERITAS_CI_SCENARIO",
    }
    if any(configured.get(key) != value for key, value in required.items()):
        raise AdmissionError("Veritas CI service paths do not match the fixed disposable fixture")
    configured_ci_keys = {key for key in configured if key.startswith("MIDAS_VERITAS_CI_")}
    if configured_ci_keys != ci_environment_keys or any(
        os.environ.get(key) != configured.get(key) for key in ci_environment_keys
    ):
        raise AdmissionError("Veritas CI worker environment differs from its service definition")
    scenario = configured.get("MIDAS_VERITAS_CI_SCENARIO")
    if scenario not in {"success", "worker_failure", "watchdog", "admission_denied"}:
        raise AdmissionError("Veritas CI scenario is missing or unsupported")
    campaign_path = Path(required["MIDAS_VERITAS_CI_CAMPAIGN_PATH"])
    source_root = Path(required["MIDAS_VERITAS_CI_SOURCE_ROOT"])
    pressure_file = Path(required["MIDAS_VERITAS_CI_PSI_FILE"])
    output_root = VERITAS_CI_ROOT / "output"
    fixture_root = VERITAS_CI_ROOT.resolve()
    if (
        VERITAS_CI_ROOT.is_symlink()
        or campaign_path.is_symlink()
        or not campaign_path.is_file()
        or campaign_path.stat().st_size > 2_000_000
        or source_root.is_symlink()
        or not source_root.is_dir()
        or pressure_file.is_symlink()
        or not pressure_file.is_file()
        or output_root.is_symlink()
        or not output_root.is_dir()
        or any(
            not path.resolve(strict=True).is_relative_to(fixture_root)
            for path in (campaign_path, source_root, pressure_file, output_root)
        )
    ):
        raise AdmissionError("Veritas CI fixture is missing or unsafe")
    try:
        campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AdmissionError("Veritas CI campaign is unreadable") from error
    campaign_identity = campaign.get("identity") if isinstance(campaign, dict) else None
    campaign_id = campaign.get("campaign_id") if isinstance(campaign, dict) else None
    if (
        not isinstance(campaign_identity, dict)
        or campaign_identity.get("raw_root") != str(source_root)
        or not isinstance(campaign_id, str)
        or not re.fullmatch(r"[0-9a-f]{64}", campaign_id)
    ):
        raise AdmissionError("Veritas CI campaign is not pinned to the disposable source root")
    campaign_sha256 = _sha256_bytes(campaign_path.read_bytes())
    if configured.get("MIDAS_VERITAS_CI_CAMPAIGN_SHA256") != campaign_sha256:
        raise AdmissionError("Veritas CI campaign digest differs from the service environment")
    if configured.get("MIDAS_VERITAS_CI_CAMPAIGN_ID") != campaign_id:
        raise AdmissionError("Veritas CI campaign ID differs from the service environment")
    return {
        "service_unit": unit_name,
        "service_invocation_id": invocation_id,
        "campaign_path": str(campaign_path),
        "campaign_sha256": campaign_sha256,
        "campaign_id": campaign_id,
        "source_root": str(source_root),
        "pressure_file": str(pressure_file),
        "output_root": str(output_root),
        "scenario": scenario,
    }


def _veritas_ci_worker_environment(context: dict[str, str]) -> dict[str, str]:
    return {
        "MIDAS_VERITAS_CI_TEST": VERITAS_CI_TEST_MARKER,
        "MIDAS_VERITAS_CI_PARENT_UNIT": context["service_unit"],
        "MIDAS_VERITAS_CI_PARENT_INVOCATION_ID": context["service_invocation_id"],
        "MIDAS_VERITAS_CI_CAMPAIGN_PATH": context["campaign_path"],
        "MIDAS_VERITAS_CI_CAMPAIGN_SHA256": context["campaign_sha256"],
        "MIDAS_VERITAS_CI_CAMPAIGN_ID": context["campaign_id"],
        "MIDAS_VERITAS_CI_SOURCE_ROOT": context["source_root"],
        "MIDAS_VERITAS_CI_PSI_FILE": context["pressure_file"],
        "MIDAS_VERITAS_CI_SCENARIO": context["scenario"],
    }


def _current_veritas_service_unit() -> str | None:
    for part in reversed(_current_cgroup().parts):
        if (
            part == VERITAS_SERVICE_UNIT
            or part == VERITAS_CI_SERVICE_UNIT
            or part.startswith("midas-heavy-veritas-")
            and part.endswith(".service")
        ):
            return part
    return None


def _expected_veritas_service_execstart() -> list[str]:
    launcher = VERITAS_RELEASE_ROOT / "bin" / "midas_resource_preflight.py"
    command = [
        str(VERITAS_RUNTIME_PYTHON),
        str(launcher),
        "run",
        "--profile",
        "veritas",
        "--storage-path",
        str(VERITAS_OUTPUT_ROOT),
        "--storage-required-mib",
        "0",
        "--storage-reserve-mib",
        "5120",
        "--memory-budget-mib",
        "128",
        "--sample-seconds",
        "30",
        "--memory-high-mib",
        "192",
        "--memory-max-mib",
        "256",
        "--cpu-quota-percent",
        "100",
        "--timeout-seconds",
        "600",
        "--label",
        "veritas-source-analysis",
        "--source-revision",
        VERITAS_APPROVED_SOURCE_REVISION,
        "--release-identity",
        VERITAS_RELEASE_ID,
        "--release-root",
        str(VERITAS_RELEASE_ROOT),
        "--expected-module-sha256",
        VERITAS_APPROVED_MODULE_SHA256,
        "--",
        *_veritas_worker_command(VERITAS_RELEASE_ROOT),
    ]
    return command


def _parse_execstart(value: str) -> list[str]:
    match = re.search(r"argv\[\]=(.*?);\s*ignore_errors=", value)
    if not match:
        raise AdmissionError("Veritas service ExecStart is not inspectable")
    try:
        return shlex.split(match.group(1))
    except ValueError as error:
        raise AdmissionError("Veritas service ExecStart is malformed") from error


def _validate_veritas_runtime_context(
    *,
    owner_invocation_id: str | None = None,
    owner_pid: int | None = None,
    owner_unit: str | None = None,
    require_current_service_cgroup: bool = True,
) -> str:
    """Prove the current caller is this exact service invocation and unit definition."""
    owner_invocation_id = owner_invocation_id or os.environ.get("INVOCATION_ID")
    owner_pid = os.getpid() if owner_pid is None else owner_pid
    if not isinstance(owner_invocation_id, str) or not re.fullmatch(
        r"[0-9a-f]{32}", owner_invocation_id
    ):
        raise AdmissionError("Veritas guard must be called from a systemd service invocation")
    current_unit = _current_veritas_service_unit()
    owner_unit = owner_unit or current_unit
    if owner_unit not in {VERITAS_SERVICE_UNIT, VERITAS_CI_SERVICE_UNIT}:
        raise AdmissionError("Veritas guard is outside an approved one-shot service unit")
    if require_current_service_cgroup and current_unit != owner_unit:
        raise AdmissionError("Veritas guard is outside the authorized one-shot service cgroup")
    timer_states = {
        unit: _properties(
            _systemctl("show", unit, "-p", "ActiveState", "-p", "UnitFileState").stdout
        )
        for unit in VERITAS_TIMER_UNITS
    }
    reality_timer = timer_states["midas-reality-capacity.timer"]
    if (
        reality_timer.get("ActiveState") != "inactive"
        or reality_timer.get("UnitFileState") != "disabled"
    ):
        raise AdmissionError("Reality capacity timer must remain disabled and inactive")
    veritas_timer = timer_states["midas-veritas-source-analysis.timer"]
    if (veritas_timer.get("ActiveState"), veritas_timer.get("UnitFileState")) not in {
        ("inactive", "disabled"),
        ("active", "enabled"),
    }:
        raise AdmissionError("Veritas timer has an inconsistent or unsafe enabled state")

    service = _properties(
        _systemctl(
            "show",
            owner_unit,
            "-p",
            "ActiveState",
            "-p",
            "MainPID",
            "-p",
            "ControlPID",
            "-p",
            "MemoryMax",
            "-p",
            "CPUQuotaPerSecUSec",
            "-p",
            "Nice",
            "-p",
            "IOSchedulingClass",
            "-p",
            "TimeoutStartUSec",
            "-p",
            "MemoryHigh",
            "-p",
            "MemorySwapMax",
            "-p",
            "ProtectSystem",
            "-p",
            "ProtectHome",
            "-p",
            "ReadWritePaths",
            "-p",
            "PrivateTmp",
            "-p",
            "NoNewPrivileges",
            "-p",
            "Restart",
            "-p",
            "WorkingDirectory",
            "-p",
            "InvocationID",
            "-p",
            "ExecStart",
            "-p",
            "Environment",
            "-p",
            "UnsetEnvironment",
            "-p",
            "RestrictAddressFamilies",
        ).stdout
    )
    if (
        service.get("ActiveState") not in {"active", "activating"}
        or service.get("MainPID") != str(owner_pid)
        or service.get("ControlPID") != "0"
        or service.get("InvocationID") != owner_invocation_id
    ):
        raise AdmissionError("Veritas source-analysis service owner identity is not current")
    ci_context = None
    if owner_unit == VERITAS_CI_SERVICE_UNIT:
        ci_context = _veritas_ci_test_context(
            unit_name=owner_unit, invocation_id=owner_invocation_id
        )
    elif os.environ.get("MIDAS_VERITAS_CI_TEST") is not None:
        raise AdmissionError("synthetic Veritas environment cannot be enabled for production")
    expected = {
        "MemoryMax": str(256 * MIB),
        "CPUQuotaPerSecUSec": "1s",
        "Nice": "19",
        "IOSchedulingClass": "3",
        "TimeoutStartUSec": "12min",
        "MemoryHigh": "infinity",
        "MemorySwapMax": "infinity",
        "ProtectSystem": "strict",
        "ProtectHome": "read-only",
        "WorkingDirectory": str(VERITAS_SERVICE_ROOT),
        "PrivateTmp": "yes",
        "NoNewPrivileges": "yes",
        "Restart": "no",
        "UnsetEnvironment": "PYTHONPATH",
    }
    mismatches = [key for key, value in expected.items() if service.get(key) != value]
    if mismatches:
        raise AdmissionError(
            "Veritas source-analysis service constraints changed: " + ", ".join(mismatches)
        )
    if ci_context and service.get("RestrictAddressFamilies") != "AF_UNIX":
        raise AdmissionError("Veritas systemd CI parent does not deny network address families")
    rw_paths = set(service.get("ReadWritePaths", "").split())
    expected_output_root = Path(ci_context["output_root"]) if ci_context else VERITAS_OUTPUT_ROOT
    expected_rw_paths = {str(expected_output_root), str(GUARDED_RECEIPT_DIR)}
    if rw_paths != expected_rw_paths:
        raise AdmissionError("Veritas service write paths differ from the approved minimal set")
    if _parse_execstart(service.get("ExecStart", "")) != _expected_veritas_service_execstart():
        raise AdmissionError("Veritas service ExecStart differs from the pinned guarded release")
    environment = service.get("Environment", "")
    if "OMP_NUM_THREADS=1" not in environment or "OPENBLAS_NUM_THREADS=1" not in environment:
        raise AdmissionError("Veritas service thread limits are missing")
    for path in (VERITAS_SERVICE_ROOT, VERITAS_OUTPUT_ROOT, expected_output_root):
        if path.is_symlink() or not path.is_dir():
            raise AdmissionError(f"Veritas service path is missing or unsafe: {path}")
    rollback_module = VERITAS_SERVICE_ROOT / "packages/midas/veritas/finalized_source_analysis.py"
    if (
        rollback_module.is_symlink()
        or not rollback_module.is_file()
        or _sha256_bytes(rollback_module.read_bytes()) != VERITAS_PRODUCTION_MODULE_SHA256
    ):
        raise AdmissionError("the existing production Veritas module is not rollback-verifiable")
    if ci_context is None and not VERITAS_OUTPUT_ROOT.resolve().is_relative_to(
        VERITAS_SERVICE_ROOT.resolve()
    ):
        raise AdmissionError("Veritas write path is outside its service root")
    if ci_context and not expected_output_root.resolve().is_relative_to(VERITAS_CI_ROOT.resolve()):
        raise AdmissionError("Veritas CI write path is outside its disposable fixture root")
    return owner_invocation_id


def _validate_veritas_transient_unit(
    *,
    expected_status_dir: Path,
    parent_invocation_id: str,
    parent_pid: int,
    output_root: Path = VERITAS_OUTPUT_ROOT,
    network_restricted: bool = False,
) -> dict[str, Any]:
    unit = _current_veritas_service_unit()
    if not unit or not unit.startswith("midas-heavy-veritas-"):
        raise AdmissionError("Veritas inner gate is outside its guarded transient service")
    props = _properties(
        _systemctl(
            "show",
            unit,
            "-p",
            "ActiveState",
            "-p",
            "MainPID",
            "-p",
            "InvocationID",
            "-p",
            "MemoryHigh",
            "-p",
            "MemoryMax",
            "-p",
            "MemorySwapMax",
            "-p",
            "CPUQuotaPerSecUSec",
            "-p",
            "IOWeight",
            "-p",
            "TasksMax",
            "-p",
            "Nice",
            "-p",
            "IOSchedulingClass",
            "-p",
            "ProtectSystem",
            "-p",
            "ProtectHome",
            "-p",
            "ReadWritePaths",
            "-p",
            "PrivateTmp",
            "-p",
            "NoNewPrivileges",
            "-p",
            "UMask",
            "-p",
            "RuntimeMaxUSec",
            "-p",
            "TimeoutStartUSec",
            "-p",
            "KillMode",
            "-p",
            "Restart",
            "-p",
            "RestrictAddressFamilies",
        ).stdout
    )
    if (
        props.get("ActiveState") not in {"active", "activating"}
        or props.get("MainPID") != str(os.getpid())
        or not re.fullmatch(r"[0-9a-f]{32}", props.get("InvocationID", ""))
    ):
        raise AdmissionError("Veritas transient unit identity is not the current inner gate")
    expected = {
        "MemoryHigh": str(192 * MIB),
        "MemoryMax": str(256 * MIB),
        "MemorySwapMax": "0",
        "CPUQuotaPerSecUSec": "1s",
        "IOWeight": "10",
        "TasksMax": "256",
        "Nice": "19",
        "IOSchedulingClass": "3",
        "ProtectSystem": "strict",
        "ProtectHome": "read-only",
        "PrivateTmp": "yes",
        "NoNewPrivileges": "yes",
        "UMask": "0077",
        "RuntimeMaxUSec": "10min",
        "TimeoutStartUSec": "10min",
        "KillMode": "control-group",
        "Restart": "no",
    }
    mismatches = [key for key, value in expected.items() if props.get(key) != value]
    if mismatches:
        raise AdmissionError(
            "Veritas transient cgroup or sandbox limits differ from the approved profile: "
            + ", ".join(mismatches)
        )
    if network_restricted and props.get("RestrictAddressFamilies") != "AF_UNIX":
        raise AdmissionError("Veritas CI transient worker does not deny network address families")
    expected_rw = {str(output_root), str(expected_status_dir)}
    if set(props.get("ReadWritePaths", "").split()) != expected_rw:
        raise AdmissionError("Veritas transient write paths exceed the research root and receipt")
    metrics = _cgroup_execution_metrics()
    if not metrics.get("available"):
        raise AdmissionError("Veritas transient cgroup metrics are unavailable")
    limits = metrics.get("limits", {})
    cgroup_expected = {
        "memory.high": str(192 * MIB),
        "memory.max": str(256 * MIB),
        "memory.swap.max": "0",
        "pids.max": "256",
    }
    if any(limits.get(key) != value for key, value in cgroup_expected.items()):
        raise AdmissionError(
            "Veritas transient effective cgroup limits do not match systemd properties"
        )
    cpu_max = limits.get("cpu.max", "").split()
    if len(cpu_max) != 2 or int(cpu_max[0]) != int(cpu_max[1]):
        raise AdmissionError("Veritas transient CPU quota is not exactly 100 percent")
    if not metrics.get("io_weight_enforced") or not re.search(
        r"(?:^|\s)default\s+10(?:\s|$)", str(metrics.get("io_weight", ""))
    ):
        raise AdmissionError("Veritas transient IOWeight=10 is not reflected in its cgroup")
    metrics["systemd_properties"] = props
    metrics["systemd_invocation_id"] = props["InvocationID"]
    metrics["parent_service_invocation_id"] = parent_invocation_id
    metrics["parent_service_pid"] = parent_pid
    metrics["limits_verified"] = True
    return metrics


def _cgroup_memory(path: Path) -> dict[str, int | None]:
    try:
        current = int((path / "memory.current").read_text().strip())
        high = _finite_limit((path / "memory.high").read_text().strip())
        maximum = _finite_limit((path / "memory.max").read_text().strip())
        events_text = (path / "memory.events").read_text()
        events = {
            key: int(value) for key, value in (line.split() for line in events_text.splitlines())
        }
    except (OSError, ValueError) as error:
        raise AdmissionError(f"cannot read memory controls for cgroup {path}: {error}") from error
    finite = [value for value in (high, maximum) if value is not None]
    return {
        "memory_current_bytes": current,
        "memory_high_bytes": high,
        "memory_max_bytes": maximum,
        "memory_headroom_bytes": max(0, min(finite) - current) if finite else None,
        "oom_events": events.get("oom", 0),
        "oom_kill_events": events.get("oom_kill", 0),
    }


def _storage_evidence(
    paths: list[str], required_bytes: int, reserve_bytes: int
) -> list[dict[str, Any]]:
    if not paths:
        raise AdmissionError("at least one --storage-path is required")
    result: list[dict[str, Any]] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.is_dir():
            raise AdmissionError(f"storage path is missing or not a directory: {path}")
        stat = os.statvfs(path)
        free_bytes = stat.f_bavail * stat.f_frsize
        result.append(
            {
                "path": str(path.resolve()),
                "available_bytes": free_bytes,
                "required_bytes": required_bytes,
                "reserve_bytes": reserve_bytes,
                "pass": free_bytes >= required_bytes + reserve_bytes,
            }
        )
    return result


def collect_evidence(
    *,
    storage_paths: list[str],
    storage_required_bytes: int,
    storage_reserve_bytes: int,
    sample_seconds: float,
    include_task_cgroup: bool,
    repeat_pressure_samples: bool = False,
    allow_current_veritas_service: bool = False,
    allow_current_synthetic_service: bool = False,
    invocation_id: str | None = None,
    veritas_parent_invocation_id: str | None = None,
    veritas_parent_unit: str | None = None,
) -> dict[str, Any]:
    meminfo = parse_meminfo(Path("/proc/meminfo").read_text(encoding="utf-8"))
    vmstat_before = parse_vmstat(Path("/proc/vmstat").read_text(encoding="utf-8"))

    def read_pressure() -> dict[str, dict[str, dict[str, float]]]:
        return {
            name: parse_psi(Path(f"/proc/pressure/{name}").read_text(encoding="utf-8"))
            for name in ("memory", "cpu", "io")
        }

    pressure_samples: list[dict[str, Any]] = []
    if repeat_pressure_samples:
        pressure_samples.append({"elapsed_seconds": 0.0, "pressure": read_pressure()})
        elapsed = 0.0
        while elapsed < sample_seconds:
            delay = min(
                float(VERITAS_IO_ADMISSION["sample_interval_seconds"]),
                sample_seconds - elapsed,
            )
            time.sleep(delay)
            elapsed += delay
            pressure_samples.append({"elapsed_seconds": elapsed, "pressure": read_pressure()})
        pressure = pressure_samples[-1]["pressure"]
    else:
        pressure = read_pressure()
        time.sleep(sample_seconds)
    vmstat_after = parse_vmstat(Path("/proc/vmstat").read_text(encoding="utf-8"))
    swap_delta = {key: vmstat_after[key] - vmstat_before[key] for key in vmstat_before}
    protected = {unit: _read_service_cgroup(unit) for unit in CRITICAL_UNITS}
    user_cgroup = (
        CGROUP_ROOT / "user.slice" / f"user-{os.getuid()}.slice" / f"user@{os.getuid()}.service"
    )
    user_memory = _cgroup_memory(user_cgroup)
    user_memory_pressure = parse_psi((user_cgroup / "memory.pressure").read_text(encoding="utf-8"))
    workers = _active_midas_workers(
        allow_current_veritas_service=allow_current_veritas_service,
        allow_current_synthetic_service=allow_current_synthetic_service,
        invocation_id=invocation_id,
        veritas_parent_invocation_id=veritas_parent_invocation_id,
        veritas_parent_unit=veritas_parent_unit,
    )
    evidence: dict[str, Any] = {
        "sampled_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host_memory": {
            "total_bytes": meminfo["MemTotal"],
            "available_bytes": meminfo["MemAvailable"],
            "swap_total_bytes": meminfo["SwapTotal"],
            "swap_free_bytes": meminfo["SwapFree"],
            "swap_used_bytes": meminfo["SwapTotal"] - meminfo["SwapFree"],
            "swap_activity_pages_during_sample": swap_delta,
        },
        "pressure": pressure,
        "protected_service_cgroups": protected,
        "user_manager_cgroup": {
            "path": str(user_cgroup),
            **user_memory,
            "pressure": user_memory_pressure,
        },
        "active_midas_worker_services": workers,
        "storage": _storage_evidence(
            storage_paths,
            storage_required_bytes,
            storage_reserve_bytes,
        ),
    }
    if repeat_pressure_samples:
        evidence["pressure_samples"] = pressure_samples
    if include_task_cgroup:
        cgroup_path = _current_cgroup()
        evidence["task_cgroup"] = {
            "path": str(cgroup_path),
            **_cgroup_memory(cgroup_path),
        }
    return evidence


def evaluate_evidence(
    evidence: dict[str, Any],
    *,
    profile: str,
    memory_budget_bytes: int,
    require_task_cgroup: bool,
) -> list[str]:
    limits = PROFILES[profile]
    reasons: list[str] = []
    host = evidence["host_memory"]
    if host["available_bytes"] < int(limits["min_available_mib"]) * MIB + memory_budget_bytes:
        reasons.append("host_memavailable_below_floor_plus_task_budget")
    if host["swap_free_bytes"] < int(limits["min_swap_free_mib"]) * MIB:
        reasons.append("swap_reserve_below_profile_floor")
    swap_activity = sum(host["swap_activity_pages_during_sample"].values())
    if swap_activity > int(limits["max_swap_activity_pages"]):
        reasons.append("swap_activity_above_profile_limit")
    checks: list[tuple[str, str, str, str]] = [
        ("memory", "some", "memory_some_avg10", "avg10"),
        ("memory", "some", "memory_some_avg60", "avg60"),
        ("memory", "full", "memory_full_avg10", "avg10"),
        ("memory", "full", "memory_full_avg60", "avg60"),
        ("cpu", "some", "cpu_some_avg10", "avg10"),
        ("cpu", "some", "cpu_some_avg60", "avg60"),
        ("io", "some", "io_some_avg10", "avg10"),
        ("io", "some", "io_some_avg60", "avg60"),
    ]
    if profile != "veritas":
        checks.extend(
            (
                ("io", "full", "io_full_avg10", "avg10"),
                ("io", "full", "io_full_avg60", "avg60"),
            )
        )
    pressure = evidence["pressure"]
    pressure_windows = [pressure]
    if profile == "veritas":
        samples = evidence.get("pressure_samples")
        if not isinstance(samples, list) or len(samples) < 4:
            reasons.append("missing_repeated_io_pressure_samples")
        else:
            pressure_windows = [
                sample.get("pressure")
                for sample in samples
                if isinstance(sample, dict) and isinstance(sample.get("pressure"), dict)
            ]
            if len(pressure_windows) != len(samples):
                reasons.append("invalid_repeated_io_pressure_samples")

    for resource, kind, limit_key, average in checks:
        for window in pressure_windows:
            current = window.get(resource, {}).get(kind, {}).get(average)
            if current is None:
                reasons.append(f"missing_{resource}_{kind}_{average}_pressure")
            elif current > float(limits[limit_key]):
                reasons.append(f"{resource}_{kind}_{average}_pressure_above_profile_limit")
    if profile == "veritas" and pressure_windows:
        reasons.extend(_veritas_io_admission_reasons(pressure_windows))
    protected_floor = int(limits["protected_headroom_mib"]) * MIB
    for unit, state in evidence["protected_service_cgroups"].items():
        if state["memory_headroom_bytes"] < protected_floor:
            reasons.append(f"{unit.replace('.', '_')}_memory_headroom_below_profile_floor")
    user_pressure = evidence["user_manager_cgroup"]["pressure"]
    for kind, limit_key in (("some", "memory_some"), ("full", "memory_full")):
        for average in ("avg10", "avg60"):
            current = user_pressure.get(kind, {}).get(average)
            if current is None:
                reasons.append(f"missing_user_manager_memory_{kind}_{average}_pressure")
            elif current > float(limits[f"{limit_key}_{average}"]):
                reasons.append(f"user_manager_memory_{kind}_{average}_pressure_above_profile_limit")
    if evidence["active_midas_worker_services"]:
        reasons.append("another_midas_worker_service_is_active")
    if any(not item["pass"] for item in evidence["storage"]):
        reasons.append("storage_required_bytes_or_reserve_unavailable")
    if require_task_cgroup:
        task = evidence.get("task_cgroup")
        if task is None:
            reasons.append("task_cgroup_evidence_missing")
        else:
            headroom = task["memory_headroom_bytes"]
            if headroom is None:
                reasons.append("task_cgroup_has_no_finite_memoryhigh_or_memorymax")
            elif headroom < memory_budget_bytes:
                reasons.append("task_cgroup_headroom_below_task_budget")
    return reasons


def _consecutive_pressure_limit_exceeded(
    values: list[float], *, limit: float, consecutive: int
) -> bool:
    current = 0
    for value in values:
        current = current + 1 if value > limit else 0
        if current >= consecutive:
            return True
    return False


def _veritas_io_admission_reasons(
    pressure_windows: list[dict[str, dict[str, dict[str, float]]]],
) -> list[str]:
    reasons: list[str] = []
    full = [window.get("io", {}).get("full", {}) for window in pressure_windows]
    avg10 = [item.get("avg10") for item in full]
    avg60 = [item.get("avg60") for item in full]
    if any(value is None for value in avg10):
        reasons.append("missing_io_full_avg10_pressure")
    if any(value is None for value in avg60):
        reasons.append("missing_io_full_avg60_pressure")
    if any(value is None for value in avg10 + avg60):
        return reasons

    avg10_values = [value for value in avg10 if value is not None]
    avg60_values = [value for value in avg60 if value is not None]
    hard10 = float(VERITAS_IO_ADMISSION["hard_avg10"])
    hard60 = float(VERITAS_IO_ADMISSION["hard_avg60"])
    if any(value > hard10 for value in avg10_values) or any(
        value > hard60 for value in avg60_values
    ):
        reasons.append("io_full_pressure_above_veritas_hard_limit")
    consecutive = int(VERITAS_IO_ADMISSION["consecutive_samples"])
    if _consecutive_pressure_limit_exceeded(
        avg10_values,
        limit=float(PROFILES["veritas"]["io_full_avg10"]),
        consecutive=consecutive,
    ):
        reasons.append("io_full_avg10_pressure_sustained_above_profile_limit")
    if _consecutive_pressure_limit_exceeded(
        avg60_values,
        limit=float(PROFILES["veritas"]["io_full_avg60"]),
        consecutive=consecutive,
    ):
        reasons.append("io_full_avg60_pressure_sustained_above_profile_limit")
    return reasons


def veritas_runtime_io_cancel_reason(
    samples: list[dict[str, float]],
) -> str | None:
    """Return a fail-closed cancellation reason for sampled runtime I/O PSI."""
    if not samples:
        return None
    for item in samples:
        for key in ("avg10", "avg60"):
            value = item.get(key)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                return "io_pressure_sample_invalid"
    current = samples[-1]
    avg10 = current.get("avg10")
    avg60 = current.get("avg60")
    assert avg10 is not None and avg60 is not None
    if avg10 > float(VERITAS_IO_RUNTIME["hard_avg10"]):
        return "io_full_avg10_pressure_above_runtime_hard_limit"
    if avg60 > float(VERITAS_IO_RUNTIME["hard_avg60"]):
        return "io_full_avg60_pressure_above_runtime_hard_limit"
    consecutive = int(VERITAS_IO_RUNTIME["consecutive_samples"])
    recent = samples[-consecutive:]
    if len(recent) < consecutive:
        return None
    if all(item["avg10"] > float(VERITAS_IO_RUNTIME["cancel_avg10"]) for item in recent):
        return "io_full_avg10_pressure_sustained_during_veritas_run"
    if all(item["avg60"] > float(VERITAS_IO_RUNTIME["cancel_avg60"]) for item in recent):
        return "io_full_avg60_pressure_sustained_during_veritas_run"
    return None


def _lock_path() -> Path:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime_dir:
        raise AdmissionError("XDG_RUNTIME_DIR is unset; refusing an unowned global workload lock")
    path = Path(runtime_dir)
    if path.is_symlink() or not path.is_dir() or path.stat().st_uid != os.getuid():
        raise AdmissionError("XDG_RUNTIME_DIR is not a user-owned real directory")
    return path / "midas-heavy-workload.lock"


def _acquire_lock() -> Any:
    path = _lock_path()
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    info = os.fstat(fd)
    if info.st_uid != os.getuid() or not stat.S_ISREG(info.st_mode):
        os.close(fd)
        raise AdmissionError("workload lock is not a user-owned regular file")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        os.close(fd)
        raise AdmissionError("another MIDAS operation owns the heavy-workload lock") from error
    os.ftruncate(fd, 0)
    os.write(fd, json.dumps({"pid": os.getpid(), "started_at": time.time()}).encode())
    return os.fdopen(fd, "r+")


def _check_lock_free() -> None:
    path = _lock_path()
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        if os.fstat(fd).st_uid != os.getuid():
            raise AdmissionError("workload lock is not owned by the current user")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise AdmissionError("another MIDAS operation owns the heavy-workload lock") from error
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _gate(
    args: argparse.Namespace, *, include_task_cgroup: bool, lock_held: bool
) -> tuple[dict[str, Any], list[str]]:
    if args.sample_seconds <= 0 or args.sample_seconds > 60:
        raise AdmissionError("--sample-seconds must be between 0 and 60")
    if args.profile in {"backup", "veritas"} and args.sample_seconds < 30:
        raise AdmissionError(
            f"{args.profile} admission requires a 30-second swap and pressure sample"
        )
    evidence = collect_evidence(
        storage_paths=args.storage_path,
        storage_required_bytes=args.storage_required_mib * MIB,
        storage_reserve_bytes=args.storage_reserve_mib * MIB,
        sample_seconds=args.sample_seconds,
        include_task_cgroup=include_task_cgroup,
        repeat_pressure_samples=args.profile == "veritas",
        allow_current_veritas_service=args.profile == "veritas",
        allow_current_synthetic_service=args.profile == "synthetic-validation"
        and include_task_cgroup,
        invocation_id=getattr(args, "invocation_id", None),
        veritas_parent_invocation_id=getattr(args, "parent_service_invocation_id", None)
        or getattr(args, "service_owner_invocation_id", None),
        veritas_parent_unit=getattr(args, "parent_service_unit", None)
        or getattr(args, "service_owner_unit", None),
    )
    reasons = evaluate_evidence(
        evidence,
        profile=args.profile,
        memory_budget_bytes=args.memory_budget_mib * MIB,
        require_task_cgroup=include_task_cgroup,
    )
    if not lock_held:
        try:
            _check_lock_free()
        except AdmissionError:
            reasons.append("another_midas_operation_owns_heavy_workload_lock")
    evidence["decision"] = "ADMIT" if not reasons else "DENY"
    evidence["blocking_reasons"] = sorted(set(reasons))
    return evidence, sorted(set(reasons))


def _print_evidence(evidence: dict[str, Any], stream: Any = sys.stderr) -> None:
    print(json.dumps(evidence, sort_keys=True, indent=2), file=stream)


def _kill_unit(unit: str, grace_seconds: float) -> dict[str, Any]:
    result: dict[str, Any] = {
        "unit": unit,
        "term_requested": False,
        "kill_requested": False,
        "inactive_confirmed": False,
        "error": None,
    }
    try:
        term = _systemctl("kill", "--signal=TERM", "--kill-whom=all", unit, check=False)
    except AdmissionError as error:
        result["error"] = _safe_diagnostic(str(error))
        return result
    result["term_requested"] = term.returncode == 0
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        try:
            state = _systemctl("show", unit, "-p", "ActiveState", "--value", check=False)
        except AdmissionError as error:
            result["error"] = _safe_diagnostic(str(error))
            return result
        if state.returncode != 0 or state.stdout.strip() in {"inactive", "failed", ""}:
            result["inactive_confirmed"] = state.returncode == 0
            return result
        time.sleep(0.1)
    try:
        killed = _systemctl("kill", "--signal=KILL", "--kill-whom=all", unit, check=False)
        result["kill_requested"] = killed.returncode == 0
    except AdmissionError as error:
        result["error"] = _safe_diagnostic(str(error))
    return result


def _read_veritas_runtime_io_pressure() -> dict[str, float]:
    try:
        marker = os.environ.get("MIDAS_VERITAS_CI_TEST")
        if marker is not None:
            if marker != VERITAS_CI_TEST_MARKER:
                raise AdmissionError("Veritas CI pressure override marker is invalid")
            ci_context = _veritas_ci_test_context(
                unit_name=os.environ.get("MIDAS_VERITAS_CI_PARENT_UNIT"),
                invocation_id=os.environ.get("MIDAS_VERITAS_CI_PARENT_INVOCATION_ID"),
            )
            if not ci_context:
                raise AdmissionError("Veritas CI pressure override is not bound to its test unit")
            pressure_path = Path(ci_context["pressure_file"])
        else:
            pressure_path = Path("/proc/pressure/io")
        pressure = parse_psi(pressure_path.read_text(encoding="utf-8"))
        full = pressure.get("full", {})
        avg10 = full.get("avg10")
        avg60 = full.get("avg60")
    except (OSError, ValueError, AdmissionError) as error:
        raise AdmissionError(f"cannot monitor runtime I/O PSI: {error}") from error
    if avg10 is None or avg60 is None:
        raise AdmissionError("runtime I/O PSI full averages are missing")
    return {"avg10": avg10, "avg60": avg60}


def _cancel_bounded_unit(
    process: subprocess.Popen[Any], unit: str, grace_seconds: float
) -> dict[str, Any]:
    unit_result = _kill_unit(unit, grace_seconds)
    runner_signal: str | None = None
    try:
        process.wait(timeout=grace_seconds + 2)
    except subprocess.TimeoutExpired:
        for signal_name, signal_value in (("TERM", signal.SIGTERM), ("KILL", signal.SIGKILL)):
            try:
                os.killpg(process.pid, signal_value)
            except ProcessLookupError:
                pass
            except OSError as error:
                runner_signal = f"{signal_name}_failed:{type(error).__name__}"
            else:
                runner_signal = signal_name
            try:
                process.wait(timeout=1)
                break
            except subprocess.TimeoutExpired:
                continue
        if process.poll() is None:
            try:
                process.kill()
                process.wait(timeout=1)
                runner_signal = "process_kill_fallback"
            except (OSError, subprocess.TimeoutExpired):
                runner_signal = "runner_client_exit_unconfirmed"
    return {
        "systemd_unit": unit_result,
        "runner_client_exit_confirmed": process.poll() is not None,
        "runner_process_group_signal": runner_signal,
    }


def _wait_for_veritas_process(
    process: subprocess.Popen[Any],
    unit: str,
    *,
    timeout_seconds: float,
    termination_grace_seconds: float,
    output: _RunnerOutput | None = None,
    on_poll: Any = None,
    on_watchdog: Any = None,
    on_cancel: Any = None,
) -> int:
    deadline = time.monotonic() + timeout_seconds
    samples: list[dict[str, float]] = []
    while True:
        if output is not None:
            output.drain()
        if on_poll is not None:
            on_poll()
        return_code = process.poll()
        if return_code is not None:
            if output is not None:
                output.drain()
            return return_code
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            if on_watchdog is not None:
                on_watchdog({"kind": "timeout", "at_utc": _utc_now()})
            cancellation = _cancel_bounded_unit(process, unit, termination_grace_seconds)
            if on_cancel is not None:
                on_cancel(cancellation)
            return 124
        try:
            sample = _read_veritas_runtime_io_pressure()
        except AdmissionError as error:
            return_code = process.poll()
            if return_code is not None:
                return return_code
            _print_evidence(
                {
                    "decision": "CANCEL",
                    "reason": "runtime_io_pressure_unavailable",
                    "detail": str(error),
                    "recent_io_pressure": samples,
                }
            )
            if on_watchdog is not None:
                on_watchdog(
                    {
                        "kind": "runtime_io_pressure_unavailable",
                        "detail": str(error)[:512],
                        "samples": samples,
                        "at_utc": _utc_now(),
                    }
                )
            cancellation = _cancel_bounded_unit(process, unit, termination_grace_seconds)
            if on_cancel is not None:
                on_cancel(cancellation)
            return VERITAS_RUNTIME_PRESSURE_CANCELLED
        samples = (samples + [sample])[-int(VERITAS_IO_RUNTIME["consecutive_samples"]) :]
        reason = veritas_runtime_io_cancel_reason(samples)
        if reason:
            return_code = process.poll()
            if return_code is not None:
                return return_code
            _print_evidence(
                {
                    "decision": "CANCEL",
                    "reason": reason,
                    "recent_io_pressure": samples,
                    "sampled_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
            )
            if on_watchdog is not None:
                on_watchdog({"kind": reason, "samples": samples, "at_utc": _utc_now()})
            cancellation = _cancel_bounded_unit(process, unit, termination_grace_seconds)
            if on_cancel is not None:
                on_cancel(cancellation)
            return VERITAS_RUNTIME_PRESSURE_CANCELLED
        time.sleep(min(float(VERITAS_IO_RUNTIME["poll_interval_seconds"]), remaining))


def _wait_for_runner_process(
    process: subprocess.Popen[Any],
    unit: str,
    *,
    timeout_seconds: float,
    termination_grace_seconds: float,
    output: _RunnerOutput,
    on_timeout: Any = None,
    on_cancel: Any = None,
    on_poll: Any = None,
) -> int:
    deadline = time.monotonic() + timeout_seconds
    while True:
        output.drain()
        if on_poll is not None:
            on_poll()
        return_code = process.poll()
        if return_code is not None:
            output.drain()
            return return_code
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            if on_timeout is not None:
                on_timeout({"kind": "timeout", "at_utc": _utc_now()})
            cancellation = _cancel_bounded_unit(process, unit, termination_grace_seconds)
            if on_cancel is not None:
                on_cancel(cancellation)
            return 124
        time.sleep(min(0.1, remaining))


def _classify_guarded_result(
    *,
    profile: str,
    return_code: int | None,
    unit: dict[str, str] | None,
    inner: dict[str, Any] | None,
    watchdog: dict[str, Any] | None,
    parent_signal: int | None,
    runner_error: str | None,
    unit_was_active_after_client_exit: bool,
    systemd_wait_completed: bool = False,
    synthetic_expected_exit: int | None = None,
    applied_limits_verified: bool = False,
    unit_cleanup_confirmed: bool = False,
    unit_after_wait: dict[str, str] | None = None,
) -> str:
    if unit_was_active_after_client_exit:
        return "result_missing_indeterminate"
    if parent_signal is not None:
        if not _unit_termination_confirmed(unit, inner):
            return "result_missing_indeterminate"
        return "cancelled_by_parent_signal"
    if watchdog:
        if not _unit_termination_confirmed(unit, inner):
            return "result_missing_indeterminate"
        if watchdog.get("kind") == "timeout":
            return "timed_out"
        return "psi_watchdog_cancelled"
    if inner and inner.get("phase") == "inner_gate_failed":
        return "inner_admission_failed"
    if inner and inner.get("decision") == "DENY":
        return "admission_denied"
    systemd_result = unit.get("Result") if unit else None
    if systemd_result == "timeout":
        return "timed_out"
    memory = (inner or {}).get("cgroup_metrics", {}).get("memory", {})
    oom_kill_count = memory.get("oom_kill_events", 0) if isinstance(memory, dict) else 0
    if systemd_result in {"oom-kill", "oom"} or oom_kill_count:
        return "worker_killed_oom_or_oomd"
    if inner and inner.get("watchdog_intervention"):
        if inner["watchdog_intervention"].get("kind") == "timeout":
            return "timed_out"
        return "psi_watchdog_cancelled"
    if profile == "synthetic-validation":
        if inner and inner.get("phase") == "worker_start_failed":
            return "worker_startup_failed"
        if not inner or inner.get("phase") != "worker_exec_requested":
            if runner_error and unit is None:
                return "unit_creation_failed"
            if unit and unit.get("ExecMainStartTimestamp") in {None, "", "n/a"}:
                return "unit_created_not_started"
            return "result_missing_indeterminate"
        if (
            not unit
            or not re.fullmatch(r"[0-9a-f]{32}", unit.get("InvocationID", ""))
            or unit.get("ExecMainStartTimestamp") in {None, "", "n/a"}
            or not systemd_wait_completed
            or not applied_limits_verified
            or not unit_cleanup_confirmed
            or unit_was_active_after_client_exit
            or synthetic_expected_exit not in {0, 1}
            or return_code != synthetic_expected_exit
        ):
            return "result_missing_indeterminate"
        final_unit = unit_after_wait
        if final_unit is not None and final_unit.get("LoadState") != "not-found":
            result = final_unit.get("Result")
            status = final_unit.get("ExecMainStatus")
            code = final_unit.get("ExecMainCode")
            if result not in {None, "success", "exit-code"}:
                return "result_missing_indeterminate"
            if status is not None and status != "":
                try:
                    if int(status) != synthetic_expected_exit:
                        return "result_missing_indeterminate"
                except ValueError:
                    return "result_missing_indeterminate"
            if code not in {None, "", "exited"}:
                return "result_missing_indeterminate"
        return "worker_succeeded" if synthetic_expected_exit == 0 else "worker_failed"
    if inner and inner.get("phase") == "worker_start_failed":
        return "worker_startup_failed"
    if profile == "veritas" and inner and inner.get("phase") == "worker_finished":
        worker_code = inner.get("worker_exit_code")
        worker_signal = inner.get("worker_signal")
        context = inner.get("execution_context")
        transient = context.get("transient_unit") if isinstance(context, dict) else None
        release = context.get("release") if isinstance(context, dict) else None
        if (
            not systemd_wait_completed
            or not applied_limits_verified
            or not unit_cleanup_confirmed
            or not isinstance(unit, dict)
            or not re.fullmatch(r"[0-9a-f]{32}", unit.get("InvocationID", ""))
            or unit.get("ExecMainStartTimestamp") in {None, "", "n/a"}
            or not isinstance(transient, dict)
            or transient.get("limits_verified") is not True
            or not isinstance(release, dict)
            or release.get("passed") is not True
        ):
            return "result_missing_indeterminate"
        if unit_after_wait and unit_after_wait.get("LoadState") != "not-found":
            if unit_after_wait.get("Result") not in {"success", "exit-code"} or unit_after_wait.get(
                "ExecMainCode"
            ) not in {"exited", "killed", "dumped"}:
                return "result_missing_indeterminate"
            try:
                systemd_status = int(unit_after_wait.get("ExecMainStatus", ""))
            except ValueError:
                return "result_missing_indeterminate"
            expected_status = (
                worker_code
                if worker_signal is None and isinstance(worker_code, int)
                else worker_signal
            )
            if systemd_status != expected_status:
                return "result_missing_indeterminate"
            if (unit_after_wait.get("Result") == "success") != (worker_code == 0):
                return "result_missing_indeterminate"
        if worker_signal is not None:
            if not isinstance(worker_signal, int) or worker_signal <= 0:
                return "result_missing_indeterminate"
            return "worker_terminated_by_signal"
        if not isinstance(worker_code, int) or isinstance(worker_code, bool):
            return "result_missing_indeterminate"
        if return_code != worker_code:
            return "result_missing_indeterminate"
        return "worker_succeeded" if worker_code == 0 else "worker_failed"
    if profile == "veritas" and inner and inner.get("phase") == "worker_running":
        return "result_missing_indeterminate"
    if profile == "veritas":
        if runner_error and unit is None:
            return "unit_creation_failed"
        if unit and unit.get("ExecMainStartTimestamp") in {None, "", "n/a"}:
            return "unit_created_not_started"
        return "result_missing_indeterminate"
    if profile != "veritas" and inner and inner.get("phase") == "worker_exec_requested":
        if return_code is None:
            return "result_missing_indeterminate"
        if return_code < 0:
            return "worker_terminated_by_signal"
        if return_code == 127:
            return "result_missing_indeterminate"
        return "worker_succeeded" if return_code == 0 else "worker_failed"
    if inner and inner.get("worker_signal"):
        return "worker_terminated_by_signal"
    if unit and unit.get("ExecMainCode") in {"killed", "dumped"}:
        try:
            int(unit.get("ExecMainStatus", "0"))
        except ValueError:
            return "result_missing_indeterminate"
        return "worker_terminated_by_signal"
    if inner and inner.get("phase") == "worker_finished":
        worker_code = inner.get("worker_exit_code")
        if worker_code == 0 and return_code == 0 and systemd_result in {None, "success"}:
            return "worker_succeeded"
        if worker_code not in {None, 0}:
            return "worker_failed"
        if worker_code == 0 and return_code not in {None, 0}:
            return "result_missing_indeterminate"
    if unit:
        started = unit.get("ExecMainStartTimestamp") not in {None, "", "n/a"}
        if not started and unit.get("ActiveState") in {"failed", "inactive"}:
            return "unit_created_not_started"
        if started and (
            not inner or inner.get("phase") in {"inner_gate_starting", "inner_gate_failed"}
        ):
            return "worker_startup_failed"
    if runner_error and unit is None:
        return "unit_creation_failed"
    if return_code not in {None, 0} and unit is None:
        return "unit_creation_failed"
    if profile != "veritas" and return_code == 0 and unit is None:
        return "worker_succeeded"
    return "result_missing_indeterminate"


def _unit_is_active(unit: dict[str, str] | None) -> bool:
    return bool(unit and unit.get("ActiveState") in {"active", "activating", "reloading"})


def _unit_termination_confirmed(unit: dict[str, str] | None, inner: dict[str, Any] | None) -> bool:
    if inner and inner.get("phase") == "worker_finished":
        return True
    if not unit or unit.get("ActiveState") not in {"inactive", "failed"}:
        return False
    return unit.get("ExecMainStartTimestamp") not in {None, "", "n/a"}


def _safe_diagnostic(value: str | None) -> str | None:
    if not value:
        return None
    clean = " ".join(value.split())
    clean = re.sub(
        r"(?i)(password|passwd|secret|token|api[_-]?key)(\s*[:=]\s*)[^\s,;]+",
        r"\1\2<redacted>",
        clean,
    )
    return clean[:512]


def _validate_synthetic_inner_args(
    args: argparse.Namespace, command: list[str], status_dir: Path
) -> tuple[int, str, dict[str, str], dict[str, Any]]:
    expected_exit = _synthetic_expected_exit(command)
    if (
        args.memory_budget_mib <= 0
        or args.memory_budget_mib > SYNTHETIC_RUN_LIMITS["memory_budget_mib"]
        or not 1 <= args.sample_seconds <= SYNTHETIC_RUN_LIMITS["max_sample_seconds"]
        or not 0 < args.execution_timeout_seconds <= SYNTHETIC_RUN_LIMITS["timeout_seconds"]
        or args.storage_required_mib != 0
        or args.storage_reserve_mib != 0
        or [Path(path).resolve() for path in args.storage_path] != [SYNTHETIC_TEST_ROOT.resolve()]
    ):
        raise AdmissionError("synthetic inner admission arguments exceed the fixed test profile")
    unit, properties, metrics = _validate_synthetic_unit_context(args.invocation_id, status_dir)
    return expected_exit, unit, properties, metrics


def _run_inside(args: argparse.Namespace, command: list[str]) -> int:
    if not command:
        raise AdmissionError("internal bounded command is missing")
    if not re.fullmatch(r"[0-9a-f]{32}", args.invocation_id or ""):
        raise AdmissionError("internal guarded invocation id is invalid")
    status_path = Path(args.status_path)
    status_dir = status_path.parent
    if (
        status_dir.is_symlink()
        or not status_dir.is_dir()
        or status_dir.name != f"{args.invocation_id}.control"
        or status_path.name != "inner-status.json"
    ):
        raise AdmissionError("internal guarded status path is missing or unsafe")
    if args.profile == "synthetic-validation":
        try:
            expected_status_dir = (
                SYNTHETIC_RECEIPT_DIR / f"{args.invocation_id}.control"
            ).resolve()
        except OSError as error:
            raise AdmissionError(f"synthetic status path could not be resolved: {error}") from error
        if status_dir.resolve() != expected_status_dir:
            raise AdmissionError("synthetic status directory is outside its private receipt root")
    _write_inner_status(status_path, args.invocation_id, phase="inner_gate_starting")
    veritas_context: dict[str, Any] | None = None
    if args.profile == "veritas":
        parent_invocation_id = args.parent_service_invocation_id or ""
        parent_pid = args.parent_service_pid
        parent_unit = getattr(args, "parent_service_unit", None) or VERITAS_SERVICE_UNIT
        if (
            not re.fullmatch(r"[0-9a-f]{32}", parent_invocation_id)
            or not isinstance(parent_pid, int)
            or parent_pid <= 1
            or parent_unit not in {VERITAS_SERVICE_UNIT, VERITAS_CI_SERVICE_UNIT}
        ):
            raise AdmissionError("Veritas inner invocation has no verified parent service identity")
        ci_test_context = _veritas_ci_test_context(
            unit_name=parent_unit, invocation_id=parent_invocation_id
        )
        output_root = (
            Path(ci_test_context["output_root"]) if ci_test_context else VERITAS_OUTPUT_ROOT
        )
        _validate_veritas_runtime_context(
            owner_invocation_id=parent_invocation_id,
            owner_pid=parent_pid,
            owner_unit=parent_unit,
            require_current_service_cgroup=False,
        )
        if not args.release_root or not args.expected_module_sha256:
            raise AdmissionError("Veritas inner invocation is missing its immutable release pin")
        release = _validate_veritas_worker_command(
            command,
            Path(args.release_root),
            args.expected_module_sha256,
            output_root=output_root,
        )
        checkpoint_before = verify_veritas_checkpoint(
            output_root,
            release,
            expected_campaign_sha256=(
                ci_test_context["campaign_sha256"] if ci_test_context else VERITAS_CAMPAIGN_SHA256
            ),
        )
        if checkpoint_before["state_sha256"] != args.expected_checkpoint_state_sha256:
            raise AdmissionError("Veritas checkpoint changed after outer admission")
        transient = _validate_veritas_transient_unit(
            expected_status_dir=status_dir,
            parent_invocation_id=parent_invocation_id,
            parent_pid=parent_pid,
            output_root=output_root,
            network_restricted=ci_test_context is not None,
        )
        veritas_context = {
            "release": release,
            "checkpoint_before": checkpoint_before,
            "transient_unit": transient,
            "parent_service_invocation_id": parent_invocation_id,
            "parent_service_unit": parent_unit,
            "parent_service_pid": parent_pid,
            "ci_test": ci_test_context,
        }
    _write_inner_status(
        status_path,
        args.invocation_id,
        phase="inner_gate_starting",
        execution_context=veritas_context,
    )
    synthetic_context: dict[str, Any] | None = None
    try:
        if args.profile == "synthetic-validation":
            expected_exit, unit, properties, metrics = _validate_synthetic_inner_args(
                args, command, status_dir
            )
            synthetic_context = {
                "expected_worker_exit_code": expected_exit,
                "unit": unit,
                "unit_properties": properties,
                "cgroup_metrics": metrics,
                "network_isolation": metrics.get("network_isolation"),
            }
        evidence, reasons = _gate(args, include_task_cgroup=True, lock_held=True)
    except Exception as error:
        try:
            _write_inner_status(
                status_path,
                args.invocation_id,
                phase="inner_gate_failed",
                decision="DENY",
                detail=_safe_diagnostic(f"{type(error).__name__}: {error}"),
                synthetic_context=synthetic_context,
                execution_context=veritas_context,
            )
        except (OSError, AdmissionError):
            pass
        raise
    decision = "DENY" if reasons else "ADMIT"
    evidence["decision"] = decision
    evidence["blocking_reasons"] = sorted(set(reasons))
    try:
        _write_inner_status(
            status_path,
            args.invocation_id,
            phase="inner_admission_denied" if reasons else "inner_admitted",
            decision=decision,
            evidence=evidence,
            synthetic_context=synthetic_context,
            execution_context=veritas_context,
        )
    except (OSError, AdmissionError) as error:
        print(
            json.dumps(
                {
                    "decision": "INDETERMINATE",
                    "reason": "inner_admission_receipt_unavailable",
                    "detail": _safe_diagnostic(str(error)),
                }
            ),
            file=sys.stderr,
        )
        return RUNNER_RESULT_MISSING
    _print_evidence(_compact_evidence(evidence))
    if reasons:
        return 75
    os.environ["MIDAS_RESOURCE_PREFLIGHT_CGROUP"] = evidence["task_cgroup"]["path"]
    os.environ["MIDAS_RESOURCE_PREFLIGHT_AT_UTC"] = evidence["sampled_at_utc"]
    os.environ["MIDAS_RESOURCE_PREFLIGHT_PROFILE"] = args.profile
    if args.profile == "veritas":
        assert veritas_context is not None
        # Recheck immediately after the 30-second inner admission window. The
        # checkpoint must still be exactly the state approved by the outer gate.
        checkpoint_ready = verify_veritas_checkpoint(
            Path(veritas_context["ci_test"]["output_root"])
            if veritas_context.get("ci_test")
            else VERITAS_OUTPUT_ROOT,
            veritas_context["release"],
            expected_campaign_sha256=(
                veritas_context["ci_test"]["campaign_sha256"]
                if veritas_context.get("ci_test")
                else VERITAS_CAMPAIGN_SHA256
            ),
        )
        if checkpoint_ready["state_sha256"] != args.expected_checkpoint_state_sha256:
            _write_inner_status(
                status_path,
                args.invocation_id,
                phase="inner_gate_failed",
                decision="DENY",
                detail="Veritas checkpoint changed during inner admission",
                execution_context=veritas_context,
            )
            return 75
        transient_now = _validate_veritas_transient_unit(
            expected_status_dir=status_dir,
            parent_invocation_id=args.parent_service_invocation_id,
            parent_pid=args.parent_service_pid,
            output_root=(
                Path(veritas_context["ci_test"]["output_root"])
                if veritas_context.get("ci_test")
                else VERITAS_OUTPUT_ROOT
            ),
            network_restricted=veritas_context.get("ci_test") is not None,
        )
        veritas_context["checkpoint_at_worker_start"] = checkpoint_ready
        veritas_context["transient_unit"] = transient_now
        return _supervise_veritas_worker(
            command,
            status_path=status_path,
            invocation_id=args.invocation_id,
            execution_context=veritas_context,
            timeout_seconds=min(
                float(args.execution_timeout_seconds),
                float(VERITAS_RUN_LIMITS["timeout_seconds"]),
            ),
            termination_grace_seconds=float(args.termination_grace_seconds),
        )
    synthetic_filesystem_isolation = None
    synthetic_network_isolation = None
    worker_fd_close_count = 0
    if args.profile == "synthetic-validation":
        try:
            worker_fd_close_count = _close_unexpected_worker_fds()
            synthetic_filesystem_isolation = _apply_synthetic_filesystem_isolation(status_dir)
            synthetic_network_isolation = _install_synthetic_network_filter()
            if not synthetic_network_isolation.get("restricted"):
                raise AdmissionError("worker network seccomp probes were not all denied")
        except (AdmissionError, OSError) as error:
            _write_inner_status(
                status_path,
                args.invocation_id,
                phase="worker_start_failed",
                decision="ADMIT",
                startup_error=_safe_diagnostic(f"{type(error).__name__}: {error}"),
                synthetic_context=synthetic_context,
            )
            return 126
    try:
        _write_inner_status(
            status_path,
            args.invocation_id,
            phase="worker_exec_requested",
            decision="ADMIT",
            exec_target=Path(command[0]).name,
            worker_start_requested_at_utc=_utc_now(),
            worker_start_requested_monotonic=time.monotonic(),
            filesystem_isolation=synthetic_filesystem_isolation,
            network_isolation=synthetic_network_isolation,
            inherited_descriptor_isolation={
                "standard_streams_only": True,
                "unexpected_descriptors_closed": worker_fd_close_count,
            },
            synthetic_context={
                **(synthetic_context or {}),
                "network_isolation": synthetic_network_isolation,
            },
        )
    except (OSError, AdmissionError) as error:
        print(
            json.dumps(
                {
                    "decision": "INDETERMINATE",
                    "reason": "worker_launch_receipt_unavailable",
                    "detail": _safe_diagnostic(str(error)),
                }
            ),
            file=sys.stderr,
        )
        return RUNNER_RESULT_MISSING
    try:
        worker_environment = (
            {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "LANG": "C", "LC_ALL": "C"}
            if args.profile == "synthetic-validation"
            else os.environ
        )
        os.execve(command[0], command, worker_environment)
    except OSError as error:
        _write_inner_status(
            status_path,
            args.invocation_id,
            phase="worker_start_failed",
            decision="ADMIT",
            worker_error=_safe_diagnostic(f"{type(error).__name__}: {error}"),
        )
        return 127
    return 70


def _run_command(args: argparse.Namespace) -> int:
    raw_command = list(args.command)
    command = raw_command[1:] if raw_command and raw_command[0] == "--" else raw_command
    synthetic_expected_exit: int | None = None
    try:
        if not command:
            raise AdmissionError("run requires a command after --")
        args.source_revision = getattr(args, "source_revision", "")
        args.release_identity = getattr(args, "release_identity", "")
        args.release_root = getattr(args, "release_root", None)
        args.expected_module_sha256 = getattr(args, "expected_module_sha256", None)
        args.label = getattr(args, "label", "task")
        if args.profile == "veritas":
            _validate_veritas_run_limits(args)
        if args.source_revision and not re.fullmatch(
            r"[A-Za-z0-9._-]{1,128}", args.source_revision
        ):
            raise AdmissionError("--source-revision must be a short immutable identifier")
        if args.release_identity and not re.fullmatch(
            r"[A-Za-z0-9._-]{1,128}", args.release_identity
        ):
            raise AdmissionError("--release-identity must be a short immutable identifier")
        if args.profile == "veritas":
            if (
                args.source_revision != VERITAS_APPROVED_SOURCE_REVISION
                or args.release_identity != VERITAS_RELEASE_ID
                or not args.release_root
                or not args.expected_module_sha256
            ):
                raise AdmissionError(
                    "Veritas run must pin the approved release and module identity"
                )
            args.release_verification = _validate_veritas_worker_command(
                command, Path(args.release_root), args.expected_module_sha256
            )
            args.service_owner_invocation_id = _validate_veritas_runtime_context()
            args.service_owner_unit = _current_veritas_service_unit() or VERITAS_SERVICE_UNIT
            if args.service_owner_unit not in {VERITAS_SERVICE_UNIT, VERITAS_CI_SERVICE_UNIT}:
                raise AdmissionError("Veritas service unit identity could not be established")
            args.ci_test_context = _veritas_ci_test_context(
                unit_name=args.service_owner_unit,
                invocation_id=args.service_owner_invocation_id,
            )
            args.veritas_output_root = (
                Path(args.ci_test_context["output_root"])
                if args.ci_test_context
                else VERITAS_OUTPUT_ROOT
            )
            if args.ci_test_context:
                # The installed permanent service command remains byte-for-byte
                # the proposed production unit. Only after its full command pin
                # is verified do we redirect the worker into disposable CI data.
                command = _veritas_worker_command(
                    Path(args.release_root), output_root=args.veritas_output_root
                )
            args.service_owner_pid = os.getpid()
            args.checkpoint_before = verify_veritas_checkpoint(
                args.veritas_output_root,
                args.release_verification,
                expected_campaign_sha256=(
                    args.ci_test_context["campaign_sha256"]
                    if args.ci_test_context
                    else VERITAS_CAMPAIGN_SHA256
                ),
            )
        if args.profile == "synthetic-validation":
            synthetic_expected_exit = _validate_synthetic_limits(args, command)
            requested_receipts = getattr(args, "receipt_dir", None)
            if (
                requested_receipts
                and Path(requested_receipts).resolve() != SYNTHETIC_RECEIPT_DIR.resolve()
            ):
                raise AdmissionError(
                    "synthetic receipts must remain in the dedicated validation directory"
                )
        receipt_dir = _prepare_receipt_directory(
            Path(
                getattr(args, "receipt_dir", None)
                or (
                    SYNTHETIC_RECEIPT_DIR
                    if args.profile == "synthetic-validation"
                    else GUARDED_RECEIPT_DIR
                )
            )
        )
        receipt, receipt_path, status_path = _new_execution_receipt(args, command, receipt_dir)
        if args.profile == "veritas":
            receipt["release_verification"] = args.release_verification
            receipt["checkpoint_before"] = args.checkpoint_before
            receipt["service_owner"] = {
                "unit": args.service_owner_unit,
                "invocation_id": args.service_owner_invocation_id,
                "pid": args.service_owner_pid,
            }
            if args.ci_test_context:
                receipt["validation_mode"] = "isolated_systemd_ci"
            _update_execution_receipt(receipt, receipt_path, phase="created")
        if args.profile == "synthetic-validation":
            receipt["expected_worker_exit_code"] = synthetic_expected_exit
            _update_execution_receipt(receipt, receipt_path, phase="created")
    except (AdmissionError, OSError) as error:
        if args.profile == "veritas" and "receipt_path" not in locals():
            try:
                args.source_revision = getattr(args, "source_revision", "")
                args.release_identity = getattr(args, "release_identity", "")
                args.label = getattr(args, "label", "veritas")
                if _current_veritas_service_unit() == VERITAS_CI_SERVICE_UNIT:
                    args.ci_test_context = {"validation_only": True}
                failed_receipt_dir = _prepare_receipt_directory(
                    Path(getattr(args, "receipt_dir", None) or GUARDED_RECEIPT_DIR)
                )
                failed_receipt, failed_path, _failed_status = _new_execution_receipt(
                    args, command, failed_receipt_dir
                )
                _finish_execution_receipt(
                    failed_receipt,
                    failed_path,
                    classification="preflight_denied",
                    exit_code=75,
                    detail=_safe_diagnostic(str(error)),
                )
                print(
                    json.dumps(
                        {
                            "invocation_id": failed_receipt["invocation_id"],
                            "receipt": str(failed_path),
                            "classification": "preflight_denied",
                            "exit_code": 75,
                        },
                        sort_keys=True,
                    ),
                    file=sys.stderr,
                )
            except (OSError, AdmissionError, KeyError, AttributeError):
                pass
        print(
            json.dumps({"decision": "DENY", "blocking_reasons": [str(error)[:512]]}),
            file=sys.stderr,
        )
        return 75

    unit = receipt["transient_unit"]["name"]
    unit_type = receipt["transient_unit"]["type"]
    process: subprocess.Popen[bytes] | None = None
    output: _RunnerOutput | None = None
    lock: Any = None
    outer_decision = "pending"
    runner_code: int | None = None
    runner_error: str | None = None
    watchdog_event: dict[str, Any] | None = None
    parent_signal: int | None = None
    final_classification = "result_missing_indeterminate"
    final_code = RUNNER_RESULT_MISSING
    systemd_wait_completed = False
    applied_limits_verified = False
    unit_cleanup_confirmed = False
    unit_after_wait: dict[str, str] | None = None
    latest_unit: dict[str, str] | None = None
    latest_inner: dict[str, Any] | None = None
    unit_active_after_client_exit = False
    previous_handlers: dict[int, Any] = {}
    last_persisted_unit: tuple[str | None, str | None, str | None] | None = None
    last_persisted_inner_phase: str | None = None
    last_metrics_write = 0.0

    def on_signal(signum: int, _frame: Any) -> None:
        raise GuardedExecutionInterrupted(signum)

    def observe_unit_and_inner(*, force: bool = False) -> None:
        nonlocal latest_unit, latest_inner, last_persisted_unit
        nonlocal last_persisted_inner_phase, last_metrics_write
        observed_unit_snapshot = _unit_snapshot(unit)
        if observed_unit_snapshot is not None:
            latest_unit = observed_unit_snapshot
        if latest_unit:
            receipt["transient_unit"]["invocation_id"] = latest_unit.get("InvocationID") or None
            receipt["transient_unit"]["last_observed_state"] = "/".join(
                value
                for value in (latest_unit.get("ActiveState"), latest_unit.get("SubState"))
                if value
            )
            unit_marker = (
                latest_unit.get("InvocationID"),
                latest_unit.get("ActiveState"),
                latest_unit.get("SubState"),
            )
            if unit_marker != last_persisted_unit:
                last_persisted_unit = unit_marker
                if latest_unit.get("InvocationID"):
                    receipt["log_references"]["journal_invocation"] = (
                        "journalctl --user _SYSTEMD_INVOCATION_ID=" + latest_unit["InvocationID"]
                    )
        latest_inner = _read_inner_status(status_path, receipt["invocation_id"])
        observed_inner = latest_inner
        observed_unit = observed_unit_snapshot or latest_unit
        inner_phase = observed_inner.get("phase") if observed_inner else None
        now_mono = time.monotonic()
        metrics_interval = 0.25 if args.profile == "synthetic-validation" else 10.0
        metrics_due = now_mono - last_metrics_write >= metrics_interval
        if force or (inner_phase and inner_phase != last_persisted_inner_phase) or metrics_due:
            if inner_phase and observed_inner:
                receipt["inner_status_record"] = observed_inner
                last_persisted_inner_phase = inner_phase
                receipt["inner_admission"] = {
                    "decision": observed_inner.get("decision", "pending"),
                    "phase": inner_phase,
                    "updated_at_utc": observed_inner.get("updated_at_utc"),
                    "evidence": observed_inner.get("admission_evidence"),
                }
                if inner_phase in {"worker_running", "worker_finished"}:
                    receipt["worker"]["start_confirmed"] = True
                    receipt["worker"]["start_observed_at_utc"] = observed_inner.get(
                        "worker_started_at_utc"
                    )
                for key in (
                    "worker_completed_at_utc",
                    "worker_runtime_seconds",
                    "worker_pid",
                ):
                    if key in observed_inner:
                        receipt["worker"][key] = observed_inner[key]
                if observed_inner.get("cgroup_metrics"):
                    receipt["cgroup_metrics"] = observed_inner["cgroup_metrics"]
                if observed_inner.get("watchdog_intervention"):
                    intervention = observed_inner["watchdog_intervention"]
                    if intervention not in receipt["watchdog_interventions"]:
                        receipt["watchdog_interventions"].append(intervention)
            if observed_unit:
                receipt["transient_unit"]["properties"] = observed_unit
                if observed_unit.get("InvocationID"):
                    receipt["log_references"]["journal_invocation"] = (
                        "journalctl --user _SYSTEMD_INVOCATION_ID=" + observed_unit["InvocationID"]
                    )
            if metrics_due and observed_unit is not None and _unit_is_active(observed_unit):
                cgroup = observed_unit.get("ControlGroup", "").strip("/")
                if cgroup:
                    receipt["cgroup_metrics"] = _cgroup_execution_metrics(
                        CGROUP_ROOT / cgroup,
                        allow_missing_io_weight=args.profile == "synthetic-validation",
                    )
                last_metrics_write = now_mono
            _update_execution_receipt(receipt, receipt_path, phase="unit_running")

    try:
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            previous_handlers[signum] = signal.signal(signum, on_signal)

        if args.memory_high_mib <= 0 or args.memory_max_mib <= args.memory_high_mib:
            raise AdmissionError("require 0 < --memory-high-mib < --memory-max-mib")
        if args.memory_budget_mib <= 0 or args.memory_budget_mib > args.memory_high_mib:
            raise AdmissionError(
                "--memory-budget-mib must be positive and no greater than MemoryHigh"
            )
        if args.timeout_seconds <= 0 or args.sample_seconds <= 0:
            raise AdmissionError("--timeout-seconds and --sample-seconds must be positive")
        if not 1 <= args.cpu_quota_percent <= 1000:
            raise AdmissionError("--cpu-quota-percent must be between 1 and 1000")
        if args.profile == "backup" and (
            args.memory_high_mib > 768
            or args.memory_max_mib > 1024
            or args.memory_budget_mib > 512
            or args.cpu_quota_percent > 20
        ):
            raise AdmissionError(
                "backup scope must stay within MemoryHigh=768 MiB, MemoryMax=1024 MiB, "
                "a 512 MiB task budget, and CPUQuota=20%"
            )
        if args.profile == "veritas" and (
            args.memory_high_mib > VERITAS_RUN_LIMITS["memory_high_mib"]
            or args.memory_max_mib != VERITAS_RUN_LIMITS["memory_max_mib"]
            or args.memory_budget_mib > VERITAS_RUN_LIMITS["memory_budget_mib"]
            or args.cpu_quota_percent > VERITAS_RUN_LIMITS["cpu_quota_percent"]
            or args.timeout_seconds > VERITAS_RUN_LIMITS["timeout_seconds"]
            or args.sample_seconds < 30
        ):
            raise AdmissionError(
                "Veritas service must stay within MemoryHigh=192 MiB, MemoryMax=256 MiB, "
                "a 128 MiB task budget, CPUQuota=100%, a 600-second timeout, and a "
                "30-second admission sample"
            )
        if args.profile == "veritas":
            _validate_veritas_runtime_context()
        _update_execution_receipt(receipt, receipt_path, phase="acquiring_lock")
        lock = _acquire_lock()
        _update_execution_receipt(receipt, receipt_path, phase="outer_admission_running")
        evidence, reasons = _gate(args, include_task_cgroup=False, lock_held=True)
        evidence["planned_cgroup"] = {
            "unit": unit,
            "unit_type": unit_type,
            "memory_high_bytes": args.memory_high_mib * MIB,
            "memory_max_bytes": args.memory_max_mib * MIB,
            "memory_swap_max_bytes": 0,
            "cpu_quota_percent": args.cpu_quota_percent,
            "io_weight": 10,
            "runtime_max_seconds": args.timeout_seconds,
            "timeout_seconds": args.timeout_seconds,
        }
        if args.profile == "synthetic-validation":
            evidence["planned_cgroup"].update(
                tasks_max=SYNTHETIC_RUN_LIMITS["tasks_max"],
                filesystem_sandbox="Landlock denies by default; system binaries read-only; invocation status writable",
                network_sandbox="RestrictAddressFamilies plus worker-only seccomp-bpf, verified before exec",
                io_weight_enforcement="requested 10; actual cgroup availability is recorded by the inner gate",
                synthetic_only=True,
            )
        if args.profile == "backup":
            evidence["planned_cgroup"]["task_io_scheduling"] = "idle"
            evidence["planned_cgroup"]["task_cpu_nice"] = 19
        elif args.profile == "veritas":
            evidence["planned_cgroup"].update(
                io_scheduling_class="idle",
                nice=19,
                filesystem_sandbox="strict; write access limited to Veritas output and this invocation status",
            )
        outer_decision = "DENY" if reasons else "ADMIT"
        receipt["outer_admission"] = {
            "decision": outer_decision,
            "evidence": _compact_evidence(evidence),
        }
        _update_execution_receipt(receipt, receipt_path, phase="outer_admission_complete")
        _print_evidence(_compact_evidence(evidence))
        if reasons:
            final_classification = "admission_denied"
            final_code = 75
            return_code = final_code
            _finish_execution_receipt(
                receipt,
                receipt_path,
                classification=final_classification,
                exit_code=return_code,
                detail="outer resource admission denied the invocation",
            )
            return final_code

        _write_inner_status(
            status_path, receipt["invocation_id"], phase="queued", decision="pending"
        )
        task_command = list(command)
        if args.profile == "backup":
            ionice = shutil.which("ionice")
            nice = shutil.which("nice")
            if ionice is None or nice is None:
                raise AdmissionError("backup jobs require ionice and nice for idle scheduling")
            task_command = [ionice, "-c", "3", nice, "-n", "19", *task_command]
        inner_command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "_inside",
            "--profile",
            args.profile,
            "--invocation-id",
            receipt["invocation_id"],
            "--status-path",
            str(status_path),
            "--memory-budget-mib",
            str(args.memory_budget_mib),
            *[part for path in args.storage_path for part in ("--storage-path", path)],
            "--storage-required-mib",
            str(args.storage_required_mib),
            "--storage-reserve-mib",
            str(args.storage_reserve_mib),
            "--sample-seconds",
            str(args.sample_seconds),
            "--execution-timeout-seconds",
            str(args.timeout_seconds),
            "--termination-grace-seconds",
            str(args.termination_grace_seconds),
            *(
                [
                    "--release-root",
                    str(args.release_root),
                    "--expected-module-sha256",
                    str(args.expected_module_sha256),
                    "--expected-checkpoint-state-sha256",
                    args.checkpoint_before["state_sha256"],
                    "--parent-service-invocation-id",
                    args.service_owner_invocation_id,
                    "--parent-service-unit",
                    args.service_owner_unit,
                    "--parent-service-pid",
                    str(args.service_owner_pid),
                ]
                if args.profile == "veritas"
                else []
            ),
            "--",
            *task_command,
        ]
        systemd_command = ["systemd-run", "--user"]
        if args.profile in {"veritas", "synthetic-validation"}:
            systemd_command.extend(
                [
                    f"--unit={unit}",
                    "--service-type=exec",
                    "--wait",
                    "--expand-environment=no",
                ]
            )
            if args.profile in {"veritas", "synthetic-validation"}:
                systemd_command.append("--collect")
        else:
            systemd_command.extend(
                ["--scope", "--collect", "--expand-environment=no", f"--unit={unit}"]
            )
        tasks_max = (
            SYNTHETIC_RUN_LIMITS["tasks_max"] if args.profile == "synthetic-validation" else 256
        )
        systemd_command.extend(
            [
                f"--property=MemoryHigh={args.memory_high_mib}M",
                f"--property=MemoryMax={args.memory_max_mib}M",
                "--property=MemorySwapMax=0",
                f"--property=CPUQuota={args.cpu_quota_percent}%",
                "--property=IOWeight=10",
                f"--property=TasksMax={tasks_max}",
            ]
        )
        if args.profile == "veritas":
            release_packages = Path(args.release_root) / "packages"
            systemd_command.extend(
                [
                    "--property=Nice=19",
                    "--property=IOSchedulingClass=idle",
                    "--property=ProtectSystem=strict",
                    "--property=ProtectHome=read-only",
                    f"--property=ReadWritePaths={args.veritas_output_root} {status_path.parent}",
                    "--property=PrivateTmp=yes",
                    "--property=NoNewPrivileges=yes",
                    "--property=UMask=0077",
                    f"--property=WorkingDirectory={VERITAS_SERVICE_ROOT}",
                    f"--property=TimeoutStartSec={args.timeout_seconds}s",
                    f"--property=RuntimeMaxSec={args.timeout_seconds}s",
                    "--property=KillMode=control-group",
                    "--property=Restart=no",
                    "--property=StandardOutput=journal",
                    "--property=StandardError=journal",
                    f"--setenv=PYTHONPATH={release_packages}:{VERITAS_RUNTIME_SITE_PACKAGES}",
                    f"--setenv=HOME={Path.home()}",
                    f"--setenv=XDG_STATE_HOME={Path.home() / '.local' / 'state'}",
                    "--setenv=OMP_NUM_THREADS=1",
                    "--setenv=OPENBLAS_NUM_THREADS=1",
                    "--setenv=MKL_NUM_THREADS=1",
                ]
            )
            if args.profile == "veritas" and args.ci_test_context:
                systemd_command.append("--property=RestrictAddressFamilies=AF_UNIX")
                for key, value in _veritas_ci_worker_environment(args.ci_test_context).items():
                    systemd_command.append(f"--setenv={key}={value}")
        elif args.profile == "synthetic-validation":
            systemd_command.extend(
                [
                    "--property=Nice=19",
                    "--property=IOSchedulingClass=idle",
                    "--property=NoNewPrivileges=yes",
                    "--property=RestrictAddressFamilies=AF_UNIX",
                    "--property=SystemCallArchitectures=native",
                    "--property=UMask=0077",
                    "--property=WorkingDirectory=/",
                    f"--property=TimeoutStartSec={SYNTHETIC_RUN_LIMITS['timeout_seconds']}s",
                    f"--property=RuntimeMaxSec={SYNTHETIC_RUN_LIMITS['timeout_seconds']}s",
                    "--property=KillMode=control-group",
                    "--property=Restart=no",
                    "--property=StandardOutput=journal",
                    "--property=StandardError=journal",
                ]
            )
        systemd_command.extend(["--", *inner_command])
        receipt["requested_systemd_properties"] = {
            "MemoryHigh": f"{args.memory_high_mib}M",
            "MemoryMax": f"{args.memory_max_mib}M",
            "MemorySwapMax": "0",
            "CPUQuota": f"{args.cpu_quota_percent}%",
            "IOWeight": "10",
            "RestrictAddressFamilies": (
                ["AF_UNIX"] if args.profile == "veritas" and args.ci_test_context else None
            ),
            "RuntimeMaxSec": (
                f"{args.timeout_seconds}s"
                if args.profile == "veritas"
                else (
                    f"{SYNTHETIC_RUN_LIMITS['timeout_seconds']}s"
                    if args.profile == "synthetic-validation"
                    else None
                )
            ),
            "Collect": args.profile in {"veritas", "synthetic-validation"},
            "KillMode": "control-group" if args.profile == "veritas" else None,
            "PrivateTmp": "yes" if args.profile == "veritas" else None,
            "ProtectSystem": "strict" if args.profile == "veritas" else None,
            "ProtectHome": "read-only" if args.profile == "veritas" else None,
            "Restart": "no" if args.profile == "veritas" else None,
            "StandardOutput": "journal" if args.profile == "veritas" else None,
            "StandardError": "journal" if args.profile == "veritas" else None,
            "ReadWritePaths": (
                [str(args.veritas_output_root), str(status_path.parent)]
                if args.profile == "veritas"
                else None
            ),
            "TasksMax": 256 if args.profile == "veritas" else None,
            "Nice": 19 if args.profile == "veritas" else None,
            "IOSchedulingClass": "idle" if args.profile == "veritas" else None,
            "TimeoutStartSec": f"{args.timeout_seconds}s" if args.profile == "veritas" else None,
            "UnsetEnvironment": "not used in transient unit; PYTHONPATH is explicitly pinned"
            if args.profile == "veritas"
            else None,
            "PYTHONPATH": (
                f"{Path(args.release_root) / 'packages'}:{VERITAS_RUNTIME_SITE_PACKAGES}"
            )
            if args.profile == "veritas"
            else None,
        }
        if args.profile == "synthetic-validation":
            receipt["requested_systemd_properties"].update(
                {
                    "TasksMax": str(tasks_max),
                    "NoNewPrivileges": "yes",
                    "RestrictAddressFamilies": ["AF_UNIX"],
                    "SystemCallArchitectures": "native",
                    "WorkerNetworkFilter": "seccomp-bpf denies socket and network syscalls before exec",
                    "CgroupIOWeight": (
                        "requested 10; enforcement is reported separately because the user manager "
                        "may not delegate the io controller"
                    ),
                    "KillMode": "control-group",
                    "Restart": "no",
                    "TimeoutStartSec": f"{SYNTHETIC_RUN_LIMITS['timeout_seconds']}s",
                    "StandardOutput": "journal",
                    "StandardError": "journal",
                    "FilesystemIsolation": "Landlock deny-by-default; /usr and loader metadata read-only; only invocation status directory writable",
                }
            )
        _update_execution_receipt(receipt, receipt_path, phase="unit_launch_requested")
        try:
            process = subprocess.Popen(
                systemd_command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                start_new_session=True,
            )
        except OSError as error:
            runner_error = f"{type(error).__name__}: {error}"
            final_classification = "unit_creation_failed"
            final_code = 70
            persisted = _try_finish_execution_receipt(
                receipt,
                receipt_path,
                classification=final_classification,
                exit_code=final_code,
                detail=_safe_diagnostic(runner_error),
            )
            return final_code if persisted else RUNNER_RESULT_MISSING
        output = _RunnerOutput(process, systemd_command)
        _update_execution_receipt(receipt, receipt_path, phase="systemd_run_client_started")

        def on_watchdog(event: dict[str, Any]) -> None:
            nonlocal watchdog_event
            watchdog_event = event
            receipt["watchdog_interventions"].append(event)
            _update_execution_receipt(
                receipt, receipt_path, phase="watchdog_cancellation_requested"
            )

        def on_cancellation(result: dict[str, Any]) -> None:
            receipt["cancellation_results"].append(result)
            _update_execution_receipt(receipt, receipt_path, phase="cancellation_observed")

        if args.profile == "veritas":
            runner_code = _wait_for_veritas_process(
                process,
                unit,
                timeout_seconds=args.timeout_seconds,
                termination_grace_seconds=args.termination_grace_seconds,
                output=output,
                on_poll=observe_unit_and_inner,
                on_watchdog=on_watchdog,
                on_cancel=on_cancellation,
            )
        else:
            runner_code = _wait_for_runner_process(
                process,
                unit,
                timeout_seconds=args.timeout_seconds,
                termination_grace_seconds=args.termination_grace_seconds,
                output=output,
                on_timeout=on_watchdog,
                on_cancel=on_cancellation,
                on_poll=observe_unit_and_inner,
            )
        systemd_wait_completed = process.poll() is not None and watchdog_event is None
        runner_output = output.summary()
        receipt["systemd_run_client"] = {
            "exit_code": runner_code,
            "wait_completed": systemd_wait_completed,
            "output": runner_output,
        }
        observe_unit_and_inner(force=True)
        unit_after_wait = (
            _unit_snapshot_after_wait(unit)
            if args.profile in {"veritas", "synthetic-validation"}
            else latest_unit
        )
        if unit_after_wait and unit_after_wait.get("LoadState") not in {None, "not-found"}:
            latest_unit = unit_after_wait
        unit_active_after_client_exit = _unit_is_active(unit_after_wait or latest_unit)
        if unit_active_after_client_exit:
            _update_execution_receipt(
                receipt,
                receipt_path,
                phase="runner_exited_while_unit_active",
                transient_unit={
                    **receipt["transient_unit"],
                    "last_observed_state": "active_after_runner_exit",
                },
            )
            cancellation = _kill_unit(unit, args.termination_grace_seconds)
            if not isinstance(cancellation, dict):
                cancellation = {"unit": unit, "cancellation_status": "not_returned"}
            cancellation["reason"] = "runner_exited_while_unit_active"
            receipt["cancellation_results"].append(cancellation)
            _update_execution_receipt(receipt, receipt_path, phase="unit_cancellation_requested")
            latest_unit = _unit_snapshot(unit)
            observe_unit_and_inner(force=True)
            unit_active_after_client_exit = _unit_is_active(latest_unit)
            if args.profile in {"veritas", "synthetic-validation"}:
                unit_after_wait = _unit_snapshot_after_wait(unit)
                unit_active_after_client_exit = _unit_is_active(unit_after_wait or latest_unit)
        inner_status = _read_inner_status(status_path, receipt["invocation_id"])
        if inner_status:
            receipt["artifacts"]["inner_status_collected"] = True
            receipt["inner_status_record"] = inner_status
            receipt["inner_admission"] = {
                "decision": inner_status.get("decision", "pending"),
                "phase": inner_status.get("phase"),
                "updated_at_utc": inner_status.get("updated_at_utc"),
                "evidence": inner_status.get("admission_evidence"),
            }
            if inner_status.get("cgroup_metrics"):
                receipt["cgroup_metrics"] = inner_status["cgroup_metrics"]
            if inner_status.get("worker_exit_code") is not None:
                receipt["result"]["worker_exit_code"] = inner_status["worker_exit_code"]
            if inner_status.get("worker_signal") is not None:
                receipt["result"]["termination_signal"] = inner_status["worker_signal"]
            if inner_status.get("watchdog_intervention") and not watchdog_event:
                receipt["watchdog_interventions"].append(inner_status["watchdog_intervention"])
            if args.profile != "veritas" and inner_status.get("phase") == "worker_exec_requested":
                if args.profile == "synthetic-validation":
                    receipt["worker"]["start_confirmed"] = (
                        systemd_wait_completed
                        and runner_code == synthetic_expected_exit
                        and bool(latest_unit and latest_unit.get("InvocationID"))
                        and bool(
                            latest_unit
                            and latest_unit.get("ExecMainStartTimestamp") not in {None, "", "n/a"}
                        )
                    )
                else:
                    receipt["worker"]["start_confirmed"] = runner_code not in {None, 127}
                receipt["worker"]["start_observed_at_utc"] = inner_status.get(
                    "worker_start_requested_at_utc"
                )
                receipt["worker"]["completed_at_utc"] = _utc_now()
                started_monotonic = inner_status.get("worker_start_requested_monotonic")
                if isinstance(started_monotonic, (int, float)) and math.isfinite(started_monotonic):
                    receipt["worker"]["runtime_seconds"] = round(
                        max(0.0, time.monotonic() - started_monotonic), 3
                    )
                if runner_code is not None and runner_code >= 0:
                    receipt["result"]["worker_exit_code"] = runner_code
                elif runner_code is not None:
                    receipt["result"]["termination_signal"] = -runner_code
        elif args.profile == "veritas":
            receipt["inner_admission"] = {"decision": "missing", "phase": "missing"}
        if latest_unit:
            receipt["transient_unit"]["properties"] = latest_unit
            receipt["transient_unit"]["invocation_id"] = latest_unit.get("InvocationID") or None
        if args.profile in {"veritas", "synthetic-validation"}:
            receipt["transient_unit"]["properties_after_wait"] = unit_after_wait or {}
            cleanup = _wait_for_transient_unit_cleanup(unit)
            receipt["transient_unit"]["cleanup"] = cleanup
            unit_cleanup_confirmed = (
                cleanup.get("confirmed") is True and cleanup.get("unit_absent") is True
            )
            if unit_cleanup_confirmed:
                receipt["transient_unit"]["last_observed_state"] = "collected"
            context = (
                inner_status.get("synthetic_context")
                if args.profile == "synthetic-validation" and inner_status
                else inner_status.get("execution_context")
                if inner_status
                else None
            )
            if isinstance(context, dict):
                if args.profile == "synthetic-validation":
                    context_metrics = context.get("cgroup_metrics")
                    if isinstance(context_metrics, dict) and context_metrics.get("available"):
                        receipt["cgroup_metrics"] = context_metrics
                    context_properties = context.get("unit_properties")
                    inner_filesystem = (
                        inner_status.get("filesystem_isolation") if inner_status else None
                    )
                    applied_limits_verified = (
                        isinstance(context_properties, dict)
                        and isinstance(context_metrics, dict)
                        and context_metrics.get("available") is True
                        and context.get("unit") == unit
                        and isinstance(context.get("network_isolation"), dict)
                        and context["network_isolation"].get("restricted") is True
                        and context["network_isolation"].get("mechanism") == "seccomp-bpf"
                        and isinstance(inner_filesystem, dict)
                        and inner_filesystem.get("enforced") is True
                    )
                else:
                    transient_context = context.get("transient_unit")
                    if isinstance(transient_context, dict) and transient_context.get("available"):
                        receipt["cgroup_metrics"] = transient_context
                    applied_limits_verified = bool(
                        isinstance(transient_context, dict)
                        and transient_context.get("limits_verified") is True
                        and context.get("release", {}).get("passed") is True
                    )
            receipt["applied_limits_verification"] = {
                "passed": applied_limits_verified,
                "source": (
                    "systemd properties and effective cgroup memory, swap, CPU, PID, and I/O "
                    "controls; the complete worker filesystem sandbox is separately verified"
                    if args.profile == "veritas"
                    else "systemd properties, cgroup memory/CPU/PID controls, worker seccomp-bpf, "
                    "and Landlock; cgroup I/O controller availability is reported separately"
                ),
            }
        final_classification = _classify_guarded_result(
            profile=args.profile,
            return_code=runner_code,
            unit=latest_unit,
            inner=inner_status,
            watchdog=watchdog_event,
            parent_signal=None,
            runner_error=runner_error,
            unit_was_active_after_client_exit=unit_active_after_client_exit,
            systemd_wait_completed=systemd_wait_completed,
            synthetic_expected_exit=synthetic_expected_exit,
            applied_limits_verified=applied_limits_verified,
            unit_cleanup_confirmed=unit_cleanup_confirmed,
            unit_after_wait=unit_after_wait,
        )
        post_execution_error: str | None = None
        if final_classification == "worker_succeeded" and args.profile == "veritas":
            try:
                post_execution = verify_veritas_post_execution_state(
                    args.veritas_output_root,
                    args.release_verification,
                    args.checkpoint_before,
                    expected_campaign_sha256=(
                        args.ci_test_context["campaign_sha256"]
                        if args.ci_test_context
                        else VERITAS_CAMPAIGN_SHA256
                    ),
                )
                receipt["post_execution_verification"] = {
                    "passed": True,
                    "checkpoint_after": post_execution,
                }
            except (AdmissionError, OSError) as error:
                post_execution_error = _safe_diagnostic(f"{type(error).__name__}: {error}")
                receipt["post_execution_verification"] = {
                    "passed": False,
                    "detail": post_execution_error,
                }
                final_classification = "post_execution_state_invalid"
        if final_classification == "worker_succeeded":
            final_code = 0
        elif final_classification == "post_execution_state_invalid":
            final_code = RUNNER_RESULT_MISSING
        elif (
            inner_status
            and isinstance(inner_status.get("worker_exit_code"), int)
            and inner_status["worker_exit_code"] != 0
        ):
            worker_exit_code = inner_status["worker_exit_code"]
            final_code = worker_exit_code if worker_exit_code >= 0 else 128 + -worker_exit_code
        elif runner_code not in {None, 0}:
            final_code = runner_code
        elif final_classification == "admission_denied":
            final_code = 75
        else:
            final_code = RUNNER_RESULT_MISSING
        receipt["result"]["runner_exit_code"] = runner_code
        persisted = _try_finish_execution_receipt(
            receipt,
            receipt_path,
            classification=final_classification,
            exit_code=final_code,
            termination_signal=receipt["result"].get("termination_signal"),
            detail=post_execution_error or runner_output.get("stderr", {}).get("diagnostic_type"),
        )
        if not persisted:
            final_classification = "result_missing_indeterminate"
            final_code = RUNNER_RESULT_MISSING
        if (
            persisted
            and args.profile == "veritas"
            and latest_unit
            and latest_unit.get("ActiveState")
            not in {
                "active",
                "activating",
                "reloading",
            }
        ):
            _systemctl("reset-failed", unit, check=False)
        if not persisted:
            print(
                json.dumps(
                    {
                        "invocation_id": receipt["invocation_id"],
                        "receipt": str(receipt_path),
                        "classification": "result_missing_indeterminate",
                        "reason": "final_execution_receipt_not_durable",
                        "unit": unit,
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return final_code
        print(
            json.dumps(
                {
                    "invocation_id": receipt["invocation_id"],
                    "receipt": str(receipt_path),
                    "classification": final_classification,
                    "exit_code": final_code,
                    "unit": unit,
                },
                sort_keys=True,
            ),
            file=sys.stdout,
        )
        return final_code
    except GuardedExecutionInterrupted as error:
        parent_signal = int(error.signum)
        if process is not None:
            cancellation = _cancel_bounded_unit(process, unit, args.termination_grace_seconds)
            receipt["cancellation_results"].append(cancellation)
        latest_unit = _unit_snapshot(unit)
        latest_inner = _read_inner_status(status_path, receipt["invocation_id"])
        receipt["transient_unit"]["properties"] = latest_unit or {}
        receipt["transient_unit"]["invocation_id"] = (
            latest_unit.get("InvocationID") if latest_unit else None
        )
        if latest_unit and latest_unit.get("InvocationID"):
            receipt["log_references"]["journal_invocation"] = (
                "journalctl --user _SYSTEMD_INVOCATION_ID=" + latest_unit["InvocationID"]
            )
        if latest_inner:
            receipt["inner_status_record"] = latest_inner
            receipt["inner_admission"] = {
                "decision": latest_inner.get("decision", "pending"),
                "phase": latest_inner.get("phase"),
                "evidence": latest_inner.get("admission_evidence"),
            }
        final_code = 128 + parent_signal
        final_classification = (
            "cancelled_by_parent_signal"
            if process is None
            else _classify_guarded_result(
                profile=args.profile,
                return_code=process.poll(),
                unit=latest_unit,
                inner=latest_inner,
                watchdog=None,
                parent_signal=parent_signal,
                runner_error=None,
                unit_was_active_after_client_exit=_unit_is_active(latest_unit),
            )
        )
        if final_classification == "result_missing_indeterminate":
            final_code = RUNNER_RESULT_MISSING
        persisted = _try_finish_execution_receipt(
            receipt,
            receipt_path,
            classification=final_classification,
            exit_code=final_code,
            termination_signal=parent_signal,
            detail=str(error),
        )
        if not persisted:
            print(
                json.dumps(
                    {
                        "invocation_id": receipt["invocation_id"],
                        "receipt": str(receipt_path),
                        "classification": "result_missing_indeterminate",
                        "reason": "final_execution_receipt_not_durable",
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return RUNNER_RESULT_MISSING
        return final_code
    except AdmissionError as error:
        runner_error = str(error)
        if process is not None:
            latest_unit = _unit_snapshot(unit)
            if _unit_is_active(latest_unit) or process.poll() is None:
                cancellation = _cancel_bounded_unit(process, unit, args.termination_grace_seconds)
                cancellation["reason"] = "admission_error_after_runner_start"
                receipt["cancellation_results"].append(cancellation)
            latest_inner = _read_inner_status(status_path, receipt["invocation_id"])
            if latest_inner:
                receipt["inner_status_record"] = latest_inner
        if process is not None:
            classification = "result_missing_indeterminate"
            failure_code = RUNNER_RESULT_MISSING
        elif outer_decision == "DENY":
            classification = "admission_denied"
            failure_code = 75
        elif outer_decision == "ADMIT":
            classification = "execution_setup_failed"
            failure_code = 70
        elif receipt.get("phase") == "outer_admission_running":
            classification = "admission_check_failed"
            failure_code = 75
        else:
            classification = "admission_denied"
            failure_code = 75
        persisted = _try_finish_execution_receipt(
            receipt,
            receipt_path,
            classification=classification,
            exit_code=failure_code,
            detail=_safe_diagnostic(runner_error),
        )
        return failure_code if persisted else RUNNER_RESULT_MISSING
    except Exception as error:
        runner_error = f"{type(error).__name__}: {error}"
        if process is not None:
            latest_unit = _unit_snapshot(unit)
            if _unit_is_active(latest_unit) or process.poll() is None:
                cancellation = _cancel_bounded_unit(process, unit, args.termination_grace_seconds)
                cancellation["reason"] = "runner_observation_error"
                receipt["cancellation_results"].append(cancellation)
            latest_inner = _read_inner_status(status_path, receipt["invocation_id"])
            if latest_inner:
                receipt["inner_status_record"] = latest_inner
        if process is not None:
            classification = "result_missing_indeterminate"
            final_code = RUNNER_RESULT_MISSING
        elif outer_decision == "pending" and receipt.get("phase") == "outer_admission_running":
            classification = "admission_check_failed"
            final_code = 75
        elif outer_decision == "pending":
            classification = "execution_setup_failed"
            final_code = 70
        elif outer_decision == "DENY":
            classification = "admission_denied"
            final_code = 75
        else:
            classification = "execution_setup_failed"
            final_code = 70
        persisted = _try_finish_execution_receipt(
            receipt,
            receipt_path,
            classification=classification,
            exit_code=final_code,
            termination_signal=parent_signal,
            detail=_safe_diagnostic(runner_error),
        )
        if not persisted:
            classification = "result_missing_indeterminate"
            final_code = RUNNER_RESULT_MISSING
        print(
            json.dumps(
                {
                    "decision": "INDETERMINATE" if process is not None or not persisted else "DENY",
                    "invocation_id": receipt["invocation_id"],
                    "receipt": str(receipt_path),
                    "reason": _safe_diagnostic(runner_error),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return final_code
    finally:
        for restore_signum, handler in previous_handlers.items():
            signal.signal(restore_signum, handler)
        if output is not None:
            output.close()
        if process is not None and process.poll() is None:
            cancellation = _cancel_bounded_unit(process, unit, args.termination_grace_seconds)
            receipt["cancellation_results"].append(cancellation)
            if receipt.get("final_classification") == "indeterminate":
                try:
                    _update_execution_receipt(
                        receipt, receipt_path, phase="final_cleanup_cancellation"
                    )
                except (OSError, AdmissionError):
                    pass
        if lock is not None:
            lock.close()


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return number


def _common_options(parser: argparse.ArgumentParser, *, defaults: bool = True) -> None:
    parser.add_argument("--profile", choices=sorted(PROFILES), default="heavy")
    parser.add_argument(
        "--memory-budget-mib", type=_positive_int, default=512 if defaults else None
    )
    parser.add_argument("--storage-path", action="append", required=True)
    parser.add_argument("--storage-required-mib", type=_positive_int, default=0)
    parser.add_argument(
        "--storage-reserve-mib", type=_positive_int, default=5120 if defaults else None
    )
    parser.add_argument("--sample-seconds", type=float, default=2.0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="action", required=True)
    check = subs.add_parser("check", help="check admission inside an already bounded cgroup")
    _common_options(check)

    run = subs.add_parser("run", help="admit and run one command in a bounded systemd scope")
    _common_options(run)
    run.add_argument("--label", default="task", help="short safe label for the transient scope")
    run.add_argument("--memory-high-mib", type=_positive_int, required=True)
    run.add_argument("--memory-max-mib", type=_positive_int, required=True)
    run.add_argument("--cpu-quota-percent", type=_positive_int, default=50)
    run.add_argument("--timeout-seconds", type=float, required=True)
    run.add_argument("--termination-grace-seconds", type=float, default=2.0)
    run.add_argument("--receipt-dir")
    run.add_argument("--source-revision", default="")
    run.add_argument("--release-identity", default="")
    run.add_argument("--release-root")
    run.add_argument("--expected-module-sha256")
    run.add_argument("command", nargs=argparse.REMAINDER)

    inside = subs.add_parser("_inside", help=argparse.SUPPRESS)
    _common_options(inside)
    inside.add_argument("--invocation-id", required=True)
    inside.add_argument("--status-path", required=True)
    inside.add_argument("--execution-timeout-seconds", type=float, default=600)
    inside.add_argument("--termination-grace-seconds", type=float, default=2)
    inside.add_argument("--release-root")
    inside.add_argument("--expected-module-sha256")
    inside.add_argument("--expected-checkpoint-state-sha256")
    inside.add_argument("--parent-service-invocation-id")
    inside.add_argument("--parent-service-unit")
    inside.add_argument("--parent-service-pid", type=_positive_int)
    inside.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.action == "run":
            label = re.sub(r"[^a-zA-Z0-9_-]+", "-", args.label).strip("-")[:32]
            if not label:
                raise AdmissionError("--label must contain a letter or number")
            args.label = label
            return _run_command(args)
        if args.action == "check":
            if args.profile == "synthetic-validation":
                raise AdmissionError(
                    "synthetic-validation is available only through the guarded run command"
                )
            evidence, reasons = _gate(args, include_task_cgroup=True, lock_held=False)
            _print_evidence(evidence, sys.stdout)
            return 0 if not reasons else 75
        if args.action == "_inside":
            command = args.command[1:] if args.command and args.command[0] == "--" else args.command
            return _run_inside(args, command)
        raise AdmissionError(f"unsupported action: {args.action}")
    except AdmissionError as error:
        if args.action == "_inside" and getattr(args, "status_path", None):
            try:
                _write_inner_status(
                    Path(args.status_path),
                    args.invocation_id,
                    phase="inner_gate_failed",
                    decision="DENY",
                    detail=_safe_diagnostic(str(error)),
                )
            except (OSError, AdmissionError):
                pass
        print(
            json.dumps({"decision": "DENY", "blocking_reasons": [str(error)]}, indent=2),
            file=sys.stderr,
        )
        return 75
    except (OSError, ValueError, KeyError) as error:
        print(
            json.dumps({"decision": "DENY", "blocking_reasons": [str(error)]}, indent=2),
            file=sys.stderr,
        )
        return 75
    return 70


if __name__ == "__main__":
    raise SystemExit(main())
