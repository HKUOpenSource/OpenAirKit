# Architecture

## Product boundary

Agentic-OCUDU provides one 5G SA data network. OCUDU supplies the RAN and
Open5GS supplies the 5G core. The Spark Platform observes and operates the base
station. The Jetson Console observes and operates the UE modem. IMS, SIP and
voice services are outside the current product boundary.

```text
Jetson Console -> RM520N modem -> B210 / OCUDU gNB -> Open5GS -> external DN
                                      |
                               Spark Platform
```

## Component ownership

| Component | Owns | Must not own |
| --- | --- | --- |
| Jetson Console | Modem lock, bounded AT workflow, owned routes, UE state, `127.0.0.1:8878` | RAN/core lifecycle or arbitrary shell commands |
| Spark Platform | Host/RAN/core evidence, history, events, bounded stack tasks, `127.0.0.1:8877` | Modem control or UE-only facts |
| OCUDU stack | B210, cell configuration, NGAP and radio metrics | Web sessions or platform data |
| Open5GS stack | Registration, PDU session, policy, N3/N4/N6 and subscriber state | RAN hardware or UI state |

Each application has its own configuration, SQLite database, runtime user,
systemd units, release version and rollback record. Web processes run without
general root privileges. Privileged actions pass through fixed helpers that
accept an operation allowlist rather than commands or service names.

## Network contract

The shared contract is versioned in `config/network-contract.json`. The current
deployment uses PLMN `460/03`, DNN `oai`, one IPv4 data PDU and the configured
`10.0.0.0/24` UE pool. Site-specific addresses and credentials stay outside
the repository.

## State semantics

Evidence quality and business health are independent. `ok`, `stale`,
`unavailable` and `unsupported` describe whether a value can be trusted.
Running, healthy and connected describe operational state. A UE is connected
only when fresh registration, PDU, address-pool, RAN-context and user-plane
evidence agree. Historical logs, an assigned IP or one ping cannot establish
current connectivity.

Collectors preserve source time and process generation. Restarts, log rotation
and counter resets create a new observation interval, preventing old devices,
false zero traffic or artificial rate spikes.
