# Ports, Routing, Real-Time Isolation and Runtime Reference

[简体中文](ports-and-runtime.zh-CN.md)

This reference consolidates all loopback port assignments, host real-time and
hardware isolation mechanisms, Jetson routing and recovery budgets, and
lifecycle script exit codes.

## Loopback Service & Port Allocation

All platform web consoles and telemetry feeds bind strictly to `127.0.0.1` and
are accessed remotely via SSH port forwarding (`ssh -L ...`).

| Port | Owner / Service | Access Policy & Isolation |
| --- | --- | --- |
| `127.0.0.1:8877` | Spark Platform (`aoc-monitor-web.service`) | Authenticated Astryx Web Console, REST API, and SSE stream (`/api/v1/stream`) |
| `127.0.0.1:8878` | Jetson Console (`aoc-v2-jetson-web.service`) | Authenticated Astryx Web Console, REST API, and SSE stream (`/api/v1/events/stream`) |
| `127.0.0.1:8879` | OCUDU gNB JSON metrics (`ws://127.0.0.1:8879`) | Root-only loopback firewall guard (`aoc-v2-metrics-guard.service`) consumed by `aoc-observe.service` |
| `127.0.0.1:8000–8002` | Reserved Inference Ports on **DGX Spark** | Unallocated by the 5G stack so co-located AI inference containers (such as vLLM) execute without port contention |

## Host Real-Time & Hardware Isolation Assets

| Component / Host | Mechanism | Purpose |
| --- | --- | --- |
| Spark RAN | `aoc-v2-cpu-latency.service` (`PartOf=aoc-v2-radio.service`) | Holds `/dev/cpu_dma_latency=0` while gNB runs to prevent deep CPU C-state wakeups |
| Spark RAN (optional) | `deploy/spark/stack/systemd/aoc-v2-radio.service.d/realtime.conf.example` | Optional `CPUAffinity` and `LimitRTPRIO=99` drop-in isolating gNB threads from co-located GPU/CPU workloads |
| Jetson UE | `/var/lib/agentic-ocudu/v2-ue/serial.lock` | Exclusive lock protecting AT serial ownership under `aoc-v2-jetson-device.service` |
| Jetson Boot (opt-in) | `/opt/agentic-ocudu/jetson/boot_connect.py` + `aoc-v2-jetson-boot.service` | Verifies release/config SHA-256 against `/etc/aoc-v2-jetson/boot.json`, gates on USB/Wi-Fi/`tailscale0`, runs at most once per Linux `boot_id`, and writes redacted progress to `/var/lib/aoc-v2-jetson-boot/public/status.json` |

## Jetson Routing & Self-Recovery Thresholds

| Parameter | Value / Behavior |
| --- | --- |
| Owned default routes | Kernel protocol `186`: `metric 5` = Wi-Fi fallback default route; `metric 10` = verified cellular preferred default route |
| Foreign route requirement | All administrator or NetworkManager default routes must maintain metrics strictly `> 10` |
| Host-bound diagnostic routes | Explicit host routes to UPF, `ext-DN`, and the public probe target stay bound to the cellular interface during Wi-Fi fallback |
| Probe interval & validity window | Standard sampling cadence `10 s`; telemetry stale threshold `20 s` |
| Cellular preference trigger | Requires `2` consecutive current successful probe samples (including the public target) |
| Wi-Fi fallback trigger | Triggers on `2` consecutive probe failures, stale telemetry (`> 20 s`), or loss of registration/PDU/interface |
| Automatic recovery budget | Active only after successful user Setup/Recover: `120 s` natural wait -> max `2` recovery jobs (`>= 300 s` cooldown), max `1` reconnect per job |

## Lifecycle CLI Timeouts & Exit Codes

Applies consistently to both `~/aoc-ops/spark/platformctl.py` and `~/aoc-ops/jetson/platformctl.py`:

| Property | Contract |
| --- | --- |
| Maintenance helper timeout | `330 s` per `aoc-maintain` invocation |
| Health wait budget | `60 s` per stage startup/stop check; `10 s` graceful Web shutdown |
| Exit code `0` | Success (also returned by `status` when services are cleanly stopped) |
| Exit code `1` | Execution or verification failure |
| Exit code `2` | Invalid command arguments |
| Exit code `3` | User-level operation lock busy |
