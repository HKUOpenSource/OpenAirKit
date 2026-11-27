# 40 MHz 6D1S3U Throughput Tuning and MTU/MSS Alignment — 2026-11-27

[简体中文](2026-11-27-40mhz-throughput-tuning.zh-CN.md)

## Scope and Environment

- Date: `2026-11-27`
- Base source revision: `18870db`
- Target release version: `1.1.0`
- Spark target: DGX Spark (ARM64, Ubuntu 24.04 LTS, kernel `7.0.0-1019-nvidia`, USRP B210 over USB 3.0 SuperSpeed, OCUDU `26.04` commit `050a2bb`, Open5GS `2.8.0` + MongoDB `8.0`)
- UE targets: Two Jetson Orin Nano nodes (ARM64, L4T kernel `5.15.148-tegra`, Quectel RM520N-GL in `cdc_ether` ECM mode, upgraded from USB 2.0 `480M` to USB 3.0 `5000M` via `AT+QCFG="usbspeed","311"` + `AT+CFUN=1,1`)
- Redaction: This record omits Tailnet addresses, hostnames, local usernames, USRP serials, SIM credentials, Wi-Fi SSIDs/BSSIDs, and raw logs.

## Bottlenecks Identified and Changes Applied

1. **Air-interface & SDR scaling (`40 MHz`, `6D1S3U`, `sc16`, `qam256`)**:
   - Expanded channel bandwidth from `20 MHz` (51 PRBs, `23.04` MSps, `sc12`, `64/64` UHD frames) to `40 MHz` (106 PRBs, `46.08` MSps, `sc16`, `256/256` UHD frames) in `deploy/spark/stack/runtime.py`, `config/network-contract.json`, `config/network-profile.example.json`, `config/jetson.example.json`, `stacks/open5gs/config.py`, and `scripts/aoclib/radio.py`.
   - Adjusted 5 ms TDD pattern from `7 DL / 2 UL` to `6 DL / 3 UL` (`6 DL sym / 4 UL sym`).
   - Enabled `pdsch.mcs_table = "qam256"` and `pusch = {"mcs_table": "qam256", "max_ue_mcs": 27}` (lifting the prior `max_ue_mcs = 24` cap).
2. **Core MTU, TCP MSS clamping, and subscriber AMBR**:
   - Raised Open5GS SMF `mtu` and UPF `ogstun` interface MTU from `1400` to `1440` (`stacks/open5gs/compose/render.py`, `stacks/open5gs/compose/runtime.py`), and updated the pinned SHA-256 in `deploy/maintenance/repair-connectivity-manifest.py`.
   - Added bidirectional `nftables` TCP MSS clamping (`1400`) in `table ip aoc_v2` (`forward` mangle chain) inside `stacks/open5gs/compose/runtime.py` to prevent PMTUD black holes when newly enumerated UE USB interfaces default to `MTU 1500`.
   - Added `align_cellular_mtu()` (`<= 1440`) to `apps/jetson-console/backend/aoc_jetson/network.py` during `managed_routes()` (`prepare` / `promote`).
   - Raised default subscriber Session AMBR from `100/200 Mbps` to `500/1000 Mbps` (`stacks/open5gs/subscriber.py`, `scripts/aoclib/core.py`, `scripts/aoclib/subscriber.py`) and updated existing live MongoDB subscriber AMBR entries without modifying `sqn` or authentication keys.
3. **Host TCP/queue sysctl profiles**:
   - Added `deploy/spark/stack/sysctl/99-aoc-v2-throughput.conf` (`bbr` + `fq` + `16 MiB` socket buffers) for Spark (`7.0.0-1019-nvidia`).
   - Added `deploy/jetson/sysctl/99-aoc-v2-jetson-throughput.conf` (`16 MiB` socket buffers, `tcp_window_scaling=1`, `tcp_mtu_probing=1`, omitting `tcp_bbr`/`sch_fq` which are absent on stock L4T `5.15.148-tegra`).

## Hardware Benchmark Results (High-SNR UE)

### End-to-End 5G N6 `iperf3` (UE Cellular Interface -> Spark N6 Bridge)

| Measurement | Baseline (`20 MHz`, `7D1S2U`, `UL MCS<=24`, USB 2.0, `cubic`) | Tuned (`40 MHz`, `6D1S3U`, `qam256`, USB 3.0, Spark `bbr+fq`) |
| --- | --- | --- |
| Downlink 1-stream TCP | `58.3 Mbps` (`934` retransmits, `dl_bs` `2.62 MB`, PHY `63 Mbps`) | `112–119 Mbps` steady (`99.2 Mbps` 10s avg incl. ramp; `0` retransmits; `dl_bs` `457–757 KB`; PHY `121 Mbps`, `0%` BLER) |
| Downlink 4-stream TCP | — | `116 Mbps` (`0` retransmits) |
| Uplink 1-stream TCP | `13.2 Mbps` (PHY `13.8 Mbps`, `400/400` UL slots, `UL MCS 24`) | `50.7 Mbps` (PHY `52.4–53.9 Mbps`, `600/600` UL slots, `UL MCS 25`, `0%–1%` BLER) |
| Uplink 4-stream TCP | — | `50.4 Mbps` |
| Radio real-time errors | `0` underflow/overflow/late | `0` underflow/overflow/late |

### Browser Speedtest Observation

- Before MTU/MSS alignment: ~40 Mbps DL / ~10 Mbps UL with `Socket Error` stalls caused by `MTU 1500` vs `1440` PMTUD black hole.
- After `MTU 1440` alignment and UPF MSS clamping (`1400`): **`107.6 Mbps` DL / `32.17 Mbps` UL** with zero socket errors.

## Verification, Rollback, and Limitations

- **Local and dry-run checks**:
  - Live Spark `gnb --dryrun` on generated `40 MHz` `runtime.py` output exited `0`.
  - `test-frontend-behavior` (`7/7`), `test-jetson-backend` (`112/112`), `test-spark-backend` (`72` ran, `1` Linux peer-cred skipped), `test-stack` (`190/190`, with `test_connectivity_endpoint_serves_only_small_health_response` executed outside the network sandbox), `typecheck`, `docs-audit` (`147` documents), `release-audit`, `license-audit`, `version-audit` (`1.1.0`), and `shell-check` all passed.
- **Rollback**: Pre-patch Spark `runtime.py`, `core/config/smf.json`, `core/runtime.py`, `core/bundle.json`, and `release.json` were backed up under `/var/lib/agentic-ocudu/v2/` before updating; restoring those files and restarting `core` and `radio` reverts cleanly. Live sysctl configs reside in drop-in `/etc/sysctl.d/` files and are independently removable.
- **Remaining limitations**:
  - The second UE remained in a lower-CQI RF position (`CQI 5–6`) and was not repositioned for concurrent dual-UE peak saturation testing.
  - Public Internet Speedtest ceiling remains bounded by Spark's upstream WAN link (`wlP9s9` 2.4 GHz Wi-Fi measured ~45 Mbps single-stream HTTP download directly from Spark during diagnostics).
