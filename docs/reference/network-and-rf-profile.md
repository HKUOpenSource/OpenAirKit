# Network, RF Baseline and Access Policy Reference

[简体中文](network-and-rf-profile.zh-CN.md)

This reference serves as the authoritative specification for the RF baseline,
5G SA network contract, and UE connectivity evaluation semantics defined in
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
| PLMN | `460/03` | Must match the provisioned USIM IMSI prefix |
| Tracking Area Code (TAC) | `1` | Single-cell SA deployment |
| Slice (SST) | `1` | Default data slice (without SD constraint) |
| PDU session type | Single `IPv4` data PDU | Focused 5G SA user plane |
| Data Network Name (`DNN`) | `oai` | Shared across core UPF policy and Jetson Device Setup |
| UE IPv4 address pool | `10.0.0.0/24` | Validated during Jetson connectivity probes |
| QoS `5QI` | `9` | Default non-GBR data bearer (`QFI 1` observed at core) |
| External DN probe endpoint | `ext-DN` HTTP `/health` on TCP `8080` | Internal to `aoc-v2-open5gs`; target for bound data probes |

## UE Configuration Profile & Policy Model

Jetson Console partitions runtime configuration into five independent blocks:

| Section | Contents | Runtime Behavior |
| --- | --- | --- |
| `network` | Target PLMN, slice (`SST`), `DNN`, expected IPv4 pool | Validated during Device Setup; edits update Jetson expectations without modifying Open5GS |
| `selection` | `rat: "NR5G-SA"`, `mode: "observe_only"`, target band, optional PCI and SSB ARFCN | Audits serving cell parameters against policy without issuing frequency-lock or cell-lock AT commands |
| `diagnostics` | Bound target addresses (`gateway`, `upf`, `ext_dn`, `public`) and required probe set | Requires at least two distinct bound targets to verify user-plane forwarding |
| `management` | `wifi_interface`, `tailscale_interface` (`tailscale0`), `spark_address` | Verifies out-of-band management protection before authorizing route mutations |
| `recovery` | `natural_wait_seconds`, `max_attempts`, `cooldown_seconds` | Bounds automatic recovery cadence following a link outage |

`radio_reference` stores the gNB carrier-center ARFCN for operator reference
rather than the serving SSB ARFCN; administrators may set `pci` and
`ssb_arfcn` to `null` to relax cell-observation matching.

## Independent Status Indicators & Telemetry Freshness

Both consoles decouple **operational health** from **telemetry freshness**:

- **Telemetry freshness states**:
  - `ok`: Current sample within the configured validity window.
  - `stale`: Last sample exceeded its validity budget (e.g., `> 20 s` on Jetson).
  - `unavailable`: Collector or device interface failed to acquire a sample.
  - `unsupported`: Field is outside the active build's telemetry schema.
- **UE Connected State Criteria**: A UE reports `connected` only when valid,
  current readings align across USIM readiness, NR SA registration on `460/03`,
  active IPv4 PDU in `10.0.0.0/24`, active RNDIS/ECM interface, current gNB RAN
  context, and bound user-plane probes. Any change in registration, serving
  cell, PDU session, or interface invalidates prior probe evidence immediately.
- **Process Generation Tracking**: Both consoles tag telemetry with source
  timestamps and process generation IDs so service restarts or counter resets
  open a clean measurement window instead of emitting synthetic throughput
  spikes.
