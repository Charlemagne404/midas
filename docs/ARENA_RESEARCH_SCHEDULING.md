# Finite research scheduling

A plan contains1-32 ordered native job configurations and due offsets within
a1-minute to7-day admission window. Source identity is frozen at creation.
Dispatch waits for idle research, at least2GiB available RAM,2GiB disk free and
headroom under the unchanged1GiB Arena cap. Native child budgets remain enforced.

Stable admission keys are written into child job records before launch. After
a crash between native admission and plan update, dispatch returns that same
child. Incomplete/interrupted children fail visibly and are not automatically
retried. Source changes produce STALE_SOURCE and a local persisted alert.
Expiry stops new admissions; existing bounded children may finish.

The user timer invokes one dispatcher pass each minute (25%CPU,512MiB,60s).
Persistent timers and user lingering allow pending plans to be observed after
logout/reboot. Transient child jobs interrupted by reboot require explicit
recovery; this does not claim automatic resumption of arbitrary training.

Pause/resume/cancel controls affect plan admissions. Cancel already admitted
children separately through Arena. Terminal completion/failure evidence is
preserved. Alerts appear in Research Director and remain local; no external
message is sent. Child model-selection behavior is unchanged.

Install after validation with `.venv/bin/python -m scripts.install_schedule_timer`.
Inspect `systemctl --user status midas-arena-scheduler.timer` and its service
journal. Stop polling with `systemctl --user disable --now
midas-arena-scheduler.timer`. Existing Midas API/web units are not modified.
