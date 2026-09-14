# Optional Site Migration Tools

This directory contains site-specific migration and coexistence tools. Default
application startup, installation and tests must not require an existing platform.

## Original Jetson Baseline Audit

`audit_jetson_baseline.py` checks the original restoration report against current
code, frontend, configuration and helper checksums. It reads selected database
fields with a read-only SQLite connection and records service and network state.
It sends no AT commands, changes no services and writes no application database.
The output omits SIM identity, authentication material and raw modem responses.

The current site needs terminal sudo because its restoration report, configuration
and database are protected. Use the installed original Python runtime only for
this one-time migration audit; it is not a V2 runtime dependency.

```sh
sudo /opt/oai-console/venv/bin/python -I /home/matt/aoc-v2-jetson-baseline.py --output /home/matt/aoc-v2-jetson-baseline-01.json
```

The staged script corresponds to this directory's audit source. Output is created
with mode `0600`, owned by the invoking sudo user. Existing output is never
overwritten; choose a new numbered filename for another observation. Keep full
reports on the device; archive only reviewed, sanitized findings in Git.

Successful execution is not acceptance. Check every restoration comparison,
maintenance state, in-flight tasks and freshness of the data-path evidence.
Public health responses alone do not prove UE connectivity. This audit does not
perform a throughput test or prove that a stale stored session remains usable.
