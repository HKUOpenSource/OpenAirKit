# Product Roadmap

[简体中文](roadmap.zh-CN.md)

This roadmap tracks capability milestones across the 5G SA stack, dual-end
management consoles, and future DIY AI ecosystem. Items marked completed are
backed by implemented source code, automated tests, and verified hardware
baselines (see [Acceptance baselines](acceptance/README.md)).

## Scope Invariants

- Single-stack **5G SA data network**: **OCUDU** RAN + **Open5GS** 5GC (`DNN=oai`, IPv4 pool `10.0.0.0/24`, `5QI=9`).
- **Independent lifecycle**: Spark Platform and Jetson Console install, upgrade, stop, and roll back separately on local host state only.
- **Evidence-driven health**: Stale values, assigned IPv4 addresses, or single pings never mark a UE connected without current SIM, registration, PDU, RAN, and bound data-probe agreement.
- IMS, SIP, voice services, and active throughput gates remain outside the current product scope.

## Milestone 1 — Reproducible 5G SA Stack (`Completed`)

- [x] Pinned ARM64 **OCUDU** gNB build, B210 USB 3.0 probe, and real-time latency clamping (`aoc-v2-cpu-latency`, `rx_gain=54`, `tx_gain=80`, `pusch.max_ue_mcs=24`).
- [x] Pinned **Open5GS 2.8.0** + **MongoDB 8.0.30** container builds, `GLIBC_TUNABLES` Linux 7.0+ kernel compatibility, and independent per-UE subscriber provisioning (`stacks/open5gs/subscriber.py`).
- [x] Standalone `aoc-v2ctl` lifecycle controller (`preflight`, `prepare`, `start`, `status`, `stop`) verifying SCTP + N2 NG Setup and clean failure retention.
- [x] Verified multi-UE 5G AKA authentication, SQN resynchronization, AMF recovery, and simultaneous dual-UE scheduling.

## Milestone 2 — Spark Platform `0.2.1` (`Completed`)

- [x] Unprivileged FastAPI + React/TypeScript (Astryx UI) console on `127.0.0.1:8877` with SQLite metric retention (schema 6 index) and persistent SSE live streams.
- [x] Guarded OCUDU JSON metrics on `ws://127.0.0.1:8879` (`aoc-v2-metrics-guard` nftables), keeping `127.0.0.1:8000–8002` clear for co-located AI inference workloads.
- [x] Dynamic Docker bridge discovery (`collector.py::bridge_interface()`), Open5GS NF/N2/N3/N4/N6 telemetry, evidence-based UE device correlation, and bounded Operations audit log.
- [x] Offline ARM64 installer, rollback, and verified multi-host hardware operation.

## Milestone 3 — Jetson Console `0.6.2` & Self-Recovery (`In Progress`)

- [x] RM520N-GL USB topology discovery covering both RNDIS (`00/01` -> AT `04`) and ECM `cdc_ether` (`04` or `0a` -> AT `02`) mounted via Jetson Orin M.2 carrier boards.
- [x] Exclusive serial locking, bounded Device Setup preview/baseline readback, and schema 3 separation of network, selection, diagnostics, management, and recovery policies.
- [x] Dual-path protocol-186 routing failover (Wi-Fi fallback metric `5` <-> cellular preference metric `10`) with independent `management_protected` checks and bounded `120 s` wait / `300 s` cooldown auto-recovery.
- [x] Opt-in cold-boot coordinator (`boot_connect.py`) verified across unattended hardware cold reboots.
- [ ] Expanded automated fault-matrix replay (serial contention, interface rename races, registration/PDU split, session expiry) and post-layout-refactor ARM64 reinstall gate.

## Milestone 4 — Community DIY AI Ecosystem (`Planned`)

- [x] Documentation baseline for dual-end compute headroom and REST/SSE integration boundaries ([DIY AI Customization](ai-customization.md)).
- [ ] Example reference consumers on DGX Spark (`127.0.0.1:8000–8002`) subscribing to Spark SSE and events.
- [ ] Example edge consumers on Jetson Orin adapting local vs. 5G workload decisions via `/api/v1/status` and `/api/v1/events/stream`.
