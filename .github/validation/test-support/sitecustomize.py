"""Synthetic user-manager PSI for bounded isolated worker and API tests only."""

from __future__ import annotations

import os


if (
    os.environ.get("MIDAS_PHASE5_SYNTHETIC_USER_PSI") == "1"
    and (
        os.environ.get("PYTEST_CURRENT_TEST")
        or os.environ.get("MIDAS_PHASE5_ISOLATED_API") == "1"
    )
):
    from midas.arena import admission

    # The CI container has no systemd user slice. Keep every other resource
    # signal real and bounded by Docker's cgroup; inject only the missing
    # user-manager PSI reader into pytest children and its isolated API server.
    admission.user_manager_memory_pressure_avg10 = lambda **_kwargs: {
        "some": 0.0,
        "full": 0.0,
    }
