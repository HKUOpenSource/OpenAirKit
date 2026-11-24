# Spark Setup

[简体中文](setup-bs-spark.zh-CN.md)

This guide covers installing **Spark Platform** and the **OCUDU + Open5GS**
base-station stack on **DGX Spark**. For hardware BOM, port tables, and kernel
notes, see [Hardware & Topology](hardware-and-topology.md) and
[Ports & Runtime](reference/ports-and-runtime.md).

## Prerequisites

- **Host**: DGX Spark (ARM64, Ubuntu 24.04, Python 3.12, `systemd`, Docker Engine with Compose).
- **SDR**: Ettus **USRP B210** connected directly to a native USB 3.0 port.
- **Ports**: Ensure loopback ports `8877` (Spark Platform) and `8879` (OCUDU JSON metrics) are free; ports `8000–8002` remain untouched for co-located AI inference workloads.
- **Locked build inputs**: Verify Open5GS digests (`stacks/open5gs/artifacts.lock.json`), Open5GS revisions (`stacks/open5gs/sources.lock.json`), OCUDU revision (`config/upstreams.json`), and site contract (`config/network-contract.json`). Keep subscriber credentials in protected deployment storage outside Git.

## 1. Install Spark Platform

Build the ARM64 archive with `make build-spark-release`, transfer and extract it
on Spark, then run verification, host checks, and installation (a fresh install
prompts for a Web Console password of at least 12 characters, stored hashed in
`/etc/aoc-monitor/auth.json`):

```sh
python3 -I -B install.py verify --path .
python3 -I -B install.py check-host --path .
sudo python3 -I -B install.py install --path .
```

The installer deploys into `/opt/agentic-ocudu/monitor` with
`aoc-control.service`, `aoc-observe.service`, and `aoc-monitor-web.service`
disabled at boot. Installing the platform leaves any running radio/core stack
untouched.

## 2. Install the 5G SA Protocol Stack

Follow [Spark Stack Deployment](../deploy/spark/stack/README.md) to build OCUDU
and Open5GS, render and provision a private authenticated N6 core bundle, and
fresh-install `aoc-v2-core.service`, `aoc-v2-radio.service`,
`aoc-v2-cpu-latency.service`, and `/usr/local/bin/aoc-v2ctl`.

To enable guarded gNB telemetry and protect real-time scheduling alongside
co-located workloads:

1. Run `sudo python3 scripts/spark/enable_radio_json_metrics.py` to activate root-only loopback telemetry on `127.0.0.1:8879` (`aoc-v2-metrics-guard.service`).
2. Keep `aoc-v2-cpu-latency.service` enabled alongside `aoc-v2-radio.service`, and configure `realtime.conf` (`CPUAffinity`, `LimitRTPRIO=99`) when sharing Spark with heavy GPU/CPU inference jobs (see [Ports & Runtime](reference/ports-and-runtime.md)).

## 3. Optional Operator Shortcuts & Verification

- To enable passwordless `~/aoc-ops/spark/` shortcuts, configure `/usr/local/sbin/aoc-maintain` via [Maintenance Helper](../deploy/maintenance/README.md) and install the lifecycle scripts from [Spark Operations](spark-operations.md).
- Forward `127.0.0.1:8877` over SSH and confirm all 12 core containers, active gNB generation, N2 NG Setup, `8879` WebSocket metrics, and bridge counters report healthy. Complete end-to-end data-path verification using a connected UE on Jetson.
