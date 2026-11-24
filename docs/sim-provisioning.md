# Subscriber Provisioning and USIM Setup

[简体中文](sim-provisioning.zh-CN.md)

This guide explains how to register a UE subscriber in **Open5GS** and prepare
a matching **5G USIM** card for **Jetson Orin + Quectel RM520N-GL** attachment.

## Requirements

- Any standard **Milenage-capable programmable 5G USIM** (for example, cards
  supported by upstream [Osmocom pySim](https://downloads.osmocom.org/docs/pysim/master/html/)).
- A standard USB CCID/PC/SC smartcard reader connected to your workstation.
- Subscriber credentials (`IMSI`, `Ki`, `OPc`) matching the 5G network contract
  in [Network & RF Profile](reference/network-and-rf-profile.md).

## 1. Provision an Independent Subscriber in Open5GS

Each UE requires its own unique `IMSI`, `Ki`, and `OPc` (initial `sqn=0`). On
**DGX Spark**, insert the subscriber record using `stacks/open5gs/subscriber.py`:

```sh
python3 stacks/open5gs/subscriber.py --help
```

Configure the subscriber with a single IPv4 data PDU aligned with the
[Network & RF Profile](reference/network-and-rf-profile.md) (`PLMN`, `DNN`,
`SST`, `5QI`). Never share one subscriber identity across multiple SIM cards or
UEs.

## 2. Program and Verify the 5G USIM

1. Store exported subscriber files (`sim.json`, identity records, and backups)
   in an access-restricted local directory outside Git (`chmod 0700`
   directories, `chmod 0600` files).
2. Write `EF.IMSI`, `Ki`, `OPc`, and the **Milenage** algorithm to your card
   using your PC/SC reader (`pySim` or your card vendor's tooling). Pass `OPc`
   directly without re-deriving it from `OP`.
3. Confirm persistent `IMSI` readback and a valid local Milenage AKA test
   vector (`AUTS` check) before inserting the Nano-SIM into the **Waveshare
   M.2 5G Carrier** on Jetson Orin.

> [!NOTE]
> If you are provisioning **TB01** experimental blank USIM cards, see the
> verified PC/SC `T=0` connection rules and APDU layouts in
> [Hardware & TB01 Notes](reference/hardware-notes.md#tb01-programmable-usim-apdu-reference).
