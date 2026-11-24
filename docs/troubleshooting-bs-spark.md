# Spark Troubleshooting

[简体中文](troubleshooting-bs-spark.zh-CN.md)

Use the symptom-based checks below when diagnosing issues on **DGX Spark**.

## Monitor Unavailable or Missing Radio Telemetry

- **Web UI unreachable on `127.0.0.1:8877`**: Inspect `aoc-control.service`, `aoc-observe.service`, and `aoc-monitor-web.service` status and journals. If `/api/v1/health` is OK while SSE disconnects, verify SSH tunnel health and session expiry before restarting services.
- **Host/core visible, gNB scheduler metrics missing**:
  - Run `ss -tna | grep :8879` and confirm `127.0.0.1:8879` is listening with an `ESTAB` connection from `aoc-observe.service`.
  - Inspect `sudo nft -nn list table inet aoc_v2_metrics_guard` to verify root-only access on port `8879`.
  - Confirm `docker network inspect aoc-v2-open5gs-core` returns the active bridge interface if bridge counters remain empty.

## OCUDU Radio Fails to Start

- **Process or B210 ownership failure**: Run `aoc-v2ctl status`, inspect the `aoc-v2-radio.service` journal, and confirm no other process holds the USRP B210 USB device.
- **Active process without N2 NG Setup**: Confirm Open5GS AMF is healthy first; preserve failure logs before retrying.
- **Unexpected config overrides**: Run `systemctl show aoc-v2-radio.service -p DropInPaths` to verify no stale temporary `/run/systemd/system/` drop-ins are masking `runtime.py` settings.

## Open5GS Core Unhealthy

- Inspect the specific failing container (`docker ps -a`, `docker logs`) for exit codes or OOM events. Check N2, N3, N4, and N6 independently.
- If `mongo` fails on Linux 7.0+ kernels due to TCMalloc `rseq` allocation, verify `GLIBC_TUNABLES=glibc.pthread.rseq=1` is present in the rendered `compose.json` (see [Hardware Notes](reference/hardware-notes.md#host-os-and-kernel-compatibility-notes)).

## UE Shown Stale or Disconnected

- Compare the current gNB process generation ID, RAN context timestamp, Open5GS PDU session, and UE probe status in Spark Platform. A session recorded prior to a gNB restart remains historical until fresh correlation evidence arrives after restart.

## RF Errors (`underflow` / `late`) or Low Throughput

- Verify `aoc-v2-cpu-latency.service` is `active` and confirm `realtime.conf` CPU affinity isolation is applied if co-located GPU/CPU workloads run on Spark (see [Ports & Runtime](reference/ports-and-runtime.md)).
- Check persisted B210 gains and MCS caps in [Network & RF Profile](reference/network-and-rf-profile.md), inspect antenna/attenuator seating, adjust one radio variable at a time with a backup, and re-verify under matching physical conditions.
