# Spark Troubleshooting

[简体中文](troubleshooting-bs-spark.zh-CN.md)

Use the symptom-based checks below when diagnosing issues on **DGX Spark**.

## Monitor Unavailable or Missing Radio Telemetry

- **Web UI unreachable on `127.0.0.1:8877`**: Check `aoc-control.service`, `aoc-observe.service`, and `aoc-monitor-web.service` status and systemd journals. If `/api/v1/health` succeeds while SSE disconnects, inspect SSH tunnel stability and session expiration before restarting services.
- **Host/core visible, gNB scheduler metrics missing**:
  - Run `ss -tna | grep :8879` and confirm `127.0.0.1:8879` is `LISTEN`ing with an `ESTAB` connection from `aoc-observe.service`.
  - Inspect `sudo nft -nn list table inet aoc_v2_metrics_guard` to verify root-only access on port `8879`.
  - Confirm `docker network inspect aoc-v2-open5gs-core` returns the active bridge interface if bridge counters read zero.

## OCUDU Radio Fails to Start

- **Process exit or B210 ownership conflict**: Run `aoc-v2ctl status`, inspect the `aoc-v2-radio.service` journal, and verify no competing process holds the USRP B210 USB device.
- **Active process without N2 NG Setup**: Confirm Open5GS AMF health first; preserve failure logs prior to retrying.
- **Unexpected configuration overrides**: Run `systemctl show aoc-v2-radio.service -p DropInPaths` to confirm no transient `/run/systemd/system/` drop-ins shadow `runtime.py` settings.

## Open5GS Core Unhealthy

- Inspect the failing container (`docker ps -a`, `docker logs`) for exit codes or OOM events, and isolate N2, N3, N4, and N6 paths independently.
- If `mongo` exits on Linux 7.0+ kernels due to TCMalloc `rseq` allocation, confirm `GLIBC_TUNABLES=glibc.pthread.rseq=1` is present in the rendered `compose.json` (see [Hardware Notes](reference/hardware-notes.md#host-os-and-kernel-compatibility-notes)).

## Stale or Disconnected UE State

- Compare the active gNB process generation ID, RAN context timestamp, Open5GS PDU session, and UE probe status in Spark Platform. Sessions recorded under an earlier gNB process generation remain historical until post-restart correlation telemetry arrives.

## RF Errors (`underflow` / `late`) or Low Throughput

- Verify `aoc-v2-cpu-latency.service` is `active` and confirm `realtime.conf` CPU core affinity isolation is applied when co-located GPU/CPU workloads run on Spark (see [Ports & Runtime](reference/ports-and-runtime.md)).
- Audit persisted B210 gains and MCS caps in [Network & RF Profile](reference/network-and-rf-profile.md), inspect antenna/attenuator seating, change one radio parameter at a time with a backup, and re-test under identical physical conditions.
