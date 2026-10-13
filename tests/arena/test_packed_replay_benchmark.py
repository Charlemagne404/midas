import pytest

from scripts.benchmark_packed_replays import benchmark
from scripts.pack_replays import pack, prune
from tests.arena.test_replay_packing import fixture


def test_matched_benchmark_preserves_replay_values(tmp_path):
    directory, _ = fixture(tmp_path)
    pack(tmp_path, "tournaments", "tournament-test")
    prune(tmp_path, "tournaments", "tournament-test")
    result = benchmark(tmp_path, directory / "replays", samples=3)
    assert result["matched_reads"] == 3
    assert result["artifact_files"] > 0
    assert result["median_packed_read_seconds"] > 0
    assert result["median_restored_read_seconds"] > 0


def test_invalid_sample_budget_refused(tmp_path):
    with pytest.raises(ValueError, match="samples"):
        benchmark(tmp_path, tmp_path, samples=201)
