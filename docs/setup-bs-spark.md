# Spark system setup

[简体中文](setup-bs-spark.zh-CN.md)

> [!TIP]
> For hardware BOM, port allocation (`8877`, `8879`, and keeping `8000–8002`
> free for DIY AI workloads) and the 0-to-1 bring-up order, start with
> [Hardware & Topology](hardware-and-topology.md) and the
> [End-to-End Quickstart](quickstart.md).

## Prerequisites

Use an ARM64 host with Ubuntu 24.04, Python 3.12, systemd, Docker Compose and a
supported B210 connected over USB 3. Confirm that ports `127.0.0.1:8877`
(Monitor Web) and `127.0.0.1:8879` (OCUDU loopback JSON metrics) are available.
Port `8879` avoids co-located services that commonly occupy `8000–8002` (such as
local vLLM containers on DGX Spark). The monitor, radio and core have separate
release and lifecycle boundaries.

Verify Open5GS image digests from `stacks/open5gs/artifacts.lock.json` and source
revisions from `stacks/open5gs/sources.lock.json`, the OCUDU revision from
`config/upstreams.json`, and site settings derived from
`config/network-contract.json`. Production subscriber material must be loaded
from the protected deployment state, never from the repository.

## Install the monitoring platform

Build with `make build-spark-release`, transfer the resulting ARM64 release,
then run its platform installer in preflight and install modes. The target is
`/opt/agentic-ocudu/monitor`; the three platform services (`aoc-control.service`,
`aoc-observe.service`, `aoc-monitor-web.service`) remain disabled at boot.
Installing the monitor does not start or restart the protocol stack.

From the unpacked Spark release, use the actual installer actions:

```sh
python3 -I -B install.py verify --path .
python3 -I -B install.py check-host --path .
sudo python3 -I -B install.py install --path .
```

After preparing the protocol stack, approve the matching
[maintenance bundle](../deploy/maintenance/README.md) (`/usr/local/sbin/aoc-maintain`)
and install the [Spark lifecycle scripts](spark-operations.md). Full-stack
startup and status check N2 independently from service process state.

## Prepare the protocol stack

Follow the [independent stack package guide](../deploy/spark/stack/README.md):
build the pinned radio artifacts, render/provision a private authenticated N6
bundle, then stage and verify with `deploy/spark/stack/package.py`. Its fresh-install
path supplies the V2 controller, `aoc-v2-core.service`, `aoc-v2-radio.service`
and `/usr/local/bin/aoc-v2ctl` without starting services; existing installations
are never overwritten.

The maintained runtime baseline reflects observed hardware tuning:

- **MongoDB kernel compatibility**: `stacks/open5gs/compose/render.py` sets
  `GLIBC_TUNABLES=glibc.pthread.rseq=1` on `mongo` for Linux 7.0+ kernels
  (tested on `7.0.0-1019-nvidia` with MongoDB `8.0.30`).
- **RF defaults**: `deploy/spark/stack/runtime.py` configures `tx_gain=80`,
  `rx_gain=54`, and `cell_cfg.pusch.max_ue_mcs=24`.
- **Low-latency and realtime helpers**: `deploy/spark/stack/libexec/aoc-v2-cpu-latency`,
  `aoc-v2-cpu-latency.service` (`PartOf=aoc-v2-radio.service`), drop-in
  `cpu-latency.conf`, and `realtime.conf.example` (`CPUAffinity`, `LimitRTPRIO=99`)
  prevent CPU C-state wakeups and contention with co-located workloads.
- **Migrated schema-2 vs fresh schema-3 `/opt/agentic-ocudu/v2/` layouts**:
  fresh installs use schema-3 (`systemd/`, strict unlisted-file checks); legacy
  migrated hosts carrying schema-2 manifests (`units/` and backup directories)
  must patch their live `runtime.py` in place and update `release.json` hashes
  rather than overwriting with schema-3 `runtime.py`.

`scripts/spark/enable_radio_json_metrics.py` supplies the guarded telemetry
transaction, migrating disabled or legacy `127.0.0.1:8001` configurations to
`127.0.0.1:8879` with `aoc-v2-metrics-guard.service` restricting access to
`uid == 0`. Validate B210 ownership, the core network, N2 and the `8879` loopback
metrics endpoint before accepting UE traffic. Local package tests do not certify
target installation or RF operation.

## Verify

Open `127.0.0.1:8877` through an SSH tunnel. Verify all 12 core containers, gNB
generation, N2, `127.0.0.1:8879` WebSocket metrics, dynamic bridge interface
counters, current UE context, active PDU and independent N3/N6 evidence.
Use a Jetson-side bound probe for end-to-end data-path acceptance.
