import json
import threading
import time
from pathlib import Path

import pytest
from midas.laboratory.analytics import compare
from midas.laboratory.campaigns import Campaigns, CampaignSpec, run_group
from pydantic import ValidationError

DATASETS = Path(__file__).resolve().parents[2] / "data/datasets"


@pytest.fixture(autouse=True)
def isolated_admission(tmp_path, monkeypatch):
    from midas.arena import admission

    monkeypatch.setattr(admission, "global_lock_path", lambda: tmp_path / "admission.lock")
    monkeypatch.setattr(
        admission,
        "resource_snapshot",
        lambda _: {
            "active_job_ids": [],
            "available_memory_bytes": 16 * 1024**3,
            "disk_free_bytes": 30 * 1024**3,
            "cpu_psi": {"some": 0},
            "memory_psi": {"some": 0, "full": 0},
            "io_psi": {"some": 0},
        },
    )


def test_pool_capacity_respects_api_and_ancestor_limits(tmp_path):
    from midas.laboratory.campaigns import require_pool_capacity

    proc, groups = tmp_path / "proc", tmp_path / "groups"
    (proc / "self").mkdir(parents=True)
    (groups / "user/api").mkdir(parents=True)
    (proc / "self/cgroup").write_text("0::/user/api\n")
    (proc / "self/status").write_text("VmRSS: 262144 kB\n")
    (groups / "user/api/memory.high").write_text(str(1536 * 1024**2))
    (groups / "user/api/memory.max").write_text(str(1792 * 1024**2))
    (groups / "user/memory.max").write_text("max")
    require_pool_capacity(CampaignSpec(workers=2), proc_root=proc, cgroup_root=groups)
    with pytest.raises(ValueError, match="fewer/smaller"):
        require_pool_capacity(CampaignSpec(workers=4), proc_root=proc, cgroup_root=groups)
    (groups / "user/memory.max").write_text(str(1024 * 1024**2))
    with pytest.raises(ValueError, match="working limit"):
        require_pool_capacity(CampaignSpec(workers=2), proc_root=proc, cgroup_root=groups)


def test_laboratory_holds_shared_admission_through_pause_drain(tmp_path, monkeypatch):
    from midas.arena import admission

    entered, finish = threading.Event(), threading.Event()
    monkeypatch.setattr(Campaigns, "_drive", lambda *args: (entered.set(), finish.wait(5)))
    lab = Campaigns(tmp_path / "lab", DATASETS)
    try:
        record = lab.create(CampaignSpec(runs=1))
        assert entered.wait(2)
        lab.control(record["id"], "pause")
        with pytest.raises(admission.ResourceAdmissionDenied):
            with admission.resource_admission_slot():
                pass
        finish.set()
        lab.threads[record["id"]].join(5)
        with admission.resource_admission_slot():
            pass
    finally:
        finish.set()
        lab.close()


def test_resource_denial_keeps_campaign_ready_and_releases_lease(tmp_path, monkeypatch):
    from midas.arena import admission

    snapshot = admission.resource_snapshot(tmp_path)
    snapshot["cpu_psi"] = {"some": 99}
    monkeypatch.setattr(admission, "resource_snapshot", lambda _: snapshot)
    lab = Campaigns(tmp_path / "lab", DATASETS)
    try:
        with pytest.raises(ValueError, match="waiting for resources"):
            lab.create(CampaignSpec(runs=1))
        assert lab.all()[0]["status"] == "READY"
        assert not lab.threads
        with admission.resource_admission_slot():
            pass
    finally:
        lab.close()


def test_thread_start_failure_releases_admission_and_preserves_recovery(tmp_path, monkeypatch):
    from midas.arena import admission

    def fail(*args, **kwargs):
        raise RuntimeError("thread unavailable")

    monkeypatch.setattr(threading.Thread, "start", fail)
    lab = Campaigns(tmp_path / "lab", DATASETS)
    try:
        with pytest.raises(RuntimeError, match="thread unavailable"):
            lab.create(CampaignSpec(runs=1))
        assert lab.all()[0]["status"] == "INTERRUPTED"
        assert not lab.threads
        with admission.resource_admission_slot():
            pass
    finally:
        lab.close()


def wait(lab, id, timeout=20):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        result = lab.get(id)
        if result["status"] != "RUNNING":
            thread = lab.threads.get(id)
            if thread:
                thread.join(timeout=5)
            return lab.get(id)
        time.sleep(0.02)
    raise AssertionError("Campaign did not terminate")


