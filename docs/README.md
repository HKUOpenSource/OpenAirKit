# Documentation

[简体中文](README.zh-CN.md)

This directory holds the canonical platform documentation, structured from
high-level architecture down to operational procedures and single-source
technical references.

## Overview & Architecture (`L1`)

| Need | Guide |
| --- | --- |
| Understand planes, component boundaries, isolation, and evidence semantics | [Architecture](architecture.md) |
| Review hardware BOM, Waveshare M.2 carrier, wiring topology, and OS prerequisites | [Hardware & Topology](hardware-and-topology.md) |

## Setup, Operations & Extensibility Guides (`L2`)

| Need | Guide |
| --- | --- |
| Execute the end-to-end multi-host deployment workflow | [End-to-End Quickstart](quickstart.md) |
| Install Spark Platform and the base-station stack | [Spark Setup](setup-bs-spark.md) |
| Build and deploy the OCUDU + Open5GS stack bundle | [Spark Stack Deployment](../deploy/spark/stack/README.md) |
| Build and verify Open5GS ARM64 container images | [Open5GS ARM64 Build](../stacks/open5gs/build/README.md) |
| Provision an Open5GS subscriber and program 5G USIM cards | [SIM Provisioning & USIM Setup](sim-provisioning.md) |
| Install, commission, and configure boot connect on Jetson Console | [Jetson Setup](setup-ue-jetson.md) |
| Operate Spark Web Console and full-stack lifecycle controls | [Spark Operations](spark-operations.md) |
| Operate Jetson Web Console, route failover, and bounded recovery | [Jetson Operations](jetson-operations.md) |
| Configure optional passwordless restricted maintenance (`aoc-maintain`) | [Maintenance Helper](../deploy/maintenance/README.md) |
| Integrate user-defined AI pipelines on reserved Spark & Jetson compute resources | [AI Extensibility Guide](ai-customization.md) |
| Diagnose base-station or core issues | [Spark Troubleshooting](troubleshooting-bs-spark.md) |
| Diagnose UE, modem, or routing issues | [Jetson Troubleshooting](troubleshooting-ue-jetson.md) |

## Technical Reference & Appendices (`L3`)

| Topic | Reference |
| --- | --- |
| RF baseline (`n78`), Open5GS data profile (`DNN`/`PLMN`/`5QI`), and access policy | [Network & RF Profile](reference/network-and-rf-profile.md) |
| Loopback ports, real-time guards, routing metrics, recovery budgets, and exit codes | [Ports & Runtime](reference/ports-and-runtime.md) |
| Authenticated REST and SSE endpoints for Spark Platform & Jetson Console | [REST & SSE API Reference](reference/api-reference.md) |
| RM520N-GL USB layouts, QMAP checks, kernel compatibility, and TB01 APDU tables | [Hardware & TB01 Notes](reference/hardware-notes.md) |
| Core 5G SA and platform terminology | [Glossary](reference/glossary.md) |

## Maintainer, Assets & Verification Baselines

| Need | Document |
| --- | --- |
| Build, package, and audit offline ARM64 releases | [Releasing](releasing.md) |
| Review brand naming decoupling, logo assets, hardware photos, and redaction rules | [Visual Assets & Brand Guide](assets/README.md) |
| Track product capability milestones | [Product Roadmap](roadmap.md) |
| Review redacted hardware verification baselines | [Verified Hardware Baselines](acceptance/README.md) |

English is the normative reference for CLI flags and Web UI labels;
`.zh-CN.md` documents provide equivalent Simplified Chinese guidance.
