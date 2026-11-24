# SIM Provisioning and TB01 Reference Guide

[简体中文](sim-programming-tb01.zh-CN.md)

This guide explains how to provision **Open5GS** subscribers and prepare
programmable **5G USIM** cards for **Jetson Orin + Quectel RM520N-GL** UEs,
followed by the verified APDU specification for **TB01** cards.

## General Programmable USIM Requirements

Any standard **Milenage-capable programmable 5G USIM** (for example, cards
supported by upstream [Osmocom pySim](https://downloads.osmocom.org/docs/pysim/master/html/))
can connect to the **OCUDU + Open5GS** network when provisioned consistently:

1. **Provision one independent subscriber per UE in Open5GS**:
   Use `stacks/open5gs/subscriber.py` on **DGX Spark** to insert a unique
   subscriber with an independent **IMSI**, **Ki**, and **OPc**, initial `sqn=0`,
   single IPv4 PDU, `dnn=oai`, `sst=1`, and `five_qi=9` (matching
   [UE Access Policy](ue-access-policy.md)). Never share one IMSI across multiple
   physical SIM cards or UEs.
2. **Keep subscriber material outside Git**:
   Store `sim.json`, identity exports, and backups in an access-restricted local
   directory outside the repository (`chmod 0700` directories, `chmod 0600` files).
   When your input provides `OPc` directly, do not treat it as `OP` and re-derive
   `OPc`.
3. **Write matching USIM credentials**:
   Program `EF.IMSI` (`6F07` under `ADF.USIM`), `Ki`, `OPc`, and the **Milenage**
   algorithm on your card via PC/SC on a Linux or macOS provisioning
   workstation, verify readback and local AUTS key agreement, then check
   first-registration SQN synchronization in live 5G SA attach.

---

## Verified Reference Profile: TB01 Programmable USIM

The sections below document the verified protocol details for **TB01** blank
USIM cards analyzed against `GRSIMWrite 4.4.9+` (`GRSIMWrite.exe` SHA-256:
`ed4912990f5a2bd5dcbf38df9743d3028a842d2b7ac5594b9825c0627eb48fe5`).
Compatibility with other TB01 firmware revisions or card models is not assumed;
vendor write adapters stay in private local storage rather than this repository.

### Card Identification & PC/SC Transport

- **Toolchain**: Python `3.12`, `pyscard 2.3.1`, and Osmocom `pySim` (reference commit `9aa8934da2415b161eb9726adad2ba7b4f35d1a7`).
- **Transport**: Exclusive system PC/SC connection with **`T=0` explicitly selected on initial connect** (no initial `T=0`/`T=1` negotiation or `T=1` fallback).
- **Target ATR**: `3B9E94801FC78031E073FE211366425454423031DB`.

### SADM vs. Standard ADM

The TB01 vendor authorization sequence uses an embedded 16-hex-character
**SADM** decoded into 8 raw bytes inside a proprietary APDU (`00 FB FF FF 08`).
This is handled separately from standard `ADM1` or UI ADM-change commands and
does not establish global write access to every EF. Keep embedded SADM values,
default ADMs, and vendor fixed prefixes private outside Git and documentation;
never brute-force ADM retry counters.

### Recommended Programming Sequence

1. **Read-only comparison with Open5GS**: Verify IMSI, Ki, OPc, AMF, OPc mode, enabled status, and target DNN/SST match the live Open5GS subscriber without modifying existing subscribers or SQN.
2. **Preflight & backup**: Require a single PC/SC reader, exclusive `T=0`, and exact ATR match. Locate the USIM application via `MF` / `EF.DIR`, back up `ICCID`, `EF.IMSI`, and `EF.AD`, and confirm target MNC length (`2` for PLMN `460/03`). Reject cards carrying another active UE's IMSI.
3. **Authorize & write `EF.IMSI` first**: Select `MF`, run vendor SADM check (`9000`), select `ADF.USIM` -> `EF.IMSI` (`6F07`), encode 9 bytes via `pySim.utils.enc_imsi`, run `UPDATE BINARY`, and read back immediately. Stop before writing keys if access is denied.
4. **Write USIM auth material (`Ki`, `OPc`, Milenage)**: Return to `MF` and apply the TB01 layouts below. Do not format, erase, rebuild `EF.DIR`, enter GSM/CDMA branches, or alter `ICCID` / `PIN` / `PUK` / `ADM`. If `EF.AD` MNC length requires adjustment, modify only the lower nibble of byte 4 while preserving all other bits.
5. **Clear blocking `EF.FPLMN` entries (if present)**: If a repurposed test card carries the target lab PLMN in `EF.FPLMN`, clear only that 3-byte entry while leaving remaining entries untouched.
6. **Reconnect & verify Milenage agreement**: Verify persistent `IMSI`, preserved `ICCID`, and MNC length, then issue a local 3G AKA test vector (`Ki`, `OPc`, random `RAND`, `AMF`) using initial `SQN 0`. Verify the returned `AUTS` MAC-S (`DC 0E ...` under `AMF=0000`). Confirm full network registration, SQN synchronization and IPv4 PDU establishment after inserting the card into the Jetson RM520N-GL modem.

### Verified TB01 APDU Command Layouts

Angle brackets mark private inputs; fixed vendor command prefixes differ per
instruction and are not interchangeable. Decode `Ki` and `OPc` from 32 hex
characters into 16 bytes each.

| Operation | APDU Layout | Notes |
| --- | --- | --- |
| Vendor SADM check | `00 FB FF FF 08 <SADM:8 bytes>` | Must precede protected writes |
| USIM IMSI (`EF.IMSI`) | `00 D6 00 00 09 <encoded IMSI:9 bytes>` | Run in selected `ADF.USIM` (`6F07`) context |
| USIM Ki | `00 FB 00 00 18 <fixed prefix:8 bytes> <Ki:16 bytes>` | Run from `MF` context |
| USIM OPc | `00 FB 00 10 19 <fixed prefix:8 bytes> 01 <OPc:16 bytes>` | Byte `01` is fixed inside the OPc layout, not the algorithm selector |
| USIM Milenage selector | `00 FB 00 00 09 <fixed prefix:8 bytes> 00` | Selector `00` = **Milenage**; `01` = **XOR** |

> [!CAUTION]
> **Milenage Selector (`00` vs. `01`)**: Offline analysis of `GRSIMWrite.exe`
> confirmed that `RadLTE_MLG` maps to `00` (Milenage) and `RadLTE_XOR` maps to
> `01` (XOR). Sending `01` causes `AUTHENTICATE` to fail with `9862`
> (incorrect MAC) even when `IMSI`, `Ki`, and `OPc` writes return `9000`.

### Response Handling and Replay Safety

- **`61xx`**: Response bytes pending; read back via bounded `GET RESPONSE` (e.g., `6110` followed by `9000` carrying `AUTS`).
- **No blind retries**: Never auto-retry authentication or writes after `6Cxx`, `63Cx` retry-counter warnings, timeouts, or ambiguous status; preserve state and inspect before proceeding.
- **Durable operation journals**: Append each mutation to an `fsync`-backed journal before execution and block replay once a card journal completes so re-running a workflow cannot accidentally overwrite another card or burn retry counters.

## References

- [Osmocom pySim documentation](https://downloads.osmocom.org/docs/pysim/master/html/)
- [pySim PC/SC implementation](https://raw.githubusercontent.com/osmocom/pysim/master/pySim/transport/pcsc.py)
- [ETSI TS 102 221: UICC interface and administrative access](https://www.etsi.org/deliver/etsi_ts/102200_102299/102221/18.02.00_60/ts_102221v180200p.pdf)
- [ETSI TS 35.208: Milenage test data](https://www.etsi.org/deliver/etsi_ts/135200_135299/135208/18.00.00_60/ts_135208v180000p.pdf)
