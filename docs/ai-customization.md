# Dual-End AI Customization and Extension Guide

[简体中文](ai-customization.zh-CN.md)

## Current Scope and Hardware Intent

> [!IMPORTANT]
> **Built-in AI modules are not yet implemented in this repository.**
> Today, Agentic-OCUDU ships the reproducible 5G SA communication stack
> (OCUDU + Open5GS), two decoupled management platforms (**Spark Platform** and
> **Jetson Console**), structured telemetry streams, bounded control endpoints,
> and host-level resource isolation.
>
> **DGX Spark** (gNB/Core side) and **Jetson Orin** (UE side) were specifically
> chosen to reserve local compute capacity at both ends so developers and
> researchers can DIY and deploy custom AI capabilities alongside the 5G stack.

## Design Principles for Custom AI Modules

Any user-developed AI module (inference service, anomaly detector, closed-loop
scheduler advisor, or ops agent) should preserve the platform's boundaries:

1. **Local-state autonomy**:
   - Modules on **DGX Spark** consume only base-station/core telemetry and act on Spark-local controls.
   - Modules on **Jetson Orin** consume only UE-local telemetry and act on Jetson-local controls.
   - Do not build a shared global control layer that tightly couples device recovery state across hosts.
2. **Evidence freshness before action**:
   - Both consoles attach source timestamps and evidence quality (`ok`, `stale`, `unavailable`, `unsupported`) to state snapshots. Never trigger automated changes from `stale` or `unavailable` snapshots.
3. **Bounded execution and hardware exclusivity**:
   - Route operational actions through authenticated console APIs (`/api/v1/control` on Spark, `/api/v1/jobs` and `/api/v1/maintenance` on Jetson) rather than bypassing serial locks or issuing raw Docker mutations.

## Compute, Port and Real-Time Isolation

### gNB / Core Side (`DGX Spark`)

- **Inference port space (`127.0.0.1:8000–8002`) is free**:
  OCUDU's loopback JSON remote-control metrics port was deliberately moved to `127.0.0.1:8879` so co-located inference engines (such as local LLM/vLLM containers) can occupy `8000–8002` without collision.
- **Port `8879` guard**:
  `aoc-v2-metrics-guard.service` applies `table inet aoc_v2_metrics_guard` to allow only `uid == 0` clients on `ws://127.0.0.1:8879`. Unprivileged AI services should subscribe to **Spark Platform** (`127.0.0.1:8877`) instead of opening `8879` directly.
- **Protecting real-time B210/OCUDU timing**:
  Keep `aoc-v2-cpu-latency.service` (`/dev/cpu_dma_latency=0`) enabled and configure CPU isolation (`systemd/aoc-v2-radio.service.d/realtime.conf.example` with `CPUAffinity` and `LimitRTPRIO=99`) before running heavy CPU/GPU workloads on Spark, preventing USB 3.0 underflows or late frames.

### UE Side (`Jetson Orin`)

- **Exclusive modem serial lock**:
  `aoc-v2-jetson-device.service` guards AT serial access with `/var/lib/agentic-ocudu/v2-ue/serial.lock`. Custom UE-side AI services must query Jetson Console APIs (`127.0.0.1:8878`) or enter maintenance mode (`POST /api/v1/maintenance`) before any external modem access.
- **Management routing preservation**:
  Do not alter protocol-186 defaults (Wi-Fi fallback metric `5`, cellular metric `10`) outside Jetson Console so SSH/Tailscale access remains protected even if a custom AI experiment interrupts cellular connectivity.

## Telemetry and Control Integration Surfaces

### gNB & Core Side — Spark Platform (`127.0.0.1:8877`)

| Direction | Endpoint | Purpose for DIY AI Modules |
| --- | --- | --- |
| Auth | `POST /api/v1/login`, `GET /api/v1/session`, `POST /api/v1/logout` | Session cookie + CSRF token for authenticated reads and controls |
| Live State | `GET /api/v1/snapshot`, `GET /api/v1/stream` (SSE) | Poll or subscribe in real time to host, B210, gNB, N2, Open5GS NFs, interfaces and devices |
| Metrics & History | `GET /api/v1/devices`, `GET /api/v1/devices/{identifier}`, `GET /api/v1/devices/{identifier}/metrics`, `GET /api/v1/components/{identifier}/metrics`, `GET /api/v1/history`, `GET /api/v1/history/catalog` | Time-series KPI inputs for anomaly detection, forecasting or RL/agent context |
| Events & Diagnostics | `GET /api/v1/events`, `GET /api/v1/events/kinds`, `GET /api/v1/diagnostics` | Structured fault history and subsystem health diagnostics |
| Bounded Control & Audit | `GET/POST /api/v1/control`, `GET /api/v1/control/{identifier}`, `POST /api/v1/control/{identifier}/cancel`, `GET /api/v1/audit` | Execute allow-listed lifecycle tasks with concurrency locks and persistent audit trails |

### UE Side — Jetson Console (`127.0.0.1:8878`)

| Direction | Endpoint | Purpose for DIY AI Modules |
| --- | --- | --- |
| Auth | `POST /api/v1/auth/login`, `GET /api/v1/auth/session`, `POST /api/v1/auth/logout` | Session cookie + CSRF token for local UE automation |
| Live State | `GET /api/v1/status`, `GET /api/v1/config`, `GET /api/v1/events/stream` (SSE) | Poll or subscribe to SIM, cell camping, NR SA registration, PDU, routing and recovery state |
| Metrics & Diagnostics | `GET /api/v1/metrics`, `GET /api/v1/history`, `GET /api/v1/diagnostics` | Passive RX/TX rate history, bound probe latencies, and task execution history |
| Bounded Actions | `GET/POST /api/v1/jobs`, `GET /api/v1/jobs/{identifier}`, `POST /api/v1/jobs/{identifier}/run`, `POST /api/v1/jobs/{identifier}/cancel`, `POST /api/v1/maintenance` | Trigger bounded Device Setup, Recover or Maintenance transitions safely |

## Recommended DIY Integration Loop

```mermaid
flowchart LR
  OBS["Subscribe via REST / SSE (8877 or 8878)"] --> VAL["Check Freshness & Evidence Quality"]
  VAL --> INF["Run Local Model / Agent on Spark or Jetson Compute"]
  INF --> ACT["Call Bounded API (/api/v1/control or /api/v1/jobs)"]
  ACT --> AUD["Verify Outcome in /api/v1/audit or /api/v1/history"]
```

### Example DIY Directions (Not Bundled Today)

Once your 5G SA baseline is verified via the [Quickstart](quickstart.md), common DIY extensions you can build independently on each host include:

- **On DGX Spark (gNB/Core side)**:
  - An LLM-assisted operations diagnostic agent co-located on `8000–8002` that reads Spark SSE/history/events and explains N2/N3 anomalies or RF degradation.
  - Custom ML telemetry pipelines consuming `/api/v1/devices/{identifier}/metrics` and `/api/v1/components/{identifier}/metrics` for multi-UE throughput/MCS trend analysis.
- **On Jetson Orin (UE side)**:
  - Edge AI applications that adapt inference/offloading behavior (local vs. Spark over 5G vs. Wi-Fi fallback) based on real-time `/api/v1/status` and `/api/v1/events/stream` link quality.
  - Custom recovery policies layered cleanly on top of `/api/v1/jobs` while honoring cooldowns and management protection.
