# Glossary

[简体中文](glossary.zh-CN.md)

| Term | Definition |
| --- | --- |
| **5G SA (Standalone)** | 5G NR radio access network (`OCUDU gNB`) interconnected directly to a cloud-native 5G Core (`Open5GS 5GC`) over N2/N3 without an LTE anchor. |
| **N2 / N3 / N4 / N6** | 3GPP 5G reference interfaces: gNB-AMF control plane (`N2` / NGAP), gNB-UPF GTP-U user plane (`N3`), SMF-UPF PFCP session control (`N4`), and UPF-Data Network forwarding interface (`N6`). |
| **`ext-DN`** | Minimal external data-network container inside `aoc-v2-open5gs` exposing an HTTP `/health` probe endpoint on TCP `8080` for bound data-plane validation. |
| **PDU Session** | Logical IPv4 user-plane session between the UE and `ext-DN` identified by `DNN=oai`, slice `SST=1`, and `5QI=9`. |
| **Telemetry Freshness (Evidence Quality)** | Independent validity tag (`ok`, `stale`, `unavailable`, `unsupported`) attached to telemetry snapshots separately from operational health so aged samples never mask outages. |
| **Protocol-186 Routing** | Kernel routing protocol `186` rules managed by Jetson Console: Wi-Fi fallback default (`metric 5`) and verified cellular preferred default (`metric 10`). |
| **QMAP / MPDN** | Quectel RM520N-GL firmware multiplexing/multi-PDN rules binding cellular PDU sessions to host RNDIS/ECM network interfaces. |
| **`boot_id` Ledger** | Persistent per-boot guard keyed by `/proc/sys/kernel/random/boot_id` inside `boot_connect.py` to limit unattended cold-boot attachment to one cycle per boot. |
| **ATR (Answer To Reset)** | Standard ISO/IEC 7816 hexadecimal response emitted upon smartcard power-up reset, encoding transport parameters (such as `T=0`) and manufacturer historical bytes used to verify programmable 5G USIM models (such as `TB01`) prior to APDU provisioning; contains no subscriber keys. |
