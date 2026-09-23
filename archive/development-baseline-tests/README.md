# Retired test fragments

These fragments were removed from active discovery on 2026-09-23. They describe
the retired SQL/IMS core and a removed one-time iperf repair, not the supported
Open5GS data-only stack. They are preserved for history and are not executable
acceptance tests. Active Open5GS coverage remains in `tests/test_open5gs_*.py`;
resource preflight and radio handoff tests remain active.

The legacy UE acceptance runner, its SQL/IMS tests, and the legacy core throughput
smoke runner were retired in Jetson 0.4.0. They are historical source only and
are excluded from release packages and active test discovery. Current protections
are covered by the Jetson agent/modem/network tests.
