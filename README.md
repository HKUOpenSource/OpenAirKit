<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/brand/logo-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="docs/assets/brand/logo-light.png">
  <img src="docs/assets/brand/logo-light.png" alt="OpenAirKit" width="540">
</picture>

<p><strong>Open-Source End-to-End 5G SA &amp; AI-RAN Experimental Platform</strong></p>

<p>
  <img alt="5G SA: OCUDU + Open5GS" src="https://img.shields.io/badge/5G_SA-OCUDU_%2B_Open5GS-brightgreen">
  <img alt="Spark Platform: 0.2.1" src="https://img.shields.io/badge/Spark_Platform-0.2.1-blue">
  <img alt="Jetson Console: 0.6.2" src="https://img.shields.io/badge/Jetson_Console-0.6.2-blue">
  <img alt="Host: ARM64 Linux" src="https://img.shields.io/badge/Host-ARM64_Linux-green">
</p>

<p>
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="docs/quickstart.md">Quickstart</a> ·
  <a href="docs/architecture.md">Architecture</a> ·
  <a href="docs/hardware-and-topology.md">Hardware</a> ·
  <a href="CONTRIBUTING.md">Contributing</a> ·
  <a href="docs/README.md">Docs</a>
</p>

</div>

**OpenAirKit** integrates a standardized ARM64 hardware testbed—**DGX Spark +
USRP B210 + Jetson Orin + Waveshare M.2 5G Carrier + Quectel RM520N-GL**—into a
reproducible **5G Standalone (SA)** IPv4 data network powered by **OCUDU**
(RAN) and **Open5GS** (5GC), paired with decoupled local management consoles at
both endpoints.

<p align="center">
  <img src="docs/assets/hardware/kit-overview.webp" alt="OpenAirKit 5G SA and AI-RAN hardware testbed" width="100%">
</p>

## Core Capabilities

- **Reproducible end-to-end bring-up**: Progress systematically from physical
  cabling and Open5GS container builds to 5G USIM provisioning and verified UE
  user-plane connectivity.
- **Decoupled local-first management**: Operate the base station (**Spark
  Platform**) and UE (**Jetson Console**) independently with live SSE
  telemetry, telemetry freshness gating, automated Wi-Fi/cellular route
  failover, and bounded self-recovery.
- **Programmable AI extensibility at both ends**: Selecting **DGX Spark** and
  **Jetson Orin** allocates dedicated AI compute capacity at both the RAN and UE
  endpoints, complemented by reserved inference ports and authenticated REST/SSE
  APIs for **custom AI workloads** and **user-defined AI pipelines**. *(Built-in
  AI modules are slated for a future milestone; see the
  [AI Extensibility Guide](docs/ai-customization.md).)*

## System Architecture

```mermaid
flowchart TB
  classDef hw fill:#f1f5f9,stroke:#475569,color:#0f172a
  classDef stack fill:#ecfdf5,stroke:#047857,color:#064e3b
  classDef mgmt fill:#eff6ff,stroke:#1d4ed8,color:#1e3a8a
  classDef ai fill:#fefce8,stroke:#a16207,stroke-dasharray:5 5,color:#713f12

  subgraph AI["Programmable AI Extension Layer (User-Defined Pipelines)"]
    direction LR
    JAI["Jetson Edge AI Runtime"]:::ai
    SAI["DGX Spark RAN-Side AI Runtime"]:::ai
  end

  subgraph MGMT["Local-First Management Plane"]
    direction LR
    JC["Jetson Console"]:::mgmt
    SP["Spark Platform"]:::mgmt
  end

  subgraph STACK["5G SA Protocol Plane"]
    direction LR
    RAN["OCUDU gNB"]:::stack
    CORE["Open5GS 5GC"]:::stack
    RAN -- "N2 / N3" --> CORE
  end

  subgraph HW["ARM64 Hardware Stack"]
    direction LR
    UEHW["Jetson Orin + RM520N-GL"]:::hw
    BSHW["DGX Spark +<br/>USRP B210"]:::hw
    UEHW <== "5G NR SA" ==> BSHW
  end

  UEHW --- JC
  BSHW --- RAN
  RAN -. "Metrics" .-> SP
  CORE -. "NF & Session State" .-> SP
  JC -. "REST / SSE" .- JAI
  SP -. "REST / SSE" .- SAI
```

## Platform Overview

