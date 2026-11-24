# Network, RF Baseline and Access Policy Reference

[简体中文](network-and-rf-profile.zh-CN.md)

This document is the single source of truth for the radio baseline, 5G SA
network contract, and UE access verification semantics defined in
`config/network-contract.json` and `deploy/spark/stack/runtime.py`.

## Radio Baseline (`OCUDU gNB` + `USRP B210`)

| Parameter | Default Baseline | Source |
| --- | --- | --- |
| Frequency band | Band `n78` | `config/network-contract.json` |
| Channel bandwidth | `20 MHz` | `config/network-contract.json` |
| Subcarrier spacing (SCS) | `30 kHz` | `config/network-contract.json` |
| MIMO / antenna configuration | `1T1R` | `deploy/spark/stack/runtime.py` |
| Carrier ARFCN | `643392` | `config/network-contract.json` |
| Physical Cell ID (PCI) | `666` | `config/network-contract.json` |
| TDD pattern | `5 ms` period (`7 DL / 2 UL / 6 DL sym / 4 UL sym`) | `config/network-contract.json` |
| UHD B210 gains | `tx_gain=80`, `rx_gain=54` | `deploy/spark/stack/runtime.py` |
| Maximum UL UE MCS | `cell_cfg.pusch.max_ue_mcs=24` | `deploy/spark/stack/runtime.py` |
| UHD receive / send frames | `64 / 64` | `deploy/spark/stack/runtime.py` |

## 5G Core and Data PDU Profile (`Open5GS 5GC`)

| Parameter | Value | Scope & Notes |
| --- | --- | --- |
| PLMN | `460/03` | Must match programmed USIM IMSI prefix |
| Tracking Area Code (TAC) | `1` | Single-cell SA deployment |
| Slice (SST) | `1` | Default data slice (without SD restriction) |
| PDU session type | Single `IPv4` data PDU | Focused 5G SA data plane |
| Data Network Name (`DNN`) | `oai` | Shared by core UPF policy and Jetson Device Setup |
| UE IPv4 address pool | `10.0.0.0/24` | Verified during Jetson connectivity checks |
| QoS `5QI` | `9` | Default non-GBR data bearer (`QFI 1` observed at core) |
| External DN test endpoint | `ext-DN` HTTP `/health` on TCP `8080` | Internal to `aoc-v2-open5gs`; used by bound data probes |

## UE Configuration Profile & Policy Model

Jetson Console organizes runtime configuration into five independent blocks:

| Section | Contents | Runtime Behavior |
| --- | --- | --- |
| `network` | Target PLMN, slice (`SST`), `DNN`, expected IPv4 pool | Validated during Device Setup; changing values updates expectations on Jetson without altering Open5GS |
| `selection` | `rat: "NR5G-SA"`, `mode: "observe_only"`, target band, optional PCI and SSB ARFCN | Compares observed serving cell against policy without issuing modem frequency or cell-lock commands |
| `diagnostics` | Bound target addresses (`gateway`, `upf`, `ext_dn`, `public`) and required probe set | Requires at least two distinct bound targets to verify user-plane forwarding |
| `management` | `wifi_interface`, `tailscale_interface` (`tailscale0`), `spark_address` | Verifies out-of-band management protection before allowing write actions |
| `recovery` | `natural_wait_seconds`, `max_attempts`, `cooldown_seconds` | Bounds automatic recovery cadence after an outage |

Note that `radio_reference` carries the gNB carrier-center ARFCN for operator
reference rather than the serving SSB ARFCN; operators may set `pci` and
`ssb_arfcn` to `null` to relax cell-observation matching.

## Independent Status Indicators & Evidence Quality

Both consoles decouple **operational health** from **evidence quality**:

- **Evidence quality states**:
  - `ok`: Fresh measurement within the configured validity window.
  - `stale`: Last sample exceeded its freshness budget (e.g., `> 20 s` on Jetson).
  - `unavailable`: Collector or device interface could not read live state.
  - `unsupported`: Field is outside the active build's telemetry capability.
- **UE Connected State Criteria**: A UE reports `connected` only when fresh
  readings agree across SIM readiness, NR SA attachment on `460/03`, active
  IPv4 PDU in `10.0.0.0/24`, active RNDIS/ECM interface, current gNB RAN
  context, and bound user-plane probes. A registration, serving-cell, PDU, or
  interface change invalidates earlier probe results immediately.
- **Collector Generation Tracking**: Both consoles tag samples with source
  timestamps and process generation IDs so restarts or counter resets open a
  clean measurement interval instead of producing artificial traffic spikes.
