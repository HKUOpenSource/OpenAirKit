# Open5GS core stack

This module is the core-network boundary for Agentic-OCUDU. The current release carries one IPv4 data PDU only:

- DNN `oai`
- IPv4 UE pool `10.0.0.0/24` (subject to the live-resource check)
- target 5QI `9`
- PLMN `46003`, TAC `1`, SST `1`
- Open5GS NFs and MongoDB in a project-owned Compose deployment

The stack is scoped to the single IPv4 data PDU above (excluding IMS, `ims` DNN,
SIP, and P-CSCF). Existing vendor or IMS contexts on a UE modem are left untouched.

Open5GS 2.8.0 and MongoDB 8.0.30 are pinned in the source and artifact locks. `stacks/open5gs/compose/render.py` injects `GLIBC_TUNABLES=glibc.pthread.rseq=1` on `mongo` so MongoDB 8.0.30 avoids TCMalloc per-CPU rseq allocation failures on Linux 7.0+ kernels. Build and Compose tooling is kept in this stack directory; production data and generated images stay outside Git.

## Ownership

The module owns its Compose project, bridge, volumes, MongoDB data, UPF TUN/N6 rules and ext-DN listener. It does not read another application's database, Docker project, launch script or service state. Site preflight checks B210, routes and conflicting listeners before starting this module.

## Required evidence before field deployment

1. Fixed Open5GS source/image and ARM64 build or manifest digest.
2. A clean MongoDB schema and explicitly imported subscriber; no copied database or SQN state.
3. AMF NGAP, SMF/UPF PFCP, N3/N6 routing and one data PDU in a no-RF test.
4. Real B210 registration, data PDU, bound-interface bidirectional probe and bounded stop/cleanup.

The module exposes structured NF/session data to the independent Spark collector when the selected Open5GS build provides it; unsupported fields remain marked `unsupported`, and UE connectivity requires separate live session and user-plane probes.
