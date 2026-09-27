# Subscription transfer and two-device acceptance — 2026-09-27

[简体中文](2026-09-27-subscription-sync.zh-CN.md)

Source base: `39dde4d0216dee973ed6cbf40ecb500e83c1ac74`, with the uncommitted
maintenance tooling and BSON fix described in the
[preparation record](2026-09-27-subscription-sync-preparation.md). Installed
applications remain Spark 0.2.0 / Jetson 0.5.1. Devices run ARM64 Python 3.12.3
(Spark) and 3.10.12 (both Jetsons); the temporary serial probe uses the installed
OAI Python environment and this repository's hardware/modem query parsers.

## Import evidence

The operator ran the staged tool with terminal sudo on Spark and supplied its
successful result. Source subscriptions: 4; target before: 1; planned/inserted: 3;
target after: 4. `existing_unchanged`, `source_static_unchanged`, `cleanup` and
`passed` were all true. The agent did not read the root-only backup files or
claim an independently exercised backup restoration.

- Private backup directory:
  `/var/lib/aoc-maintenance/subscription-sync-1790492951589900727`.
- Offline volume archive SHA-256:
  `a8f5fb41769e4d7ad59d5c281d6d6189665cfec77b2c382a56f5039bb63b1283`.
- Bundle SHA-256:
  `3e40ff4c69c064d36cc6f055e4423249f399b4e8af5269f3de17ee3b8a8a82ec`.

Initial independent SSH checks confirmed OAI still active, the OCUDU core/radio
inactive, no project containers, and the MongoDB volume retained. During the
subsequent OCUDU run, an authenticated, read-only MongoDB query independently
confirmed all four records: one IPv4 `oai` session, configured 5QI 9, and BSON
int64 SQN for every subscription. Raw identities, credentials and SQN values
were not exported. Dynamic authentication later advances SQN normally; the
preservation claim applies to import, not to subsequent network activity.

## Device and core acceptance

The user had separately commissioned OAI start/stop scripts. Inspection of the
installed Jetson script confirmed that stop first terminates the controller,
then invokes its fixed management helper to preserve Wi-Fi and disable automatic
modem default routes. Both stops passed; no other controller was active. Fresh
Tailscale peer endpoint route lookups, including its transport mark, selected
Wi-Fi on both devices; Wi-Fi was also their only default route.

A temporary query-only probe used exclusive serial access and checked controller
inactivity before opening the modem. It queried current SIM fingerprint, serving
cell, registration, data context and address. It never called modem writes,
changed SIM/settings, or issued a recovery/reset. Both SIM fingerprints were
matched with the source subscription inventory. The same probe established
working OAI registration and bound data paths before switching.

Switch sequence: stop both OAI Jetson controllers → stop Spark OAI with its
installed script → start OCUDU with `~/aoc-ops/spark/start.sh`. All twelve
Open5GS/data-network containers became healthy and gNB NG Setup succeeded.
Early samples correctly showed no registration/PDU; both modems subsequently
reattached naturally without an explicit reset or reconnect.

| Current evidence during OCUDU operation | matt Jetson | zihao Jetson |
| --- | --- | --- |
| SIM matched to imported inventory | Yes, pre-existing target record | Yes, newly imported record |
| RAT / PLMN / band / PCI | NR5G-SA / 46003 / n78 / 666 | NR5G-SA / 46003 / n78 / 666 |
| Fresh modem registration | Registered | Registered |
| Data PDU / address pool | Active / valid | Active / valid |
| Core AMF mobility / connection | Registered / connected | Registered / connected |
| Core SMF session / QFI / 5QI | Active `oai` / 1 / 9 | Active `oai` / 1 / 9 |
| UE/core address correlation | Match | Match; distinct from matt |
| Bound gateway / UPF / public probes | All passed | All passed |

The UE samples were taken within one second of each other, and the core sample
approximately eleven seconds later showed two connected UE contexts and two
active data sessions simultaneously. Each probe used two small ICMP requests
bound to the discovered modem interface after verifying the route. Request/reply
traffic establishes bidirectional reachability, not throughput or unsolicited
downlink initiation. The OCUDU-specific ext-DN HTTP endpoint was not tested from
these temporary UE probes.

Fresh AMF logs contained two registration-complete events, one synchronization
failure match and no MAC-failure match. The bounded logs did not explicitly expose
an AUTS marker, so this run does not independently certify an AUTS exchange.
Final registration, current PDU state and user-plane results passed.

## Return to baseline and scope

OCUDU stop passed: all five project services inactive with zero PIDs, no project
core containers, no web listener; the database volume was retained. Spark OAI
was then started with its installed script, followed by both Jetson OAI controllers.
All three lifecycle commands passed. Final checks confirmed:

- OAI core, gNB, collector and web services active with zero automatic restarts;
  all nine OAI core/data-network containers healthy.
- Both Jetson installed `verify-jetson.sh` checks exited zero and reached their
  acceptance-success marker, covering bound probes, routes and service boundaries.
  Both public health endpoints report `ok`, version 0.3.0.
- Current OAI SMF shows the two mapped subscribers with activated `oai` sessions.
- OCUDU core/radio remain inactive, project containers absent, MongoDB volume
  retained. Final running platform is OAI, with the four subscriptions ready for
  the next OCUDU startup. No temporary probe holds a serial port.

The second Jetson was validated with the temporary query-only tool; its OCUDU
Console was not installed or commissioned. The other two subscriptions have
database/schema validation only, not hardware acceptance. No Gate, full fault
matrix, five-cycle requirement or database-restore acceptance is closed by this
single two-device switch test. The database backup remains private on Spark.

Only acceptance documentation changed in this follow-up. `make docs-audit
VENV=local/bootstrap-check` passed for 88 current documents, and `git diff --check`
passed. Earlier code/test changes remain uncommitted; this follow-up did not
repeat unchanged backend tests or frontend builds.
