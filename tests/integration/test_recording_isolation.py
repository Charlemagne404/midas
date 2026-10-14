from pathlib import Path

from apps.api.config import Settings
from apps.api.service import Service


def test_temporary_database_has_its_own_recording_directory(tmp_path):
    service = Service(Settings(database_url=f"sqlite+aiosqlite:///{tmp_path}/paper.db"))
    assert service.recorder.root == tmp_path / "recordings"


def test_explicit_recording_root_is_preserved(tmp_path):
    destination = tmp_path / "separate-capture"
    service = Service(
        Settings(
            database_url=f"sqlite+aiosqlite:///{tmp_path}/paper.db",
            recording_root=destination,
        )
    )
    assert service.recorder.root == destination


def test_default_production_recording_location_is_compatible():
    service = Service(Settings(database_url="sqlite+aiosqlite:///./data/midas.db"))
    assert service.recorder.root == Path("data/recordings")
