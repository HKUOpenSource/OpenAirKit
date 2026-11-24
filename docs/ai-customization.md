# Dual-End AI Customization and Extension Guide

[简体中文](ai-customization.zh-CN.md)

**DGX Spark** (gNB/Core side) and **Jetson Orin** (UE side) were intentionally
selected to reserve GPU and edge compute capacity at both ends of the 5G SA
link. Built-in AI agents and models are planned for a future milestone; today the
platform provides dedicated compute headroom, real-time isolation, and
authenticated local APIs so developers and researchers can build and deploy DIY
AI modules cleanly alongside the radio and core stack.

## Design Principles for DIY AI Modules

1. **Local-host autonomy**: Modules on **DGX Spark** consume base-station/core
   telemetry and act on Spark controls (`127.0.0.1:8877`); modules on
   **Jetson Orin** consume UE telemetry and act on Jetson jobs
   (`127.0.0.1:8878`). Keep decision loops local without introducing shared
   cross-host control coupling.
2. **Freshness-gated inference**: Inspect source timestamps and evidence
   quality (`ok`, `stale`, `unavailable`, `unsupported`) before acting on a
   snapshot; trigger operational mutations only when quality is `ok`.
3. **Bounded execution & hardware isolation**: Issue mutations exclusively
   through authenticated REST endpoints rather than bypassing the Jetson AT
   serial lock or mutating Open5GS containers directly.

## Compute, Port and Real-Time Isolation

- **DGX Spark (gNB / Core side)**:
  - **Inference port headroom (`8000–8002`)**: OCUDU JSON metrics bind to `127.0.0.1:8879` behind `aoc-v2-metrics-guard.service`, leaving `127.0.0.1:8000–8002` free for co-located LLM/vLLM or ML inference containers. Unprivileged AI services consume Spark Platform (`127.0.0.1:8877`).
  - **Real-time radio protection**: Retain `aoc-v2-cpu-latency.service` and configure CPU affinity (`realtime.conf`) when running heavy co-located inference jobs so OCUDU real-time threads never suffer USB 3.0 underflows or late frames.
- **Jetson Orin (UE side)**:
  - **Exclusive serial & route ownership**: Custom UE agents read telemetry and trigger workflows through Jetson Console (`127.0.0.1:8878`), preserving `/var/lib/agentic-ocudu/v2-ue/serial.lock` and protocol-186 Wi-Fi management protection.

Full port allocations, latency guards, and serial lock paths are detailed in
[Ports & Runtime Reference](reference/ports-and-runtime.md).

## Integration Loop & API Surface

```mermaid
flowchart LR
  OBS["Subscribe via REST / SSE"] --> VAL["Verify Evidence Quality"]
  VAL --> INF["Run Local Inference on Spark / Jetson"]
  INF --> ACT["Invoke Bounded Control / Job API"]
  ACT --> AUD["Inspect Audit / History Outcome"]
```

All authenticated telemetry streams (`GET /api/v1/stream`, `GET /api/v1/snapshot`,
`GET /api/v1/status`, `GET /api/v1/events/stream`) and bounded control actions
(`POST /api/v1/control`, `POST /api/v1/jobs`, `POST /api/v1/maintenance`) are
documented in the [REST & SSE API Reference](reference/api-reference.md).

### Research & Extension Directions

- **On DGX Spark (gNB/Core side)**: Co-locate an LLM ops/diagnostic agent on `8000–8002` consuming Spark SSE, events, and KPI time series (`devices/{identifier}/metrics`, `components/{identifier}/metrics`), or build RAN anomaly and multi-UE scheduling analyzers.
- **On Jetson Orin (UE side)**: Build link-aware edge inference applications that adapt local execution vs. 5G offloading to Spark using `/api/v1/status` and `/api/v1/events/stream`, or layer domain-specific recovery policies on top of `/api/v1/jobs`.
