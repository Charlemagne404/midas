from midas.arena.jobs import artifact_usage
from midas.arena.tournaments import TournamentSpec

from scripts.profile_arena_budget import pathlib_bytes, profile, scandir_bytes


def test_scan_parity_including_file_links_without_directory_recursion(tmp_path):
    (tmp_path / "one").write_bytes(b"abc")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "two").write_bytes(b"12345")
    (tmp_path / "file-link").symlink_to(tmp_path / "one")
    (tmp_path / "directory-link").symlink_to(tmp_path / "nested", target_is_directory=True)
    (tmp_path / "broken-link").symlink_to(tmp_path / "missing")
    assert pathlib_bytes(tmp_path) == scandir_bytes(tmp_path) == (11, 3)
    assert artifact_usage(tmp_path) == (11, 3)
    report = profile(tmp_path, repeats=2)
    assert len(report["measurements"]) == 4
    assert all(r["bytes"] == 11 for r in report["measurements"])


def test_performance_replay_is_explicit_and_research_remains_default():
    assert TournamentSpec(dataset_id="d").purpose == "research"
    assert (
        TournamentSpec(dataset_id="d", purpose="performance_replay").purpose == "performance_replay"
    )