def test_campaign_parallel_results_deterministic_and_compact_reconstruction(tmp_path):
    lab = Campaigns(tmp_path, DATASETS)
    try:
        config = CampaignSpec(runs=6, retain_successes=0)
        first = lab.create(config)
        assert wait(lab, first["id"])["status"] == "COMPLETED"
        parallel = lab.create(config.model_copy(update={"workers": 2}))
        assert wait(lab, parallel["id"])["status"] == "COMPLETED"
        one, two = lab.runs(first["id"]), lab.runs(parallel["id"])
        assert [r["result"]["result_hash"] for r in one] == [
            r["result"]["result_hash"] for r in two
        ]
        assert lab.artifact(one[0]["id"])["result"]["journal"]
        with lab.connect() as c:
            assert (
                c.execute("SELECT count(*) FROM runs WHERE artifact IS NOT NULL").fetchone()[0] == 0
            )
    finally:
        lab.close()


def test_interrupt_checkpoint_cancel_resume_and_reopen(tmp_path):
    lab = Campaigns(tmp_path, DATASETS)
    spec = CampaignSpec(runs=5)
    campaign = lab.create(spec, launch=False)
    # A real committed episode before abrupt interruption; unfinished work is rerun.
    lab._commit(campaign["id"], 0, run_group(spec.model_dump(mode="json"), 0, str(DATASETS)))
    with lab.connect() as c:
        c.execute("UPDATE campaigns SET status='RUNNING' WHERE id=?", (campaign["id"],))
    lab.close()
    recovered = Campaigns(tmp_path, DATASETS)
    try:
        assert recovered.get(campaign["id"])["status"] == "INTERRUPTED"
        recovered.control(campaign["id"], "cancel")
        assert recovered.get(campaign["id"])["status"] == "CANCELLED"
        recovered.control(campaign["id"], "resume")
        assert wait(recovered, campaign["id"])["completed"] == 5
        with recovered.connect() as c:
            assert c.execute("SELECT count(*) FROM runs WHERE idx=0").fetchone()[0] == 1
    finally:
        recovered.close()


def test_active_pause_commits_inflight_work_and_safe_resume(tmp_path):
    lab = Campaigns(tmp_path, DATASETS)
    try:
        campaign = lab.create(CampaignSpec(runs=30))
        lab.control(campaign["id"], "pause")
        paused = wait(lab, campaign["id"])
        assert paused["status"] == "PAUSED"
        assert paused["completed"] < 30
        lab.control(campaign["id"], "resume")
        assert wait(lab, campaign["id"])["completed"] == 30
    finally:
        lab.close()


def test_compact_results_require_an_exact_replay_match(tmp_path, monkeypatch):
    lab = Campaigns(tmp_path, DATASETS)
    try:
        campaign = lab.create(CampaignSpec(runs=1, retain_successes=0))
        wait(lab, campaign["id"])
        run = lab.runs(campaign["id"])[0]
        monkeypatch.setattr(
            "midas.laboratory.campaigns.code_hash", lambda: "different-implementation"
        )
        # An operational source hash change is safe when deterministic execution matches.
        assert lab.artifact(run["id"])["result"]["result_hash"] == run["result"]["result_hash"]
        monkeypatch.setattr(
            "midas.laboratory.campaigns.execute",
            lambda scenario: {"result_hash": "different-result"},
        )
        with pytest.raises(ValueError, match="no longer reproduces"):
            lab.artifact(run["id"])
    finally:
        lab.close()


def test_resource_limits_and_configuration_fail_closed():
    with pytest.raises(ValidationError, match="Extreme"):
        CampaignSpec(runs=1_000_000)
    with pytest.raises(ValidationError, match="fee"):
        CampaignSpec(dataset_id="ctf-4024677", fee_rate=".01")
    with pytest.raises(ValidationError):
        CampaignSpec(workers=128)
    with pytest.raises(ValidationError):
        CampaignSpec(families=("imaginary",))


def test_paired_comparison_same_scenarios_preserves_no_trade_and_losses(tmp_path):
    lab = Campaigns(tmp_path, DATASETS)
    try:
        campaign = lab.create(
            CampaignSpec(
                runs=3, models=("optimistic", "conservative"), strategies=("arbitrage", "no_trade")
            )
        )
        finished = wait(lab, campaign["id"])
        assert finished["completed"] == 12
        rows = lab.runs(campaign["id"])
        analysis = compare(rows)
        assert len(analysis["distributions"]) == 4
        assert all(
            d["mean"] == 0 for d in analysis["distributions"] if d["variant"].startswith("no_trade")
        )
        assert all(p["pairs"] == 3 for p in analysis["paired"])
        assert compare(rows) == analysis
        # Fees, limits and starting capital match across all compared strategies.
        for row in rows:
            artifact = lab.artifact(row["id"])
            scenario = artifact["result"]["scenario"]
            assert scenario["account"]["capital"] == "100"
            assert scenario["account"]["limits"] == finished["spec"]["limits"]
    finally:
        lab.close()


