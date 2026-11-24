# TB01 experimental SIM programming method

[简体中文](sim-programming-tb01.zh-CN.md)

## Quick Role in End-to-End Setup

Before inserting a SIM card into a Jetson UE (see [Quickstart](quickstart.md)):

1. Provision a **separate subscriber per UE** in Open5GS (`stacks/open5gs/subscriber.py`)
   with independent **IMSI**, **Ki** and **OPc**, `sqn=0`, single IPv4 PDU,
   `dnn=oai`, `sst=1` and `five_qi=9` (aligning with [UE Access Policy](ue-access-policy.md)).
2. Keep exported `sim.json` / subscriber material in private local storage
   outside Git (`chmod 0700` directories, `chmod 0600` files).
3. Program the TB01 USIM with the reviewed `GRSIMWrite 4.4.9+` adapter
   contract below (PC/SC `T=0`, exact TB01 ATR, **Milenage selector `00`**)
   and confirm both IMSI readback and AUTS MAC-S match before booting the UE.

## Background and scope

This document records the programming performed locally on 2026-10-16,
including a fault discovered and corrected during verification. Its scope is
the reviewed GRSIMWrite 4.4.9+ binary and the card used in this session;
compatibility with other TB01 firmware or card models is unproven. The adapter
remains in private local storage and is not a released repository tool.

## Observed result and verification limits

| Item | Observed result |
| --- | --- |
| Source | Existing Spark experimental SIM material, compared read-only with the live Open5GS subscriber before programming |
| IMSI | Read back immediately after the USIM write and again after reconnection |
| Ki / OPc | Valid AUTS MAC-S under the same material; no card key readout |
| Algorithm | Corrected to Milenage, vendor selector `00` |
| ICCID, PIN, PUK, ADM | Preserved; no commands to change these fields |
| MNC length | Both original and target lengths were 2; no EF.AD change needed |
| Core | Database and SQN unchanged |
| Offline tests | Corrected adapter passed 13 tests |
| Network access | Jetson registration and data service untested; first registration must still verify SQN synchronization |

A valid AUTS demonstrates Milenage operation with the intended Ki / OPc. It
does not establish a normal successful AKA exchange. This session received a
synchronization response, not a normal RES / CK / IK success response, and did
not establish a UE data session.

## Toolchain and card identification

- Private Python 3.12 environment, `pyscard 2.3.1`, and official Osmocom pySim
  pinned to commit `9aa8934da2415b161eb9726adad2ba7b4f35d1a7`.
- System PC/SC reader access with **T=0 explicitly selected on the initial
  connection**. No initial T=0 / T=1 negotiation or T=1 fallback.
- Exact ATR match: `3B9E94801FC78031E073FE211366425454423031DB`. This identifies
  the vendor software's TB01 branch, not a proven retail model or complete COS
  capability set.
- Vendor EXE / DLL files were analyzed offline, without executing them locally
  or through Wine. Reviewed `GRSIMWrite.exe` SHA-256:
  `ed4912990f5a2bd5dcbf38df9743d3028a842d2b7ac5594b9825c0627eb48fe5`.

## SADM and ADM

The TB01 vendor check uses embedded **SADM**: decode 16 hexadecimal characters
into eight raw bytes and place them in a proprietary APDU. The software handles
this separately from the UI ADM field and the ADM change command. There is no
evidence that SADM is standard ADM1.

A separately authorized management check returned `9000` without programming.
The later programming task performed its required SADM check in a new operation
journal. Each task records execution state and does not retry automatically.
Success proves acceptance of that vendor check only; each subsequent write
establishes its own access result, not unrestricted access to every file.

Embedded SADM, default ADM, and vendor fixed prefixes are omitted here. No ADM
guessing was used; actual values remain within the restricted local workflow.

## Programming sequence used

1. **Compare with the live core first.** A read-only Spark helper compared the
   private SIM files with the unique corresponding Open5GS subscriber, including
   IMSI, Ki, OPc, AMF, OPc mode, enabled state, and expected DNN / SST. It exported
   redacted comparison results without recreating the subscriber, resetting SQN,
   or restarting services.
