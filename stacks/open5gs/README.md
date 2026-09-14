# Open5GS core stack

This module is the core-network boundary for Agentic-OCUDU. The current release carries one IPv4 data PDU only:

- DNN `oai`
- IPv4 UE pool `10.0.0.0/24` (subject to the live-resource check)
- target 5QI `9`
- PLMN `46003`, TAC `1`, SST `1`
- Open5GS NFs and MongoDB in a project-owned Compose deployment

IMS, `ims` DNN, SIP, P-CSCF and a second PDU are intentionally outside this release. A modem may retain vendor or IMS contexts; the executor does not delete them or treat their absence as a data failure.

Open5GS 2.8.0 and MongoDB 8.0.30 are pinned in the source and artifact locks. Build and Compose tooling is kept in this stack directory; production data and generated images are never committed.

## Ownership

The module owns its Compose project, bridge, volumes, MongoDB data, UPF TUN/N6 rules and ext-DN listener. It does not read another application's database, Docker project, launch script or service state. Site preflight checks B210, routes and conflicting listeners before starting this module.

## Required evidence before field deployment

1. Fixed Open5GS source/image and ARM64 build or manifest digest.
2. A clean MongoDB schema and explicitly imported subscriber; no copied database or SQN state.
3. AMF NGAP, SMF/UPF PFCP, N3/N6 routing and one data PDU in a no-RF test.
4. Real B210 registration, data PDU, bound-interface bidirectional probe and bounded stop/cleanup.

The module must expose structured NF/session data to the independent Spark collector when the selected Open5GS build provides it. Unsupported fields remain `unsupported`; a process health check is not a UE/session proof.
