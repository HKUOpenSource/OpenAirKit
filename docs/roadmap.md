# Product Roadmap

[简体中文](roadmap.zh-CN.md)

This roadmap tracks capability milestones across the 5G SA protocol stack,
dual-end management consoles, and the upcoming **Open AI-RAN Extension
Ecosystem**. Completed milestones reflect verified source implementations,
automated test suites, and hardware acceptance baselines (see
[Acceptance Baselines](acceptance/README.md)).

## Architectural Invariants

- **Single-stack 5G SA IPv4 data network**: **OCUDU** RAN + **Open5GS** 5GC (see [Network & RF Profile](reference/network-and-rf-profile.md)).
- **Independent lifecycle**: Spark Platform and Jetson Console install, upgrade, stop, and roll back separately on strictly local host state.
- **Freshness-validated connectivity**: Connected status requires consistency across valid USIM readiness, NR SA registration, active IPv4 PDU, RAN context, and bound user-plane probes.

## Milestone 1 — Reproducible 5G SA Stack (`Completed`)

- [x] Pinned ARM64 **OCUDU** gNB build, USRP B210 probe, and real-time CPU latency protection (`aoc-v2ctl` lifecycle controller).
- [x] Pinned **Open5GS** + **MongoDB** ARM64 container build and verification pipeline with per-UE subscriber provisioning (`stacks/open5gs/subscriber.py`).
- [x] Automated N2 NG Setup readiness check on startup with failure-preserving diagnostics.
- [x] Hardware-verified multi-UE 5G AKA authentication, SQN resynchronization, AMF recovery, and concurrent multi-UE scheduling.

## Milestone 2 — Spark Platform (`Completed`)

- [x] Unprivileged FastAPI + Astryx React console on `127.0.0.1:8877` with indexed SQLite metric history and persistent SSE telemetry streams.
- [x] Guarded OCUDU JSON telemetry on `127.0.0.1:8879`, keeping `127.0.0.1:8000–8002` unallocated for co-located AI inference workloads.
- [x] Dynamic Open5GS Docker bridge discovery, NF/N2/N3/N4/N6 telemetry, evidence-correlated UE state, and bounded Operations audit trail.
- [x] Offline ARM64 installer, rollback workflow, and multi-host hardware verification.

## Milestone 3 — Jetson Console & Self-Recovery (`In Progress`)

- [x] Quectel RM520N-GL USB topology discovery across RNDIS and ECM `cdc_ether` layouts on Jetson Orin M.2 carrier boards.
- [x] Exclusive AT serial locking, Device Setup configuration previews and baseline readback, and separated network/selection/diagnostic/recovery policy blocks.
- [x] Dual-path IPv4 route failover (`Wi-Fi` fallback <-> `cellular` preference), `management_protected` verification, and bounded automatic recovery.
- [x] Opt-in cold-boot coordinator (`boot_connect.py`) verified across unattended cold reboots.
- [ ] Expanded automated fault-matrix replay and post-refactor ARM64 install/rollback regression gate.

## Milestone 4 — Open AI-RAN Extension Ecosystem (`Planned`)

- [x] Dual-end dedicated AI compute isolation and authenticated REST/SSE integration specification ([AI Extensibility Guide](ai-customization.md)).
- [ ] Reference **DGX Spark** (`127.0.0.1:8000–8002`) inference pipelines consuming Spark SSE streams and events.
- [ ] Reference **Jetson Orin** edge consumers orchestrating local vs. 5G-offloaded inference via Jetson Console telemetry.
