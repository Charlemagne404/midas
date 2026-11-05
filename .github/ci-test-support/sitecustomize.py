"""Synthetic user-manager PSI for bounded isolated CI worker and API tests.

The GitHub hosted runner does not place this disposable API process inside a
systemd user-manager cgroup. Keep CPU, memory, I/O, disk, and process-pool
checks real; provide only the missing user-manager PSI reading. This module is
loaded from the explicit CI support path and activates only in pytest-spawned
children or an isolated browser API process.
"""

from __future__ import annotations

import os

if os.environ.get("MIDAS_PHASE5_SYNTHETIC_USER_PSI") == "1" and (
    os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("MIDAS_PHASE5_ISOLATED_API") == "1"
):
    from midas.arena import admission

    def synthetic_user_manager_memory_pressure_avg10(**_kwargs: object) -> dict[str, float]:
        return {"some": 0.0, "full": 0.0}

    admission.user_manager_memory_pressure_avg10 = synthetic_user_manager_memory_pressure_avg10
