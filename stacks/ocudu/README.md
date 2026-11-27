# OCUDU Radio Stack

[简体中文](README.zh-CN.md)

This directory handles OCUDU source fetching, ARM64 compilation, artifact
checksum recording, gNB configuration generation, and health checks. The default baseline
runs as a monolithic `CU-CP + CU-UP + DU` gNB attached to a **USRP B210** over
USB 3.0 / UHD.

Upstream source revisions are pinned in `config/upstreams.json`. Keep source
checkouts, private dependencies, and build outputs inside a dedicated build
workspace outside this repository, and avoid altering system-wide `/usr/local`
UHD installations.

## Implementation Layout

- `scripts/build.py`: Fetches pinned upstream commits, compiles OCUDU on ARM64 as an unprivileged user (using private mbedTLS / GTest tarballs), runs no-RF unit tests, and writes `build-result.json`.
- `deploy/spark/stack/runtime.py`: Renders the single-data-PDU radio configuration (`n78`, `40 MHz`, `30 kHz` SCS, `1T1R`, `6D1S3U`, `srate=46.08`, `otw_format=sc16`, `256/256` UHD frames, `tx_gain=80`, `rx_gain=54`, `pdsch`/`pusch` `qam256` with `pusch.max_ue_mcs=27`) and checks B210 ownership + N2 readiness.
- `scripts/probe_b210.cpp`: Probes UHD serial and gain ranges when the B210 is idle.
- `deploy/spark/stack/package.py`: Stages, verifies, and fresh-installs ARM64 radio + core artifacts without starting services.
- `deploy/spark/stack/libexec/aoc-v2-cpu-latency` & `deploy/spark/stack/systemd/`: Provides `LimitRTPRIO=99`, `aoc-v2-cpu-latency.service` (`PartOf=aoc-v2-radio.service`), and optional `realtime.conf.example`; `scripts/spark/enable_radio_json_metrics.py` enables the guarded `127.0.0.1:8879` JSON metrics endpoint.

## Build Entry Point

```sh
python3 stacks/ocudu/scripts/build.py --workspace <private-workspace> --jobs 2
```

Systemd unit management belongs to `deploy/spark/stack/systemd/`. This module
never starts Open5GS directly; gNB, AMF, and UPF addresses are supplied through
site-protected deployment state. The baseline carries a single IPv4 data
PDU (`5QI=9`).

## Verification Notes

Complete the no-RF build and config checks before verifying B210 USB 3.0
enumeration, real-time scheduling, and N2 setup during a maintenance window.
Never invoke `probe-b210` while the gNB holds the SDR device.

References: [OCUDU Installation](https://docs.ocudu.org/user_manual/installation/), [CU/DU & B210 Tutorial](https://docs.ocudu.org/tutorials/cu_du_split/).