2. **Transfer privately.** Existing `sim.json`, `identity.json`, and comparison
   results were transferred over SSH / SCP to restricted local storage and
   checked for file consistency. Directories use `0700`, files `0600`. No new
   keys were generated. An OPc input must not be treated as OP and derived again.
3. **Preflight and back up read-only.** Require exactly one reader, exclusive
   T=0 access, and an exact full ATR match. Find the unique USIM application via
   MF / EF.DIR. Privately back up ICCID, USIM IMSI, and EF.AD; check lengths and
   target MNC length without reading Ki / OPc. Recheck card identity before writes.
4. **Check access, then write IMSI first.** Select MF and perform the vendor
   SADM check. Select EF.IMSI (`6F07`) under ADF.USIM, encode nine bytes with
   pySim `enc_imsi`, UPDATE BINARY, and compare an immediate readback. If file
   access is denied, stop before writing keys; do not try another ADM.
5. **Write USIM authentication material.** Return to MF and use the reviewed
   TB01 templates for Ki, OPc, and the algorithm selector. Do not format, erase,
   rebuild EF.DIR, enter GSM / CDMA branches, or change PIN / PUK / ADM. If EF.AD
   needs adjustment, change only the MNC length nibble in byte four, preserving
   other bits and bytes. No adjustment was needed here.
6. **Reconnect and verify.** Check persistent IMSI, preserved ICCID, and MNC
   length. Generate a local USIM 3G AKA vector using the target Ki / OPc, random
   RAND, and AMF. This session used initial SQN 0, consistent with the core
   comparison, without changing core SQN.
7. **Correct the selector and verify again.** The initial verification exposed
   the algorithm error described below. The correction sent only the SADM
   check, algorithm selector `00`, and one AKA command. It did not rewrite IMSI,
   Ki, or OPc. Verify AUTS, save a redacted completion report, and close the
   reader connection.

## TB01 command layouts and encoding

These are reviewed layouts, not executable instructions. Angle brackets mark
private data. Fixed prefixes are extracted privately from the reviewed binary;
their semantics have not been independently established and are not assumed to
be standard ADM.

| Operation | Layout |
| --- | --- |
| Vendor SADM check | `00 FB FF FF 08 <SADM:8 bytes>` |
| USIM IMSI | In the selected USIM file context: `00 D6 00 00 09 <encoded IMSI:9 bytes>` |
| USIM Ki | `00 FB 00 00 18 <fixed prefix:8 bytes> <Ki:16 bytes>` |
| USIM OPc | `00 FB 00 10 19 <fixed prefix:8 bytes> 01 <OPc:16 bytes>` |
| USIM Milenage | `00 FB 00 00 09 <fixed prefix:8 bytes> 00` |

Preserve each command's distinct fixed prefix; they are not interchangeable.
The `01` within the OPc template is a fixed field, not the algorithm selector.
Decode Ki and OPc from 32 hexadecimal characters into 16 bytes each; AMF is two
bytes. Use the standard IMSI encoder rather than placing decimal text in an APDU.

## Algorithm selection fault and correction

The initial implementation read the DWORD after a Delphi field name as that
control's offset. The current record's offset is actually seven bytes before
the name; the original read belonged to the next record. This reversed the
Milenage / XOR mapping. Initial IMSI, Ki, and OPc writes returned `9000`, but
selector `01` caused AUTHENTICATE to return `9862` (incorrect MAC), which is not
an SQN synchronization failure.

Review of field records, UI data, and command construction established:

- `RadLTE_MLG` has offset `0x614`; `RadLTE_XOR` has offset `0x618`.
- The software checks the XOR control and maps it to internal enum 9. The TB01
  builder encodes enum 9 as `01` and the other branch as `00`.
- For this TB01 workflow, **Milenage = `00`; XOR = `01`**.

The corrected adapter passed 13 offline tests, including rejection of the wrong
field record, prevention of IMSI / key rewrites during algorithm-only repair,
and Milenage standard vectors. Original and correction journals remain private.

## Response handling and replay prevention

- `61xx` means response data is pending; fetch it using bounded GET RESPONSE.
  Final verification initially returned `6110`, followed by `9000` with an AUTS
  response beginning `DC 0E`.
