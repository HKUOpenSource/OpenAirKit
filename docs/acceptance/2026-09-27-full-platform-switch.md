# Full platform switch acceptance — 2026-09-27

[简体中文](2026-09-27-full-platform-switch.zh-CN.md)

Source baseline: `39dde4d0216dee973ed6cbf40ecb500e83c1ac74`, with the existing
uncommitted subscription-sync changes preserved. One complete dual-console
OAI → OCUDU → OAI round trip passed. The final running platform is OAI; both
OCUDU Consoles remain installed and stopped. Live execution was on 2026-09-27,
approximately 16:00–16:11 Hong Kong time. Preparation failures and their fixes
are retained below rather than counted as successful first attempts.

## Observed baseline and release

- Spark is running OAI core, gNB, collector and Web services. All nine OAI
  core/data containers report healthy. Unrelated containers remain untouched.
- Both Jetsons passed the installed OAI `verify-jetson.sh`: service and
  loopback listener, RNDIS routing, interface-bound gateway/UPF/ext-DN/public
  probes, service privilege boundary and fixed helper checks. Both report
  Console version 0.3.0.
- The first Jetson has OCUDU Console 0.5.1, release `186b6c4659cc5e14`.
  All 48 manifest-listed files matched their hashes. Only these files and the
  manifest were transferred, including the ARM64 Python 3.10 offline wheels;
  no installed virtual environment, device configuration, password or state
  was copied. The extracted release passed the existing content-addressed
  package verifier.
- At initial inspection, the second Jetson had no OCUDU installation or maintenance helper.
  The staged bundle passed its non-mutating device preflight, complete payload
  checksums and native `visudo` validation for the existing fixed-action policy.
- The first Jetson's current SSH transport route was verified over Wi-Fi with
  the Tailscale transport mark. The second did not expose a direct peer
  endpoint; direct transport verification is therefore pending. Before its
  installation, the preparation script requires Wi-Fi-only IPv4 defaults and
  no modem IPv6 default after the existing OAI stop helper protects management.

## Reviewed preparation artifacts

Private staging is under `local/full-switch-20260927/` locally and
`~/aoc-ops/full-switch-20260927/` on the devices. Production addresses and
operator commands remain there or in the private conversation.

| Artifact | SHA-256 |
| --- | --- |
| Maintenance approval archive | `0f80651b7f2da7b17fa7f39eaf55450aab6fc2e9d41211ffd5b2463a81dbd952` |
| Existing bootstrap | `de14da6063b3c658457d49d76b6c2314bb060ca3ab6ed5e23a51d043ad98f49c` |
| Corrected terminal preparation script | `4f8f14499d8dc5d7356144756bf03bef4c4ad0878346a99a8b340b43cb1d75f7` |

The terminal script validates the archive before loading its installer, stops
only the second Jetson's OAI Console, installs offline with a new interactively
entered password, commissions that device's own SIM, installs the existing
restricted maintenance policy, and stops the new Console. Its finalization
attempts OAI restoration and runs the installed OAI acceptance check. A changed
fresh-install baseline aborts; partially completed installs require inspection
before retrying. New OCUDU units must remain disabled at boot.

The route operation adds only the OCUDU ext-DN host route through the detected
known modem interface, tagged with protocol 187 and a private root-owned
journal. It rejects conflicting routes. Cleanup removes only a matching owned
route and preserves pre-existing routes. Four isolated mock checks passed:
conflict rejection, changed-route deletion rejection, exact owned cleanup and
idempotent repeated addition. Initially neither device had an exact ext-DN
host route; the operator's subsequent attempt created it on the first device.

## First operator attempt and corrections

The operator reported successful offline installation on the second Jetson,
followed by `ModuleNotFoundError: No module named 'serial'` during takeover.
The wrapper had called takeover inside the OS Python process, which lacks
application dependencies. Its finalization stopped OCUDU, restored OAI and
passed the OAI acceptance check. Independent inspection confirmed the expected
release is installed, its own Python environment imports pyserial 3.5, OAI is
active, both OCUDU units are inactive, and the maintenance helper is absent.

The first Jetson reported `New route verification failed`. Independent readback
confirmed the route was added correctly: iproute2 rendered protocol 187 as its
standard name `isis`, while the wrapper required the numeric string. Numeric
`ip -N -j` output reports 187 as expected. The route remains present, pending
journal-aware verification and eventual cleanup; it has not been rolled back.

The corrected wrapper requests numeric protocol output and runs takeover
through the installed application virtual environment. Its new `finish-install`
operation validates the existing release and protected config, requires the
observed uncommissioned state with no maintenance approval, and continues
without reinstalling or replacing the Console password. Existing archive and
release digests are unchanged. Six local checks passed: interpreter selection,
numeric protocol readback and the four route safety cases. The updated script
was staged on both devices; the second device passed complete installed-release,
runtime import and non-mutating bootstrap checks. This corrects the private
test wrapper, not the deployed OCUDU release.

