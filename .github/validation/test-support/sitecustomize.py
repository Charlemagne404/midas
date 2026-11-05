"""Synthetic user-manager PSI for bounded native-worker CI children only."""

from __future__ import annotations

import os


if (
    os.environ.get("MIDAS_PHASE5_SYNTHETIC_USER_PSI") == "1"
    and os.environ.get("PYTEST_CURRENT_TEST")
):
    from midas.arena import admission

    # The CI container has no systemd user slice. Keep every other resource
    # signal real and bounded by Docker's cgroup; inject only the missing
    # user-manager PSI reader into child interpreters launched by pytest.
    admission.user_manager_memory_pressure_avg10 = lambda **_kwargs: {
        "some": 0.0,
        "full": 0.0,
    }
