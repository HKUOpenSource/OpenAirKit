# Hardware, Modem USB and TB01 Reference Notes

[简体中文](hardware-notes.zh-CN.md)

This appendix consolidates modem USB interface topology mappings, Quectel
RM520N-GL firmware diagnostics, Linux kernel compatibility notes, and the TB01
USIM APDU reference.

## Quectel RM520N-GL USB Interface Layouts

When mounted on the **Waveshare SIM8262E-M2 5G for Jetson Orin** expansion
board over USB 3.0, the RM520N-GL enumerates under either an **RNDIS** or **ECM
(`cdc_ether`)** USB layout. Jetson Console validates USB interface descriptors
rather than `ttyUSB` node numbers before opening any serial device and rejects
mismatches:

| USB Data Driver | Data `bInterfaceNumber` | Serial `bInterfaceNumber` (`DIAG / GNSS / AT / Modem`) | Required `device.at_interface_number` |
| --- | --- | --- | --- |
| `rndis_host` (RNDIS) | `00/01` | `02`, `03`, `04`, `05` | `"04"` |
| `cdc_ether` (ECM) | `04` | `00`, `01`, `02`, `03` | `"02"` |
| `cdc_ether` (ECM) | `0a` | `00`, `01`, `02`, `03` | `"02"` |

If your RM520N-GL firmware switches between RNDIS and ECM, stop services first
and update `device.at_interface_number` in `/etc/aoc-v2-jetson/device.json`.
Regenerate `/etc/aoc-v2-jetson/boot.json` afterward if opt-in boot coordination
is active.

## Quectel RM520N-GL QMAP and MPDN Firmware Check

On RM520N-GL QMAP firmware, host packet forwarding requires an active default
WWAN and MPDN rule binding matching the modem DHCP lease and `CGACT` context.
Jetson Console configures the `oai` data context while preserving pre-existing
QMAP bindings. If a registered modem with an IPv4 lease passes no host traffic,
stop `aoc-v2-jetson-device.service` and run the read-only AT checks below
against vendor documentation:

```text
AT+CGDCONT?
AT+QCFG="usbnet"
AT+QCFG="usbspeed"
AT+QMAP="MPDN_rule"
AT+QMAPWAC?
AT+QNWPREFCFG="nr5g_band"
AT+QNWPREFCFG="nr5g_disable_mode"
AT+QNWPREFCFG="mode_pref"
```

## Host OS and Kernel Compatibility Notes

- **DGX Spark Linux 7.0+ kernels + MongoDB 8.0**: `stacks/open5gs/compose/render.py` automatically injects `GLIBC_TUNABLES=glibc.pthread.rseq=1` into the `mongo` container so TCMalloc per-CPU `rseq` allocation initializes cleanly on newer Linux kernels.
- **Jetson `ModemManager` exclusion**: Stop, disable, and mask `ModemManager.service` to prevent AT serial contention with `aoc-v2-jetson-device.service`.
- **RM520N-GL USB 3.0 speed negotiation (`bcdUSB 2.00` vs SuperSpeed)**: If `lsusb -d 2c7c:0801 -v` reports `bcdUSB 2.00` (`480 Mbps`) even when attached to a SuperSpeed port, stop `aoc-v2-jetson-device.service` during a maintenance window and inspect `AT+QCFG="usbspeed"`; set `AT+QCFG="usbspeed","311"` (and verify `Bus 02 / 5000M` enumeration after modem reboot) for `40 MHz`+ cellular throughput.
- **Host sysctl throughput profiles**: Stock Jetson L4T `5.15-tegra` kernels do not include `tcp_bbr` or `sch_fq` modules; apply `deploy/jetson/sysctl/99-aoc-v2-jetson-throughput.conf` on Jetson (raising `rmem_max`/`wmem_max` to `16 MiB` and enabling `tcp_mtu_probing`) and `deploy/spark/stack/sysctl/99-aoc-v2-throughput.conf` on Spark (enabling `bbr` + `fq` and `16 MiB` socket buffers).

## TB01 Programmable USIM APDU Reference

When provisioning **TB01** unprovisioned 5G USIM test cards
(`ATR: 3B9E94801FC78031E073FE211366425454423031DB`), execute the verified
instruction sequence below over an exclusive **PC/SC `T=0`** session (`pyscard`
+ Osmocom `pySim.utils.enc_imsi`). Store vendor SADM keys, fixed vendor
prefixes, IMSI, Ki, and OPc strictly inside restricted local directories
(`0700`/`0600`) outside Git.

| Operation | APDU Layout | Technical Notes |
| --- | --- | --- |
| Vendor SADM check | `00 FB FF FF 08 <SADM:8 bytes>` | Decoded from 16 hex chars; execute from `MF` before protected writes |
| USIM IMSI (`EF.IMSI`) | `00 D6 00 00 09 <encoded IMSI:9 bytes>` | Execute inside selected `ADF.USIM` -> `EF.IMSI` (`6F07`); verify readback immediately |
| USIM Ki | `00 FB 00 00 18 <fixed prefix:8 bytes> <Ki:16 bytes>` | Execute from `MF` context |
| USIM OPc | `00 FB 00 10 19 <fixed prefix:8 bytes> 01 <OPc:16 bytes>` | Byte `01` is a fixed constant inside the OPc instruction, not the algorithm selector |
| USIM Milenage selector | `00 FB 00 00 09 <fixed prefix:8 bytes> 00` | **`00` = Milenage**, **`01` = XOR** (selector `01` produces `AUTHENTICATE` error `9862`) |

### TB01 Card Safety Rules

- **Preserve factory file layout**: Keep `ICCID`, `PIN`, `PUK`, and `ADM` intact, and never format or reconstruct `EF.DIR`. Modify only the lower nibble of byte 4 in `EF.AD` when the target MNC length differs (`2` for PLMN `460/03`).
- **Clear blocking `EF.FPLMN` entries on reuse**: When reusing a previously tested card that cached `460/03` in `EF.FPLMN`, clear only that 3-byte entry.
- **Handle `61xx` cleanly and avoid blind retries**: Retrieve pending response bytes via bounded `GET RESPONSE` (e.g., `6110` -> `9000` carrying `AUTS`). Halt immediately on `63Cx` retry-counter warnings or ambiguous status words without retrying authentication keys.
- **Closed-loop validation**: Execute a local 3G AKA vector (`Ki`, `OPc`, random `RAND`, initial `SQN 0`) and confirm `AUTS` MAC-S validates under `AMF=0000`, followed by live 5G SA attachment verification on Jetson.
