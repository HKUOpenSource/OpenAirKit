# Glossary

[简体中文](glossary.zh-CN.md)

| Term | Definition |
| --- | --- |
| **5G SA (Standalone)** | 5G NR radio access network (`OCUDU gNB`) directly connected to a cloud-native 5G Core (`Open5GS 5GC`) over N2/N3 without an LTE anchor. |
| **N2 / N3 / N4 / N6** | 3GPP 5G reference interfaces: gNB-AMF control plane (`N2` / NGAP), gNB-UPF GTP-U user plane (`N3`), SMF-UPF PFCP session control (`N4`), and UPF-Data Network interface (`N6`). |
| **`ext-DN`** | Lightweight external data-network container inside `aoc-v2-open5gs` exposing an HTTP `/health` endpoint on TCP `8080` as a bound user-plane probe target. |
| **PDU Session** | Logical IPv4 user-plane connection between the UE and `ext-DN` identified by `DNN=oai`, slice `SST=1`, and `5QI=9`. |
| **Evidence Quality** | Independent trustworthiness label (`ok`, `stale`, `unavailable`, `unsupported`) attached to telemetry snapshots separately from operational health. |
| **Protocol-186 Routing** | Default IPv4 routes managed by Jetson Console under Linux routing protocol `186`: Wi-Fi fallback (`metric 5`) and verified cellular preference (`metric 10`). |
| **QMAP / MPDN** | Quectel RM520N-GL multiplexing/multi-PDN firmware rules mapping cellular PDU sessions to host RNDIS/ECM data interfaces. |
| **`boot_id` Ledger** | Persistent per-boot record keyed by `/proc/sys/kernel/random/boot_id` inside `boot_connect.py` to execute unattended setup at most once per cold boot. |
| **ATR (Answer To Reset)** | Standard ISO/IEC 7816 hex response returned by a smartcard upon power-up reset, encoding transport parameters (such as `T=0`) and manufacturer historical bytes used to verify programmable USIM models (such as `TB01`) before issuing card-specific APDU writes; contains no subscriber keys. |
