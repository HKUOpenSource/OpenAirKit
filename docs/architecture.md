# Architecture

[简体中文](architecture.zh-CN.md)

## Product boundary

Agentic-OCUDU provides one reproducible 5G SA data network with decoupled
management consoles at both ends. OCUDU supplies the RAN and Open5GS supplies
the 5G core. The Spark Platform observes and operates the base station. The
Jetson Console observes and operates the UE modem. IMS, SIP and voice services
are outside the current product boundary.

## Three-plane overview

```text
Jetson Console (127.0.0.1:8878) -> RM520N-GL modem -> B210 / OCUDU gNB -> Open5GS -> external DN
        |                                                     |
[UE DIY AI Headroom]                          127.0.0.1:8879 (JSON metrics, root-only nftables guard)
(Jetson Orin Compute)                                         |
                                                Spark Platform (127.0.0.1:8877)
                                                              |
                                               [gNB DIY AI Headroom]
                                               (DGX Spark, 8000-8002 free)
```

1. **5G SA Radio & Core Plane**: OCUDU gNB (`B210`, Band `n78`) and Open5GS 5GC
   (`12` containers + `ext-DN`) carry the data plane and follow [Hardware & Topology](hardware-and-topology.md).
2. **Local Management & Self-Recovery Plane**: **Spark Platform** (`0.2.1`) and
   **Jetson Console** (`0.6.2`) track only local host/device state, verify
   evidence quality, and perform bounded lifecycle, failover and recovery tasks.
3. **Reserved Dual-End AI Compute & Extension Plane**: No built-in AI models
   are shipped in this repository today. Instead, **DGX Spark** and **Jetson Orin**
   reserve local compute capacity at both ends while port isolation (`8879`
   keeping `8000–8002` free), real-time CPU pinning (`aoc-v2-cpu-latency`) and
   authenticated REST/SSE endpoints allow custom DIY AI modules to integrate
   cleanly. See [DIY AI Customization](ai-customization.md).

## Component ownership

| Component | Owns | Must not own |
| --- | --- | --- |
| Jetson Console (`0.6.2`) | Modem lock, bounded AT workflow, owned protocol-186 routes, UE state, `127.0.0.1:8878` | RAN/core lifecycle or arbitrary shell commands |
| Spark Platform (`0.2.1`) | Host/RAN/core evidence, history, events, bounded stack tasks, `127.0.0.1:8877` | Modem control or UE-only facts |
| OCUDU stack | B210 (`rx_gain=54`, `tx_gain=80`, `pusch.max_ue_mcs=24`), cell configuration, NGAP, `127.0.0.1:8879` metrics, `aoc-v2-cpu-latency` | Web sessions or platform data |
| Open5GS stack | Registration, PDU session, policy, N3/N4/N6 (`aoc-v2-open5gs-core`), MongoDB (`GLIBC_TUNABLES` on 7.0+ kernels) | RAN hardware or UI state |

## Runtime, UI and privilege boundaries

- **Shared UI boundary**: Both React consoles consume [`packages/console-ui`](../packages/console-ui/README.md) (`Astryx Core`, `Charts`, `Neutral` theme, and `UIProvider`) and track only local device/session state without introducing a global fleet state layer.
- **Privilege isolation**: Each web service (`aoc-web` on Spark, `aoc-v2-jetson-web` on Jetson) runs unprivileged without Docker socket or serial hardware access. Root-only control actions enter either through the local device socket (`aoc-control` / `aoc-v2-jetson-device`) or through `/usr/local/sbin/aoc-maintain` (`deploy/maintenance/`), which enforces SHA-256 approved archives and exact `NOPASSWD: NOSETENV` action allowlists.
- **Loopback port isolation**: Spark uses `127.0.0.1:8877`, Jetson uses `127.0.0.1:8878`, and OCUDU JSON remote-control WebSocket uses `127.0.0.1:8879` guarded by `aoc-v2-metrics-guard.service` (`table inet aoc_v2_metrics_guard` rejecting `skuid != 0`), avoiding `127.0.0.1:8000–8002` co-located inference workloads on DGX Spark.
- **Host/USB adaptation**: Spark's `collector.py::bridge_interface()` resolves the Docker bridge interface dynamically from `docker network inspect` (handling `br-<id12>` bridges as well as named bridges), while `deploy/spark/stack/` manages `/dev/cpu_dma_latency` (`aoc-v2-cpu-latency.service`) and kernel 7.0+ MongoDB allocator compatibility (`GLIBC_TUNABLES=glibc.pthread.rseq=1`). Jetson `hardware.py::discover()` validates Quectel RM520N USB interfaces across supported RNDIS (`00/01` -> AT `04`) and ECM `cdc_ether` (`04` or `0a` -> AT `02`) topologies before opening a serial port.
- **Opt-in Jetson boot coordinator**: When explicitly installed, `deploy/jetson/boot_connect.py` sits outside the immutable application release, verifies pinned hashes in `/etc/aoc-v2-jetson/boot.json`, gates device startup on USB/Wi-Fi/Tailscale readiness, and schedules at most one standard setup cycle per boot without storing SIM credentials.

## Network contract

The shared contract is versioned in `config/network-contract.json`. The current
deployment uses PLMN `460/03`, DNN `oai`, one IPv4 data PDU and the configured
`10.0.0.0/24` UE pool. Site-specific addresses and credentials stay outside
the repository.

## State semantics

Evidence quality and business health are independent. `ok`, `stale`,
`unavailable` and `unsupported` describe whether a value can be trusted.
Running, healthy and connected describe operational state. A UE is connected
only when fresh registration, PDU, address-pool, RAN-context and user-plane
evidence agree. Historical logs, an assigned IP or one ping cannot establish
current connectivity.

Collectors preserve source time and process generation. Restarts, log rotation
and counter resets create a new observation interval, preventing old devices,
false zero traffic or artificial rate spikes.