- Validate AUTS MAC-S with the same Ki / OPc, recovered card SQN, and the
  synchronization procedure's `AMF=0000`. Validity establishes key agreement;
  actual registration must still verify that the network accepts resynchronization.
- Do not automatically retry authentication or writes, including after `6Cxx`.
  Stop on retry-counter indications such as `63Cx`, timeouts, or ambiguous
  results. Preserve state and do not try alternative management codes.
- Before each authentication or mutation, append the operation to a durable
  journal and synchronize it to disk. Restrict command types, counts, and file
  context. Keep read-only tools separate from the writer. Completed journals
  block replay; never delete them to bypass that protection.

## Private records and next steps

The local private SIM tools directory contains `tb01/program-20261016/`, with
original backups, source material, journals, corrected `adapter-v2/`, and
`completion.json`. The old adapter is historical evidence and must not be reused.
These files stay outside Git. Do not copy IMSI, ICCID, keys, management codes,
credential commitments, or raw logs into documentation, command arguments, or chat.

Next, insert the card into Jetson and verify modem recognition, network
selection, first SQN synchronization, registration, and a data session. Preparing
this document performed no additional card or device operations.

## Second UE card — 2026-10-16

The second card was programmed using the corrected `adapter-v2` workflow above,
with a separate operation journal and independent experimental credentials.
This is a later execution record; the earlier observations describe the first
card at its programming stage.

Question: can a second card be provisioned without reusing the first UE's
identity or changing its live subscription? No `.codegraph/` index existed.
The operation path was the canonical `stacks/open5gs/subscriber.py` insert,
private material comparison, corrected adapter preflight/program, and a bounded
forbidden-network entry update. No repository product source was changed.

| Check | Observed result |
| --- | --- |
| Core provisioning | One new subscriber; total increased from one to two |
| Existing subscribers | Static fields preserved; SQN did not decrease; no service restart |
| New material | Independent IMSI, Ki and OPc; initial new subscriber SQN zero; private export matched the core proof |
| Card identification | Exact TB01 ATR and T=0; this card had the same factory ICCID as the first card but a different original IMSI |
| Card protection | Full preflight snapshot required; first UE IMSI explicitly rejected; factory ICCID preserved |
| Programming | One SADM check, IMSI, Ki, OPc and Milenage `00`; writes accepted without automatic retries |
| Verification | IMSI persisted across reconnection, MNC length remained two, AUTS MAC-S matched the new Ki / OPc |
| Selection state | Cleared the single target experimental PLMN entry in the 90-byte forbidden list; other 87 bytes unchanged, including after reconnection |
| Reader | Connection closed after each stage |
| UE2 registration | Not yet tested; the second Jetson's modem was not enumerated during the earlier SSH inventory |

The AUTS result proves key agreement, with the same synchronization limitation
described above. It does not prove successful network registration. Forbidden
entry cleanup used a separate one-shot journal and no authentication command or
credential rewrite. ICCID, PIN, PUK and ADM were preserved throughout.

Offline validation passed 37 checks: five canonical subscriber tests, eight
provisioning/preservation checks, thirteen corrected-adapter tests and eleven
second-card identity/selection/replay checks. Private records were archived in
`tb01/program-ue2-20261016/` outside Git, with all 27 copied files verified.
Directories use `0700` and files `0600`. Retain both source and archived journals;
their fixed task paths are historical records, not a command to repeat the burn.

Next, move this second card to the second UE, confirm modem and SIM recognition,
then verify registration, SQN synchronization and the data path. The first UE's
card, platform and subscriber were not reconfigured by this operation.

## References

- [Osmocom pySim documentation](https://downloads.osmocom.org/docs/pysim/master/html/)
- [pySim PC/SC implementation](https://raw.githubusercontent.com/osmocom/pysim/master/pySim/transport/pcsc.py)
- [ETSI TS 102 221: UICC interface and administrative access](https://www.etsi.org/deliver/etsi_ts/102200_102299/102221/18.02.00_60/ts_102221v180200p.pdf)
- [ETSI TS 35.208: Milenage test data](https://www.etsi.org/deliver/etsi_ts/135200_135299/135208/18.00.00_60/ts_135208v180000p.pdf)
