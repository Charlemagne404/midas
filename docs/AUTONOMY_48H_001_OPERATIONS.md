# MIDAS 48H-001 Operations

The finite campaign state is stored under `data/autonomy/48H-001/`. It is created only after preflight passes. The user systemd timer persists independently of a terminal and is enabled for the user manager, which has linger enabled on the current host.

## Inspect status

```bash
cd /home/charlie/midas
./.venv/bin/python scripts/autonomy_48h.py status
systemctl --user status midas-autonomy-48h-001.timer
```

`STATUS.md` and `status.json` are refreshed every five minutes. The final report will be written to `data/autonomy/48H-001/AUTONOMY_48H_001_FINAL_REPORT.md` after the 48-hour deadline and bounded completion grace period.

## Pause, resume, cancel

```bash
./.venv/bin/python scripts/autonomy_48h.py pause
./.venv/bin/python scripts/autonomy_48h.py resume
./.venv/bin/python scripts/autonomy_48h.py cancel
```

Pause stops new campaign job admission and lets a healthy current job finish. Resume uses the original deadline. Cancel requests cancellation of the current campaign job, preserves partial artifacts, and permanently ends this campaign. Neither action stops Reality, Veritas, the Arena scheduler, or other ordinary MIDAS services.

The supervisor log is available with:

```bash
journalctl --user -u midas-autonomy-48h-001.service
```

All campaign-generated Arena work is hypothetical synthetic simulation. It cannot place orders or promote a result into a protected campaign.
