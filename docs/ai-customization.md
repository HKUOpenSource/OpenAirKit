# Dual-End Programmable AI Extensibility Guide

[简体中文](ai-customization.zh-CN.md)

**DGX Spark** (RAN/Core endpoint) and **Jetson Orin** (UE endpoint) are
provisioned to reserve dedicated GPU and edge compute capacity at both ends of
the 5G SA link. While turnkey built-in AI agents are scheduled for a future
milestone, the platform already enforces compute isolation, real-time RAN
scheduling protection, and authenticated local APIs so researchers and system
developers can deploy **custom AI workloads** and **user-defined AI pipelines**
cleanly alongside the 5G stack.

## Architectural Principles for Custom AI Workloads

1. **Endpoint autonomy**: Workloads on **DGX Spark** subscribe to RAN/core
   telemetry and invoke bounded controls locally on Spark (`127.0.0.1:8877`);
   workloads on **Jetson Orin** consume UE telemetry and trigger local device
   jobs on Jetson (`127.0.0.1:8878`). Keep inference loops host-local without
   introducing cross-host control coupling.
2. **Freshness-gated execution**: Evaluate source timestamps and telemetry
   freshness state (`ok`, `stale`, `unavailable`, `unsupported`) before running
   closed-loop actions; authorize state-changing operations only when snapshot
   freshness is `ok`.
3. **Bounded control and lock safety**: Dispatch mutations exclusively through
   authenticated REST APIs rather than bypassing the Jetson AT serial lock or
   modifying Open5GS containers out of band.

## Compute, Port, and Real-Time Isolation

- **DGX Spark (gNB / Core side)**:
  - **Reserved inference ports (`8000–8002`)**: OCUDU JSON metrics bind to
    `127.0.0.1:8879` behind `aoc-v2-metrics-guard.service`, leaving
    `127.0.0.1:8000–8002` unallocated for co-located LLM/vLLM or ML inference
    containers. Unprivileged AI services integrate with **Spark Console** via
    `127.0.0.1:8877`.
  - **Real-time radio protection**: Retain `aoc-v2-cpu-latency.service` and
    apply CPU core pinning (`realtime.conf`) when scheduling compute-intensive
    inference jobs so OCUDU real-time threads avoid USB 3.0 underflows or late
    frames.
- **Jetson Orin (UE side)**:
  - **Exclusive serial & route protection**: User-defined UE AI services query
    link telemetry and submit workflows through **Jetson Console**
    (`127.0.0.1:8878`), preserving `/var/lib/agentic-ocudu/v2-ue/serial.lock`
    and protocol-186 out-of-band Wi-Fi protection.

Authoritative port allocations, real-time guards, and lock paths are specified
in [Ports & Runtime Reference](reference/ports-and-runtime.md).

## Closed-Loop Integration Pattern & API Surface

```mermaid
flowchart LR
  OBS["Subscribe via REST / SSE"] --> VAL["Gate on Telemetry Freshness"]
  VAL --> INF["Execute Local Inference (Spark / Jetson)"]
  INF --> ACT["Invoke Bounded Control / Job API"]
  ACT --> AUD["Audit Execution & History"]
```

Authenticated telemetry feeds (`GET /api/v1/stream`, `GET /api/v1/snapshot`,
`GET /api/v1/status`, `GET /api/v1/events/stream`) and bounded control endpoints
(`POST /api/v1/control`, `POST /api/v1/jobs`, `POST /api/v1/maintenance`) are
specified in the [REST & SSE API Reference](reference/api-reference.md).

### Target AI-RAN Extension Workloads

- **RAN / Core side (DGX Spark)**: Deploy an LLM operations or diagnostics
  pipeline on `8000–8002` consuming Spark SSE streams, subsystem events, and
  KPI time series (`devices/{identifier}/metrics`,
  `components/{identifier}/metrics`), or implement RAN anomaly detection and
  multi-UE scheduling analytics.
- **UE edge side (Jetson Orin)**: Build link-aware edge AI applications that
  dynamically partition inference between on-device Orin execution and 5G-offloaded
  compute on Spark using `/api/v1/status` and `/api/v1/events/stream`, or layer
  domain-specific recovery policies over `/api/v1/jobs`.
