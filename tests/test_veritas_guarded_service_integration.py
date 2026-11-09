from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import scripts.midas_resource_preflight as preflight

sys.path.insert(0, str(Path(__file__).parents[1] / "packages"))
from scripts import veritas_source_analysis as source_analysis  # noqa: E402


@pytest.mark.parametrize("active_state", ["active", "activating"])
def test_ci_worker_accepts_current_oneshot_parent_state(
    monkeypatch: pytest.MonkeyPatch, active_state: str
) -> None:
    invocation_id = "a" * 32
    stdout = f"{active_state}\n{invocation_id}\n"
    monkeypatch.setattr(
        source_analysis.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, stdout, ""),
    )

    source_analysis._verify_ci_parent_service_identity(
        "midas-veritas-source-analysis-ci.service", invocation_id
    )


@pytest.mark.parametrize(
    ("returncode", "stdout"),
    [
        (0, "inactive\n" + "a" * 32 + "\n"),
        (0, "activating\n" + "b" * 32 + "\n"),
        (1, "activating\n" + "a" * 32 + "\n"),
        (0, "activating\n"),
    ],
)
def test_ci_worker_rejects_stale_or_unverified_parent_identity(
    monkeypatch: pytest.MonkeyPatch, returncode: int, stdout: str
) -> None:
    invocation_id = "a" * 32
    monkeypatch.setattr(
        source_analysis.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, returncode, stdout, ""),
    )

    with pytest.raises(SystemExit, match="parent service identity could not be verified"):
        source_analysis._verify_ci_parent_service_identity(
            "midas-veritas-source-analysis-ci.service", invocation_id
        )


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _release_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, dict[str, str]]:
    root = tmp_path / "release"
    values = {
        "packages/midas/__init__.py": b"# package\n",
        "packages/midas/reality/__init__.py": b"# reality package\n",
        "packages/midas/veritas/__init__.py": b"# veritas package\n",
        "packages/midas/veritas/finalized_source_analysis.py": b"# approved analysis\n",
        "packages/midas/veritas/economics.py": b"# economics\n",
        "packages/midas/arbitrage/__init__.py": b"# arbitrage package\n",
        "packages/midas/arbitrage/engine.py": b"# engine\n",
        "packages/midas/core/__init__.py": b"# core package\n",
        "packages/midas/core/models.py": b"# core models\n",
        "packages/midas/economics/__init__.py": b"# economics package\n",
        "packages/midas/economics/attestation.py": b"# attestation\n",
        "packages/midas/economics/fees.py": b"# fee helpers\n",
        "packages/midas/reality/execution_research.py": b"# execution\n",
        "packages/midas/reality/foundry.py": b"# foundry\n",
        "packages/midas/reality/model_features.py": b"# model features\n",
        "packages/midas/reality/model_fitting.py": b"# model fitting\n",
        "packages/midas/reality/model_metrics.py": b"# model metrics\n",
        "packages/midas/reality/model_registry.py": b"# model registry\n",
        "packages/midas/reality/reconstruction.py": b"# reconstruction\n",
        "packages/midas/reality/research_measurements.py": b"# measurements\n",
        "packages/midas/reality/research_schema.py": b"# schema\n",
        "packages/midas/reality/shadow_campaign.py": b"# campaign\n",
        "packages/midas/reality/shadow_policy.py": b"# policy\n",
        "packages/midas/reality/shadow_source.py": b"# source\n",
        "packages/midas/reality/shadow_store.py": b"# shadow store\n",
        "packages/midas/reality/shadow_worker.py": b"# worker\n",
        "packages/midas/reality/storage.py": b"# storage\n",
        "packages/midas/risk/engine.py": b"# risk engine provenance\n",
        "scripts/veritas_source_analysis.py": b"# fixed worker wrapper\n",
        "bin/midas_resource_preflight.py": b"# fixed guarded launcher\n",
        "rollback/previous-finalized_source_analysis.py": b"# previous module\n",
        "rollback/midas-veritas-source-analysis.service": b"# previous service\n",
        "rollback/20-frozen-campaign-import.conf": b"# previous overlay pin\n",
    }
    release_id = "test-veritas-release-v1"
    source_revision = "1" * 40
    campaign_sha = _sha(b"test campaign")
    rollback_sha = _sha(b"old production module")
    runtime = {
        "finalized_source_analysis.py": _sha(
            values["packages/midas/veritas/finalized_source_analysis.py"]
        ),
        "scripts/veritas_source_analysis.py": _sha(values["scripts/veritas_source_analysis.py"]),
        "economics.py": _sha(values["packages/midas/veritas/economics.py"]),
        **{
            f"reality/{name}": _sha(values[f"packages/midas/reality/{name}"])
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
    module_sha = runtime["finalized_source_analysis.py"]
    wrapper_sha = runtime["scripts/veritas_source_analysis.py"]
    package_init_files = {
        name: _sha(values[name])
        for name in (
            "packages/midas/__init__.py",
            "packages/midas/reality/__init__.py",
            "packages/midas/veritas/__init__.py",
        )
    }
    release_dependency_files = {
        name: _sha(values[name]) for name in preflight.VERITAS_APPROVED_RELEASE_DEPENDENCY_FILES
    }
    service_text = Path("deploy/systemd/user/midas-veritas-source-analysis.service").read_text(
        encoding="utf-8"
    )
    service_text = service_text.replace(preflight.VERITAS_RELEASE_ID, release_id)
    service_text = service_text.replace(preflight.VERITAS_APPROVED_SOURCE_REVISION, source_revision)
    service_text = service_text.replace(preflight.VERITAS_APPROVED_MODULE_SHA256, module_sha)
    rollback_artifacts = {
        "rollback/previous-finalized_source_analysis.py": _sha(
            values["rollback/previous-finalized_source_analysis.py"]
        ),
        "rollback/midas-veritas-source-analysis.service": _sha(
            values["rollback/midas-veritas-source-analysis.service"]
        ),
        "rollback/20-frozen-campaign-import.conf": _sha(
            values["rollback/20-frozen-campaign-import.conf"]
        ),
    }
    monkeypatch.setattr(
        preflight,
        "VERITAS_RELEASE_ROOT",
        Path.home() / ".local" / "share" / "midas-veritas" / "releases" / release_id,
    )
    monkeypatch.setattr(preflight, "VERITAS_RELEASE_ID", release_id)
    monkeypatch.setattr(preflight, "VERITAS_APPROVED_SOURCE_REVISION", source_revision)
    monkeypatch.setattr(preflight, "VERITAS_APPROVED_MODULE_SHA256", module_sha)
    monkeypatch.setattr(preflight, "VERITAS_APPROVED_WRAPPER_SHA256", wrapper_sha)
    rollback_sha = rollback_artifacts["rollback/previous-finalized_source_analysis.py"]
    monkeypatch.setattr(preflight, "VERITAS_PRODUCTION_MODULE_SHA256", rollback_sha)
    monkeypatch.setattr(
        preflight,
        "VERITAS_PRODUCTION_SERVICE_SHA256",
        rollback_artifacts["rollback/midas-veritas-source-analysis.service"],
    )
    monkeypatch.setattr(
        preflight,
        "VERITAS_PRODUCTION_IMPORT_DROPIN_SHA256",
        rollback_artifacts["rollback/20-frozen-campaign-import.conf"],
    )
    monkeypatch.setattr(preflight, "VERITAS_CAMPAIGN_SHA256", campaign_sha)
    monkeypatch.setattr(preflight, "VERITAS_APPROVED_RUNTIME_CODE_FILES", runtime)
    monkeypatch.setattr(preflight, "VERITAS_APPROVED_PACKAGE_INIT_FILES", package_init_files)
    monkeypatch.setattr(
        preflight, "VERITAS_APPROVED_RELEASE_DEPENDENCY_FILES", release_dependency_files
    )
    runtime_sha = _sha(preflight._canonical_json(runtime))
    monkeypatch.setattr(preflight, "VERITAS_RUNTIME_ANALYSIS_CODE_SHA256", runtime_sha)
    test_python_runtime = {
        **preflight.VERITAS_APPROVED_PYTHON_RUNTIME,
        "validated_patch_version": (
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        ),
    }
    monkeypatch.setattr(preflight, "VERITAS_APPROVED_PYTHON_RUNTIME", test_python_runtime)

    for relative, data in values.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    service = root / "service" / "midas-veritas-source-analysis.service"
    service.parent.mkdir(parents=True)
    service.write_text(service_text, encoding="utf-8")
    values["service/midas-veritas-source-analysis.service"] = service.read_bytes()
    files = {relative: _sha(data) for relative, data in values.items()}
    manifest = {
        "format": "midas-veritas-guarded-release",
        "format_version": 1,
        "release_identity": release_id,
        "source_revision": source_revision,
        "launcher_source_revision": "2" * 40,
        "release_source_revision": "2" * 40,
        "candidate_module_sha256": module_sha,
        "wrapper_sha256": wrapper_sha,
        "rollback_module_sha256": rollback_sha,
        "rollback_artifacts_sha256": rollback_artifacts,
        "campaign_sha256": campaign_sha,
        "runtime_analysis_code_files": runtime,
        "runtime_analysis_code_sha256": runtime_sha,
        "package_init_files_sha256": package_init_files,
        "release_dependency_files_sha256": release_dependency_files,
        "python_runtime": test_python_runtime,
        "python_distribution_versions": preflight.VERITAS_APPROVED_DISTRIBUTION_VERSIONS,
        "launcher_sha256": files["bin/midas_resource_preflight.py"],
        "service_sha256": files["service/midas-veritas-source-analysis.service"],
        "files_sha256": files,
    }
    manifest_bytes = preflight._canonical_json(manifest) + b"\n"
    (root / "RELEASE-MANIFEST.json").write_bytes(manifest_bytes)
    (root / "RELEASE-MANIFEST.sha256").write_text(
        f"{_sha(manifest_bytes)}  RELEASE-MANIFEST.json\n", encoding="ascii"
    )
    for path in sorted(root.rglob("*"), reverse=True):
        os.chmod(path, 0o555 if path.is_dir() else 0o444)
    os.chmod(root, 0o555)
    return root, files


def test_immutable_veritas_release_manifest_checks_exact_dependency_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _files = _release_fixture(tmp_path, monkeypatch)
    result = preflight.verify_veritas_release(
        root,
        expected_release_identity=preflight.VERITAS_RELEASE_ID,
        expected_source_revision=preflight.VERITAS_APPROVED_SOURCE_REVISION,
        expected_module_sha256=preflight.VERITAS_APPROVED_MODULE_SHA256,
    )
    assert result["passed"] is True
    assert result["file_count"] == 34

    dependency = root / "packages/midas/reality/model_fitting.py"
    os.chmod(dependency, 0o644)
    dependency.write_text("# changed helper\n", encoding="utf-8")
    os.chmod(dependency, 0o444)
    with pytest.raises(preflight.AdmissionError, match="file hash mismatch"):
        preflight.verify_veritas_release(
            root,
            expected_release_identity=preflight.VERITAS_RELEASE_ID,
            expected_source_revision=preflight.VERITAS_APPROVED_SOURCE_REVISION,
            expected_module_sha256=preflight.VERITAS_APPROVED_MODULE_SHA256,
        )


def test_immutable_veritas_release_rejects_unvalidated_python_patch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _files = _release_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(preflight.sys, "version_info", SimpleNamespace(major=3, minor=12, micro=4))
    with pytest.raises(preflight.AdmissionError, match="interpreter or ABI"):
        preflight.verify_veritas_release(
            root,
            expected_release_identity=preflight.VERITAS_RELEASE_ID,
            expected_source_revision=preflight.VERITAS_APPROVED_SOURCE_REVISION,
            expected_module_sha256=preflight.VERITAS_APPROVED_MODULE_SHA256,
        )


def _sealed_state(body: dict) -> dict:
    state = dict(body)
    state["state_sha256"] = _sha(preflight._canonical_json(body))
    return state


def test_checkpoint_guard_accepts_v1_and_migrated_v2_lineage_and_rejects_damage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign = _sha(b"campaign")
    legacy_files = {"old-analysis.py": "a" * 64}
    legacy_sha = _sha(preflight._canonical_json(legacy_files))
    monkeypatch.setattr(preflight, "VERITAS_CAMPAIGN_SHA256", campaign)
    monkeypatch.setattr(preflight, "VERITAS_LEGACY_CODE_SHA256", legacy_sha)
    v1_body = {
        "schema_version": 1,
        "analysis_version": "veritas-finalized-reality-source-analysis-v1",
        "campaign_sha256": campaign,
        "analysis_code_sha256": legacy_sha,
        "analysis_code_files": legacy_files,
        "processed_segment_count": 9,
        "last_ordinal": 27,
        "processed_source_bytes": 4096,
        "last_event_sha256": "b" * 64,
        "prefix_catalog_sha256": "c" * 64,
    }
    v1 = _sealed_state(v1_body)
    (tmp_path / "source-analysis-state-v1.json").write_text(json.dumps(v1), encoding="utf-8")
    release = {
        "runtime_analysis_code_sha256": preflight.VERITAS_RUNTIME_ANALYSIS_CODE_SHA256,
        "runtime_analysis_code_files": preflight.VERITAS_APPROVED_RUNTIME_CODE_FILES,
    }
    verified_v1 = preflight.verify_veritas_checkpoint(tmp_path, release)
    assert verified_v1["schema_version"] == 1
    assert verified_v1["processed_segment_count"] == 9

    v2_body = {
        **v1_body,
        "schema_version": 2,
        "analysis_code_sha256": release["runtime_analysis_code_sha256"],
        "analysis_code_files": release["runtime_analysis_code_files"],
        "migration": {
            "from_state_schema_version": 1,
            "from_state_sha256": v1["state_sha256"],
            "from_processed_segment_count": 9,
            "to_analysis_code_sha256": release["runtime_analysis_code_sha256"],
        },
    }
    (tmp_path / "source-analysis-state-v2.json").write_text(
        json.dumps(_sealed_state(v2_body)), encoding="utf-8"
    )
    verified_v2 = preflight.verify_veritas_checkpoint(tmp_path, release)
    assert verified_v2["schema_version"] == 2
    assert verified_v2["legacy_state_sha256"] == v1["state_sha256"]

    path = tmp_path / "source-analysis-state-v2.json"
    corrupted = json.loads(path.read_text(encoding="utf-8"))
    corrupted["last_ordinal"] += 1
    path.write_text(json.dumps(corrupted), encoding="utf-8")
    with pytest.raises(preflight.AdmissionError, match="seal is invalid"):
        preflight.verify_veritas_checkpoint(tmp_path, release)


def test_post_execution_gate_requires_sealed_v2_state_and_bounded_matching_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign = _sha(b"campaign")
    legacy_files = {"old-analysis.py": "a" * 64}
    legacy_sha = _sha(preflight._canonical_json(legacy_files))
    monkeypatch.setattr(preflight, "VERITAS_CAMPAIGN_SHA256", campaign)
    monkeypatch.setattr(preflight, "VERITAS_LEGACY_CODE_SHA256", legacy_sha)
    v1_body = {
        "schema_version": 1,
        "analysis_version": "veritas-finalized-reality-source-analysis-v1",
        "campaign_sha256": campaign,
        "analysis_code_sha256": legacy_sha,
        "analysis_code_files": legacy_files,
        "processed_segment_count": 9,
        "last_ordinal": 27,
        "processed_source_bytes": 4096,
        "last_event_sha256": "b" * 64,
        "prefix_catalog_sha256": "c" * 64,
    }
    v1 = _sealed_state(v1_body)
    (tmp_path / "source-analysis-state-v1.json").write_text(json.dumps(v1), encoding="utf-8")
    release = {
        "runtime_analysis_code_sha256": preflight.VERITAS_RUNTIME_ANALYSIS_CODE_SHA256,
        "runtime_analysis_code_files": preflight.VERITAS_APPROVED_RUNTIME_CODE_FILES,
    }
    before = preflight.verify_veritas_checkpoint(tmp_path, release)

    v2_body = {
        **v1_body,
        "schema_version": 2,
        "analysis_code_sha256": release["runtime_analysis_code_sha256"],
        "analysis_code_files": release["runtime_analysis_code_files"],
        "migration": {
            "from_state_schema_version": 1,
            "from_state_sha256": v1["state_sha256"],
            "from_processed_segment_count": 9,
            "to_analysis_code_sha256": release["runtime_analysis_code_sha256"],
        },
        "processed_segment_count": 10,
        "last_ordinal": 30,
        "processed_source_bytes": 8192,
        "last_event_sha256": "d" * 64,
        "prefix_catalog_sha256": "e" * 64,
    }
    state = _sealed_state(v2_body)
    (tmp_path / "source-analysis-state-v2.json").write_text(json.dumps(state), encoding="utf-8")
    summary = {
        "schema_version": 1,
        "analysis_version": "veritas-finalized-reality-source-analysis-v1",
        "active_segment_read": False,
        "campaign_sha256": campaign,
        "analysis_code_sha256": release["runtime_analysis_code_sha256"],
        "processed_segment_count": 10,
        "processed_source_bytes": 8192,
        "last_processed_ordinal": 30,
        "prefix_catalog_sha256": "e" * 64,
        "batch_processed_segment_count": 1,
        "batch_processed_source_bytes": 4096,
        "status": "catching_up",
        "readiness": "catching_up_finalized_source",
    }
    summary["summary_sha256"] = _sha(preflight._canonical_json(summary))
    summary_path = tmp_path / "source-research-summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    checked = preflight.verify_veritas_post_execution_state(tmp_path, release, before)
    assert checked["schema_version"] == 2
    assert checked["batch_processed_segment_count"] == 1
    assert checked["processed_segment_count"] == 10

    summary["batch_processed_segment_count"] = 129
    summary.pop("summary_sha256")
    summary["summary_sha256"] = _sha(preflight._canonical_json(summary))
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(preflight.AdmissionError, match="bounded batch"):
        preflight.verify_veritas_post_execution_state(tmp_path, release, before)

    for field, invalid_value in (
        ("schema_version", 2),
        ("analysis_version", "unexpected-analysis"),
        ("active_segment_read", True),
    ):
        summary["batch_processed_segment_count"] = 1
        summary[field] = invalid_value
        summary.pop("summary_sha256")
        summary["summary_sha256"] = _sha(preflight._canonical_json(summary))
        summary_path.write_text(json.dumps(summary), encoding="utf-8")
        with pytest.raises(preflight.AdmissionError, match="incompatible semantics"):
            preflight.verify_veritas_post_execution_state(tmp_path, release, before)
        summary[field] = {
            "schema_version": 1,
            "analysis_version": "veritas-finalized-reality-source-analysis-v1",
            "active_segment_read": False,
        }[field]


def test_post_execution_gate_accepts_v1_migration_without_new_eligible_segments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign = _sha(b"campaign")
    legacy_files = {"old-analysis.py": "a" * 64}
    legacy_sha = _sha(preflight._canonical_json(legacy_files))
    monkeypatch.setattr(preflight, "VERITAS_CAMPAIGN_SHA256", campaign)
    monkeypatch.setattr(preflight, "VERITAS_LEGACY_CODE_SHA256", legacy_sha)
    v1_body = {
        "schema_version": 1,
        "analysis_version": "veritas-finalized-reality-source-analysis-v1",
        "campaign_sha256": campaign,
        "analysis_code_sha256": legacy_sha,
        "analysis_code_files": legacy_files,
        "processed_segment_count": 9,
        "last_ordinal": 27,
        "processed_source_bytes": 4096,
        "last_event_sha256": "b" * 64,
        "prefix_catalog_sha256": "c" * 64,
    }
    v1 = _sealed_state(v1_body)
    (tmp_path / "source-analysis-state-v1.json").write_text(json.dumps(v1), encoding="utf-8")
    release = {
        "runtime_analysis_code_sha256": preflight.VERITAS_RUNTIME_ANALYSIS_CODE_SHA256,
        "runtime_analysis_code_files": preflight.VERITAS_APPROVED_RUNTIME_CODE_FILES,
    }
    before = preflight.verify_veritas_checkpoint(tmp_path, release)
    state = _sealed_state(
        {
            **v1_body,
            "schema_version": 2,
            "analysis_code_sha256": release["runtime_analysis_code_sha256"],
            "analysis_code_files": release["runtime_analysis_code_files"],
            "migration": {
                "from_state_schema_version": 1,
                "from_state_sha256": v1["state_sha256"],
                "from_processed_segment_count": 9,
                "to_analysis_code_sha256": release["runtime_analysis_code_sha256"],
            },
        }
    )
    (tmp_path / "source-analysis-state-v2.json").write_text(json.dumps(state), encoding="utf-8")
    summary = {
        "schema_version": 1,
        "analysis_version": "veritas-finalized-reality-source-analysis-v1",
        "active_segment_read": False,
        "campaign_sha256": campaign,
        "analysis_code_sha256": release["runtime_analysis_code_sha256"],
        "processed_segment_count": 9,
        "processed_source_bytes": 4096,
        "last_processed_ordinal": 27,
        "prefix_catalog_sha256": "c" * 64,
        "batch_processed_segment_count": 0,
        "batch_processed_source_bytes": 0,
        "status": "current",
        "readiness": "awaiting_finalized_campaign_window_end",
    }
    summary["summary_sha256"] = _sha(preflight._canonical_json(summary))
    (tmp_path / "source-research-summary.json").write_text(json.dumps(summary), encoding="utf-8")

    checked = preflight.verify_veritas_post_execution_state(tmp_path, release, before)
    assert checked["schema_version"] == 2
    assert checked["processed_segment_count"] == before["processed_segment_count"]
    assert checked["batch_processed_segment_count"] == 0


def test_release_worker_command_is_fixed_to_immutable_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "release"
    monkeypatch.setattr(preflight, "VERITAS_RELEASE_ROOT", root)
    monkeypatch.setattr(
        preflight,
        "verify_veritas_release",
        lambda *_args, **_kwargs: {
            "passed": True,
            "release_identity": preflight.VERITAS_RELEASE_ID,
        },
    )
    command = preflight._veritas_worker_command(root)
    assert command[:3] == [
        str(preflight.VERITAS_RUNTIME_PYTHON),
        "-S",
        str(root / "scripts" / "veritas_source_analysis.py"),
    ]
    assert preflight._validate_veritas_worker_command(
        command, root, preflight.VERITAS_APPROVED_MODULE_SHA256
    )["passed"]
    with pytest.raises(preflight.AdmissionError, match="fixed bounded"):
        preflight._validate_veritas_worker_command(
            [*command, "--max-segments", "9999"], root, preflight.VERITAS_APPROVED_MODULE_SHA256
        )
    with pytest.raises(preflight.AdmissionError, match="module hash"):
        preflight._validate_veritas_worker_command(command, root, "0" * 64)


def test_source_service_execstart_is_the_single_guarded_execution_owner() -> None:
    unit = Path("deploy/systemd/user/midas-veritas-source-analysis.service").read_text(
        encoding="utf-8"
    )
    execstart = next(
        line.partition("=")[2] for line in unit.splitlines() if line.startswith("ExecStart=")
    )
    execstart = execstart.replace("%h", str(Path.home()))
    assert shlex.split(execstart) == preflight._expected_veritas_service_execstart()
    assert "UnsetEnvironment=PYTHONPATH" in unit
    assert "ProtectSystem=strict" in unit
    assert "ProtectHome=read-only" in unit
    assert "Restart=no" in unit
    assert "KillMode=control-group" in unit
    assert "--max-segments 128 --max-source-mib 32" in unit


def test_pinned_worker_python_does_not_load_editable_install_pth(tmp_path: Path) -> None:
    release_packages = tmp_path / "release-packages"
    release_midas = release_packages / "midas"
    release_midas.mkdir(parents=True)
    (release_midas / "__init__.py").write_text(
        "from pkgutil import extend_path\n__path__ = extend_path(__path__, __name__)\n",
        encoding="utf-8",
    )
    (release_midas / "pinned.py").write_text("VALUE = 'release'\n", encoding="utf-8")

    editable_root = tmp_path / "checkout-packages"
    editable_midas = editable_root / "midas"
    editable_midas.mkdir(parents=True)
    (editable_midas / "leaked.py").write_text("VALUE = 'checkout'\n", encoding="utf-8")
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    (site_packages / "editable-install.pth").write_text(f"{editable_root}\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            "import importlib.util, midas.pinned; "
            "assert midas.pinned.VALUE == 'release'; "
            "assert importlib.util.find_spec('midas.leaked') is None",
        ],
        cwd=tmp_path,
        env={
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": f"{release_packages}:{site_packages}",
        },
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_transient_veritas_gate_requires_effective_limits_and_both_parent_identities(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    unit = "midas-heavy-veritas-test-123456789abc.service"
    invocation_id = "d" * 32
    properties = {
        "ActiveState": "active",
        "MainPID": str(os.getpid()),
        "InvocationID": invocation_id,
        "MemoryHigh": str(192 * preflight.MIB),
        "MemoryMax": str(256 * preflight.MIB),
        "MemorySwapMax": "0",
        "CPUQuotaPerSecUSec": "1s",
        "IOWeight": "10",
        "TasksMax": "256",
        "Nice": "19",
        "IOSchedulingClass": "3",
        "ProtectSystem": "strict",
        "ProtectHome": "read-only",
        "ReadWritePaths": (
            f"{preflight.VERITAS_OUTPUT_ROOT} {tmp_path} "
            f"{preflight.VERITAS_USER_MANAGER_BUS_SOCKET}"
        ),
        "Environment": (
            f"XDG_RUNTIME_DIR={preflight.VERITAS_USER_MANAGER_RUNTIME_DIR} "
            "DBUS_SESSION_BUS_ADDRESS=unix:path="
            f"{preflight.VERITAS_USER_MANAGER_BUS_SOCKET}"
        ),
        "PrivateTmp": "yes",
        "NoNewPrivileges": "yes",
        "UMask": "0077",
        "RuntimeMaxUSec": "10min",
        "TimeoutStartUSec": "10min",
        "KillMode": "control-group",
        "Restart": "no",
    }
    monkeypatch.setattr(preflight, "_current_veritas_service_unit", lambda: unit)
    monkeypatch.setattr(
        preflight,
        "_systemctl",
        lambda *_args, **_kwargs: SimpleNamespace(
            stdout="\n".join(f"{key}={value}" for key, value in properties.items())
        ),
    )
    monkeypatch.setattr(
        preflight,
        "_cgroup_execution_metrics",
        lambda: {
            "available": True,
            "io_weight_enforced": True,
            "io_weight": "default 10\n",
            "limits": {
                "memory.high": str(192 * preflight.MIB),
                "memory.max": str(256 * preflight.MIB),
                "memory.swap.max": "0",
                "cpu.max": "100000 100000",
                "pids.max": "256",
            },
            "memory_peak_bytes": 42 * preflight.MIB,
            "memory": {"oom_kill_events": 0},
        },
    )
    result = preflight._validate_veritas_transient_unit(
        expected_status_dir=tmp_path,
        parent_invocation_id="e" * 32,
        parent_pid=123,
    )
    assert result["limits_verified"] is True
    assert result["parent_service_invocation_id"] == "e" * 32

    properties["Environment"] = ""
    with pytest.raises(preflight.AdmissionError, match="user-manager invocation"):
        preflight._validate_veritas_transient_unit(
            expected_status_dir=tmp_path,
            parent_invocation_id="e" * 32,
            parent_pid=123,
        )

    properties["Environment"] = (
        f"XDG_RUNTIME_DIR={preflight.VERITAS_USER_MANAGER_RUNTIME_DIR} "
        "DBUS_SESSION_BUS_ADDRESS=unix:path="
        f"{preflight.VERITAS_USER_MANAGER_BUS_SOCKET}"
    )
    properties["MemoryMax"] = str(512 * preflight.MIB)
    with pytest.raises(preflight.AdmissionError, match="limits differ"):
        preflight._validate_veritas_transient_unit(
            expected_status_dir=tmp_path,
            parent_invocation_id="e" * 32,
            parent_pid=123,
        )


@pytest.mark.parametrize(
    ("inner_code", "runner_code", "expected"),
    [(0, 0, "worker_succeeded"), (7, 7, "worker_failed"), (0, 7, "result_missing_indeterminate")],
)
def test_veritas_result_requires_worker_systemd_and_receipt_evidence(
    inner_code: int, runner_code: int, expected: str
) -> None:
    unit = {
        "InvocationID": "a" * 32,
        "ExecMainStartTimestamp": "now",
        "Result": "success" if inner_code == 0 else "exit-code",
    }
    inner = {
        "phase": "worker_finished",
        "worker_exit_code": inner_code,
        "execution_context": {
            "release": {"passed": True},
            "transient_unit": {"limits_verified": True},
        },
    }
    kwargs = {
        "profile": "veritas",
        "return_code": runner_code,
        "unit": unit,
        "inner": inner,
        "watchdog": None,
        "parent_signal": None,
        "runner_error": None,
        "unit_was_active_after_client_exit": False,
        "systemd_wait_completed": True,
        "applied_limits_verified": True,
        "unit_cleanup_confirmed": True,
        "unit_after_wait": {"LoadState": "not-found"},
    }
    assert preflight._classify_guarded_result(**kwargs) == expected
    assert (
        preflight._classify_guarded_result(**{**kwargs, "unit_cleanup_confirmed": False})
        == "result_missing_indeterminate"
    )
    if inner_code:
        contradictory = {
            **kwargs,
            "unit_after_wait": {
                "LoadState": "loaded",
                "Result": "exit-code",
                "ExecMainCode": "exited",
                "ExecMainStatus": str(inner_code + 1),
            },
        }
        assert preflight._classify_guarded_result(**contradictory) == "result_missing_indeterminate"


def test_missing_veritas_lifecycle_evidence_never_becomes_success() -> None:
    common = {
        "profile": "veritas",
        "return_code": 0,
        "unit": {"ExecMainStartTimestamp": "now", "InvocationID": "a" * 32},
        "inner": None,
        "watchdog": None,
        "parent_signal": None,
        "runner_error": None,
        "unit_was_active_after_client_exit": False,
        "systemd_wait_completed": True,
        "applied_limits_verified": True,
        "unit_cleanup_confirmed": True,
    }
    assert preflight._classify_guarded_result(**common) == "result_missing_indeterminate"
    assert (
        preflight._classify_guarded_result(
            **{**common, "unit": None, "runner_error": "bus unavailable"}
        )
        == "unit_creation_failed"
    )
    assert (
        preflight._classify_guarded_result(
            **{
                **common,
                "unit": {"ActiveState": "inactive", "ExecMainStartTimestamp": "n/a"},
            }
        )
        == "unit_created_not_started"
    )
