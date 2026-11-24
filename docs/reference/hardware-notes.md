# Hardware, Modem USB and TB01 Reference Notes

[简体中文](hardware-notes.zh-CN.md)

This appendix consolidates device-specific USB topology rules, Quectel
RM520N-GL firmware checks, Linux kernel notes, and the TB01 USIM APDU
reference.

## Quectel RM520N-GL USB Interface Layouts

When mounted on the **Waveshare SIM8262E-M2 5G for Jetson Orin**
expansion board over USB 3.0, the RM520N-GL enumerates either an **RNDIS** or
**ECM (`cdc_ether`)** topology. Jetson Console verifies the USB interface
descriptors before opening any serial port and rejects mismatches (`ttyUSB`
numbers alone are non-deterministic):

| USB Data Driver | Data `bInterfaceNumber` | Serial `bInterfaceNumber` (`DIAG / GNSS / AT / Modem`) | Required `device.at_interface_number` |
| --- | --- | --- | --- |
| `rndis_host` (RNDIS) | `00/01` | `02`, `03`, `04`, `05` | `"04"` |
| `cdc_ether` (ECM) | `04` | `00`, `01`, `02`, `03` | `"02"` |
| `cdc_ether` (ECM) | `0a` | `00`, `01`, `02`, `03` | `"02"` |

Update `device.at_interface_number` in `/etc/aoc-v2-jetson/device.json` while
services are stopped if your RM520N-GL firmware switches between RNDIS and ECM.
If opt-in boot coordination is enabled, refresh `/etc/aoc-v2-jetson/boot.json`
after changing `device.json`.

## Quectel RM520N-GL QMAP and MPDN Firmware Check

On RM520N-GL QMAP firmware, a modem DHCP lease and active `CGACT` context
require a matching default WWAN and MPDN rule binding for host data forwarding.
Jetson Console configures the `oai` data context while preserving existing
QMAP rules. If a registered modem with an IPv4 address passes no host traffic,
stop `aoc-v2-jetson-device.service` and inspect the read-only AT state against
the vendor manual:

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

- **DGX Spark Linux 7.0+ kernels + MongoDB 8.0**: `stacks/open5gs/compose/render.py` automatically sets `GLIBC_TUNABLES=glibc.pthread.rseq=1` on the `mongo` container so TCMalloc per-CPU `rseq` allocation initializes cleanly on newer Linux kernels.
- **Jetson `ModemManager` exclusion**: Stop, disable, and mask `ModemManager.service` so it never contends with `aoc-v2-jetson-device.service` for the RM520N-GL AT serial interface.

## TB01 Programmable USIM APDU Reference

If you provision **TB01** blank USIM cards (`ATR: 3B9E94801FC78031E073FE211366425454423031DB`),
use the verified instruction sequence below over an exclusive **PC/SC `T=0`**
connection (`pyscard` + Osmocom `pySim.utils.enc_imsi`). Keep vendor SADM keys,
fixed vendor prefixes, IMSI, Ki, and OPc in restricted local storage (`0700`/`0600`)
outside Git.

| Operation | APDU Layout | Technical Notes |
| --- | --- | --- |
| Vendor SADM check | `00 FB FF FF 08 <SADM:8 bytes>` | Decoded from 16 hex chars; execute from `MF` before protected writes |
| USIM IMSI (`EF.IMSI`) | `00 D6 00 00 09 <encoded IMSI:9 bytes>` | Execute in selected `ADF.USIM` -> `EF.IMSI` (`6F07`); read back immediately |
| USIM Ki | `00 FB 00 00 18 <fixed prefix:8 bytes> <Ki:16 bytes>` | Execute from `MF` context |
| USIM OPc | `00 FB 00 10 19 <fixed prefix:8 bytes> 01 <OPc:16 bytes>` | Byte `01` is fixed inside the OPc instruction, not the algorithm selector |
| USIM Milenage selector | `00 FB 00 00 09 <fixed prefix:8 bytes> 00` | **`00` = Milenage**, **`01` = XOR** (selector `01` causes `AUTHENTICATE` error `9862`) |

### TB01 Card Safety Rules

- **Do not alter factory card structure**: Preserve `ICCID`, `PIN`, `PUK`, and `ADM`, and never format or rebuild `EF.DIR`. Only update the lower nibble of byte 4 in `EF.AD` if the target MNC length differs (`2` for PLMN `460/03`).
- **Clear blocking `EF.FPLMN` entries when reusing cards**: If a previously tested card stored `460/03` in `EF.FPLMN`, clear only that 3-byte entry.
- **Handle `61xx` and avoid blind retries**: Read pending response data using bounded `GET RESPONSE` (e.g., `6110` -> `9000` carrying `AUTS`). Stop immediately on `63Cx` retry-counter warnings or ambiguous responses without retrying keys.
- **Local verification**: Run a local 3G AKA vector (`Ki`, `OPc`, random `RAND`, initial `SQN 0`) and confirm the returned `AUTS` MAC-S validates under `AMF=0000`, then complete live 5G SA attach verification on Jetson.