<table>
  <tr>
    <td align="center" valign="bottom" width="20%"><img src="docs/assets/hardware/dgx-spark.webp" width="112" alt="DGX Spark" /><br/><sub><b>DGX Spark</b></sub></td>
    <td align="center" valign="bottom" width="20%"><img src="docs/assets/hardware/usrp-b210.webp" width="112" alt="USRP B210" /><br/><sub><b>USRP B210</b></sub></td>
    <td align="center" valign="bottom" width="20%"><img src="docs/assets/hardware/jetson-orin-nano.webp" width="112" alt="Jetson Orin Nano" /><br/><sub><b>Jetson Orin</b></sub></td>
    <td align="center" valign="bottom" width="20%"><img src="docs/assets/hardware/waveshare-m2-5g-carrier.webp" height="72" alt="Waveshare M.2 5G Carrier" /><br/><sub><b>M.2 5G Carrier</b></sub></td>
    <td align="center" valign="bottom" width="20%"><img src="docs/assets/hardware/quectel-rm520n-gl.webp" height="72" alt="Quectel RM520N-GL" /><br/><sub><b>RM520N-GL</b></sub></td>
  </tr>
</table>

| Component | Hardware / Software Role | Local Access | Reference |
| --- | --- | --- | --- |
| **Base Station & Core** | **DGX Spark** + **USRP B210** running **OCUDU** & **Open5GS** | `aoc-v2ctl` / `systemctl` | [Network & RF Profile](docs/reference/network-and-rf-profile.md) |
| **Spark Platform** | Base-station telemetry collector, Web UI & bounded executor (`apps/spark-platform/`) | `127.0.0.1:8877` | [Spark Operations](docs/spark-operations.md) |
| **UE Host & Modem** | **Jetson Orin** + **Waveshare M.2 5G Carrier** + **Quectel RM520N-GL** + 5G USIM | USB 3.0 + Wi-Fi management | [Hardware & Topology](docs/hardware-and-topology.md) |
| **Jetson Console** | UE modem supervision, route failover & bounded recovery (`apps/jetson-console/`) | `127.0.0.1:8878` | [Jetson Operations](docs/jetson-operations.md) |

Both consoles share `@aoc/console-ui` (`packages/console-ui/`), maintain
strictly local host state, and remain disabled at boot unless explicitly
configured.

## Documentation Map

| Category | Guides |
| --- | --- |
| **Start Here** | [Hardware & Topology](docs/hardware-and-topology.md) · [End-to-End Quickstart](docs/quickstart.md) · [Architecture](docs/architecture.md) |
| **Deployment & Provisioning** | [Spark Setup](docs/setup-bs-spark.md) · [Stack Deployment](deploy/spark/stack/README.md) · [SIM Provisioning](docs/sim-provisioning.md) · [Jetson Setup](docs/setup-ue-jetson.md) |
| **Operations & AI Extensibility** | [Spark Operations](docs/spark-operations.md) · [Jetson Operations](docs/jetson-operations.md) · [AI Extensibility Guide](docs/ai-customization.md) |
| **Troubleshooting** | [Spark Troubleshooting](docs/troubleshooting-bs-spark.md) · [Jetson Troubleshooting](docs/troubleshooting-ue-jetson.md) |
| **Technical Reference (`L3`)** | [Network & RF Profile](docs/reference/network-and-rf-profile.md) · [Ports & Runtime](docs/reference/ports-and-runtime.md) · [API Reference](docs/reference/api-reference.md) · [Hardware & TB01 Notes](docs/reference/hardware-notes.md) · [Glossary](docs/reference/glossary.md) |

See the [full documentation index](docs/README.md) for release engineering,
product roadmap milestones, and visual asset standards.

## Repository Layout

- `apps/spark-platform/`: Spark telemetry collector, FastAPI backend, and React UI.
- `apps/jetson-console/`: Jetson device executor, FastAPI backend, and React UI.
- `packages/console-ui/`: Shared Astryx Core, Charts, and Neutral theme components.
- `stacks/ocudu/` & `stacks/open5gs/`: RAN build inputs, Open5GS container builds, Compose rendering, and subscriber provisioning CLI.
- `deploy/`: Stack controller, platform installers, restricted maintenance helper, and optional Jetson boot coordinator.
- `scripts/` & `config/`: Release builders, metrics firewall guard, repository audits, and site network contracts.
- `docs/`: Paired English and Simplified Chinese documentation, reference appendices, and verified acceptance baselines.

## Build and Verify from Source

Requires Python `3.10–3.12` and Node.js `22`.

```sh
make install-dev BOOTSTRAP_PYTHON=python3.12
make check
```

Pass `VENV=local/dev-venv` to both targets when using a custom virtual
environment path. Review [Contributing](CONTRIBUTING.md),
[Security Policy](SECURITY.md), and [Releasing](docs/releasing.md) before
submitting changes or cutting release artifacts.