def test_failure_artifacts_and_original_incident_preserved(tmp_path):
    lab = Campaigns(tmp_path, DATASETS)
    try:
        campaign = lab.create(
            CampaignSpec(runs=1, families=("ledger_mutation",), retain_successes=0)
        )
        assert wait(lab, campaign["id"])["failed"] == 1
        row = lab.runs(campaign["id"])[0]
        artifact = lab.artifact(row["id"])
        assert artifact["incident"]["classification"] == "CONTROLLED_MUTATION"
        assert artifact["result"]["journal"]
        original = json.dumps(artifact["incident"])
        assert json.dumps(lab.artifact(row["id"])["incident"]) == original
    finally:
        lab.close()


def test_single_writer_ownership_and_read_only_archive(tmp_path):
    writer = Campaigns(tmp_path, DATASETS)
    try:
        with pytest.raises(ValueError, match="writer"):
            Campaigns(tmp_path, DATASETS)
        reader = Campaigns(tmp_path, DATASETS, read_only=True)
        try:
            assert reader.all() == []
            with pytest.raises(ValueError, match="reader"):
                reader.create(CampaignSpec(runs=1))
        finally:
            reader.close()
    finally:
        writer.close()


def test_journal_tampering_and_conflicting_result_identity_detected(tmp_path):
    lab = Campaigns(tmp_path, DATASETS)
    try:
        spec = CampaignSpec(runs=1)
        campaign = lab.create(spec)
        assert wait(lab, campaign["id"])["status"] == "COMPLETED"
        row = lab.runs(campaign["id"])[0]
        with lab.connect() as c:
            archived = json.loads(
                c.execute("SELECT artifact FROM runs WHERE id=?", (row["id"],)).fetchone()[0]
            )
            archived["journal"][0]["after"]["available"] = "999"
            c.execute("UPDATE runs SET artifact=? WHERE id=?", (json.dumps(archived), row["id"]))
        with pytest.raises(ValueError, match="journal integrity"):
            lab.artifact(row["id"])
        mutated = run_group(spec.model_dump(mode="json"), 0, str(DATASETS))
        mutated[0]["result"]["result_hash"] = "different"
        with pytest.raises(ValueError, match="Conflicting experiment"):
            lab._commit(campaign["id"], 0, mutated)
    finally:
        lab.close()


def test_wall_and_disk_budgets_interrupt_without_losing_results(tmp_path):
    lab = Campaigns(tmp_path, DATASETS)
    try:
        # Deliberately pre-exhausted disk budget, bounded artifact preserved explicitly.
        (tmp_path / "budget-probe").write_bytes(b"x" * 9 * 1024**2)
        campaign = lab.create(CampaignSpec(runs=100, max_disk_mb=8))
        interrupted = wait(lab, campaign["id"])
        assert interrupted["status"] == "INTERRUPTED"
        assert "disk budget" in interrupted["error"]
        (tmp_path / "budget-probe").unlink()
        # Wall budget already consumed by archived coordinator time.
        with lab.connect() as c:
            c.execute("UPDATE campaigns SET elapsed=301 WHERE id=?", (campaign["id"],))
        lab.control(campaign["id"], "resume")
        assert "Wall-clock" in wait(lab, campaign["id"])["error"]
    finally:
        lab.close()


def test_low_capital_family_and_invalid_financial_results_not_aggregated(tmp_path):
    from midas.laboratory.campaigns import plan

    spec = CampaignSpec(runs=1, families=("low_capital",), strategies=("arbitrage", "no_trade"))
    scenarios = plan(spec, 0, DATASETS)
    assert scenarios[0].account.capital <= 5
    assert scenarios[0].account.capital == scenarios[1].account.capital
    lab = Campaigns(tmp_path, DATASETS)
    try:
        campaign = lab.create(CampaignSpec(runs=1, families=("ledger_mutation",)))
        completed = wait(lab, campaign["id"])
        assert completed["failed"] == 1
        assert completed["mean_pnl"] is None
        assert compare(lab.runs(campaign["id"]))["excluded_invariant_failures"] == 1
    finally:
        lab.close()


def test_isolated_recorder_does_not_change_simulation_identity(tmp_path, monkeypatch):
    from midas.laboratory import campaigns

    source_root = Path(campaigns.__file__).resolve().parents[3]
    for path in (source_root / "packages/midas").rglob("*.py"):
        destination = tmp_path / path.relative_to(source_root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(path.read_bytes())
    monkeypatch.setattr(
        campaigns, "__file__", str(tmp_path / "packages/midas/laboratory/campaigns.py")
    )
    baseline = campaigns.code_hash()
    recorder = tmp_path / "packages/midas/reality/recorder_extension.py"
    recorder.write_text("# independent read-only recorder extension\n")
    assert campaigns.code_hash() == baseline
    # Financial-domain changes must still invalidate the simulation identity.
    contract = tmp_path / "packages/midas/core/contract_extension.py"
    contract.write_text("# financial contract change\n")
    assert campaigns.code_hash() != baseline
