# Documentation

[简体中文](README.zh-CN.md)

This directory is the canonical documentation source for the platform,
organized from high-level architecture down to actionable guides and single-source
technical references.

## Overview & Architecture (`L1`)

| Need | Guide |
| --- | --- |
| Understand planes, ownership, isolation, and evidence semantics | [Architecture](architecture.md) |
| Review hardware BOM, Waveshare M.2 carrier, wiring topology, and OS prereqs | [Hardware & Topology](hardware-and-topology.md) |

## Setup, Operations & Customization Guides (`L2`)

| Need | Guide |
| --- | --- |
| Follow the 0-to-1 cross-host bring-up path | [End-to-End Quickstart](quickstart.md) |
| Install Spark Platform and the base-station stack | [Spark Setup](setup-bs-spark.md) |
| Build and deploy the OCUDU + Open5GS stack bundle | [Spark Stack Deployment](../deploy/spark/stack/README.md) |
| Build and verify Open5GS ARM64 container images | [Open5GS ARM64 Build](../stacks/open5gs/build/README.md) |
| Provision an Open5GS subscriber and program 5G USIM cards | [SIM Provisioning & USIM Setup](sim-provisioning.md) |
| Install, commission, and configure boot connect on Jetson Console | [Jetson Setup](setup-ue-jetson.md) |
| Operate Spark Web Console and full-stack lifecycle controls | [Spark Operations](spark-operations.md) |
| Operate Jetson Web Console, routing failover, and self-recovery | [Jetson Operations](jetson-operations.md) |
| Configure optional passwordless restricted maintenance (`aoc-maintain`) | [Maintenance Helper](../deploy/maintenance/README.md) |
| Build custom AI extensions on reserved Spark & Jetson headroom | [DIY AI Customization](ai-customization.md) |
| Diagnose base-station or core issues | [Spark Troubleshooting](troubleshooting-bs-spark.md) |
| Diagnose UE, modem, or routing issues | [Jetson Troubleshooting](troubleshooting-ue-jetson.md) |

## Technical Reference & Appendices (`L3`)

| Topic | Reference |
| --- | --- |
| RF baseline (`n78`), Open5GS data profile (`DNN`/`PLMN`/`5QI`), and access policy | [Network & RF Profile](reference/network-and-rf-profile.md) |
| Loopback ports, real-time guards, routing metrics, recovery timers, and exit codes | [Ports & Runtime](reference/ports-and-runtime.md) |
| Authenticated REST and SSE endpoints for Spark Platform & Jetson Console | [REST & SSE API Reference](reference/api-reference.md) |
| RM520N-GL USB layouts, QMAP checks, kernel compatibility, and TB01 APDU tables | [Hardware & TB01 Notes](reference/hardware-notes.md) |
| Core 5G SA and platform terminology | [Glossary](reference/glossary.md) |

## Maintainer, Assets & Verification Baselines

| Need | Document |
| --- | --- |
| Build, package, and audit offline ARM64 releases | [Releasing](releasing.md) |
| Brand naming decoupling, Logo slots, hardware photos, and redaction rules | [Visual Assets & Brand Guide](assets/README.md) |
| Check product capability milestones | [Product Roadmap](roadmap.md) |
| Review redacted hardware verification baselines | [Verified Hardware Baselines](acceptance/README.md) |

English is the normative language for commands and UI labels; `.zh-CN.md`
provides matching Simplified Chinese guidance.