## Completed round trip

The operator completed the corrected second-device commissioning in 23.7 seconds:
its own SIM was bound, the approved maintenance helper was installed, the temporary
route was added, and OAI was restored with acceptance passing. The first-device
route recheck returned ready without creating another route. Independent checks
confirmed both approval bundles, stopped OCUDU units and running OAI before testing.

Both OAI Consoles were stopped before Spark OAI. Wi-Fi was the only IPv4 default
on both Jetsons; actual SSH peer endpoint routes, including the Tailscale mark,
were verified over Wi-Fi on both. Spark OCUDU started before the two OCUDU Consoles.
Both Consoles exited maintenance with automatic recovery paused. No explicit
modem reset, forced reconnection or subscription rewrite was performed.

| Measured command duration, seconds | Spark | First Jetson (matt) | Second Jetson (zihao) |
| --- | ---: | ---: | ---: |
| Stop OAI | 5.16 | 2.61 | 5.18 |
| Start OCUDU | 36.37 | 2.59 | 2.73 |
| Stop OCUDU | 2.77 | 1.11 | 1.18 |
| Restore OAI | 23.80 | 12.90 | 15.01 |

Durations include SSH and lifecycle readiness checks. First sampled dual-device
OCUDU connectivity was 94.53 seconds after the Spark OCUDU start command began.
On the return leg, OAI SMF first showed both expected active sessions after
156.59 seconds; the second device recovered later than the first. Both observations
were within the 300-second bound. These are observed recovery bounds, not precise
radio interruption measurements or performance benchmarks.

## Live acceptance evidence

| Check | First Jetson | Second Jetson |
| --- | --- | --- |
| Fresh OCUDU Console registered / PDU active / connected | Pass | Pass |
| Management protected / recovery paused | Pass | Pass |
| Modem-interface-bound gateway / UPF / ext-DN / public ICMP | Pass | Pass |
| Modem-interface-bound OCUDU ext-DN HTTP health body | Pass | Pass |
| Independent SIM and UE address correlation with core | Pass | Pass |
| Final OAI six-stage installed verification | Pass | Pass |

OCUDU had 12 healthy containers, successful N2 setup, two connected AMF devices,
and two active `oai` sessions, each with QFI 1 / 5QI 9. The two distinct UE address
hashes matched their respective modem readbacks. Serial readbacks were performed
only after releasing the Console and before stopping the corresponding core.
The existing OAI baseline also had both matching active sessions; final OAI SMF
again showed both expected devices with activated sessions and matching addresses.

Seven paired samples spanning 60 seconds all reported fresh OCUDU connectivity,
registration, active PDU and protected management; the observation loop completed
in 60.9 seconds. Automatic recovery remained paused. All 12 repeated lifecycle
checks passed: start and stop for each of the two platforms on all three hosts.
Repeated OCUDU starts preserved process IDs. Sampled systemd restart counts were
zero, and opposite-platform controllers were inactive. Stop checks verified zero
PIDs, released Web listeners/device sockets and no remaining core containers.

## Final state, cleanup and limits

- Spark OAI core, gNB, collector and Web services are active; all nine OAI
  core/data containers are healthy. Both OAI Consoles are active and passed
  the installed service, listener, routing, data-probe and privilege checks.
- All five Spark OCUDU services and both OCUDU services on each Jetson are
  inactive with zero PIDs. Both Jetson OCUDU units remain disabled at boot.
  The second device's commissioned 0.5.1 installation is retained.
- The OCUDU MongoDB volume remains present. The previously synchronized four
  subscriptions were not reimported; normal network authentication may advance SQN.
- Terminal route cleanup was requested while restoring OAI to avoid extending
  the outage for interactive sudo. Independent final numeric route-table reads
  show neither temporary ext-DN host route remains. Root-only cleanup journal
  deletion was not independently inspected.
- Unrelated containers were not operated on. No public API or deployed release
  code changed. Private tooling and raw execution evidence remain ignored.

The successful run includes explicit route preparation and exiting Console
maintenance. The existing standalone start scripts certify service readiness;
they do not add the OCUDU ext-DN route or automatically leave maintenance.
Future switch automation must preserve these prerequisites. This single round
trip does not certify repeated-cycle reliability, throughput, failure injection,
backup restoration or the other two subscriptions without hardware.

Investigation followed the private wrapper → installed takeover → modem runtime
path and the route add → iproute2 JSON → ownership check path. The two wrapper
regressions and four route safety tests passed. Final documentation passed
`make docs-audit VENV=local/bootstrap-check` (90 current documents) and
`git diff --check`. Earlier subscription acceptance is documented
[separately](2026-09-27-subscription-sync.md).
