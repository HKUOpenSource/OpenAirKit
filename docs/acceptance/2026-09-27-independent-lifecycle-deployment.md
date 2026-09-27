# OCUDU 0.6.0 hardware deployment and lifecycle validation

Date: 2026-09-27. Source base: `39dde4d0216dee973ed6cbf40ecb500e83c1ac74`
plus the reviewed, uncommitted lifecycle changes. Both commissioned ARM64 Jetsons
were upgraded from 0.5.1 to 0.6.0. Spark received the revised standalone lifecycle
scripts; its monitoring application remains 0.2.0.

## Deployment identity and boundary

- Jetson release: `8ade791a3317ad5e`; all 51 installed manifest files matched on both devices.
- Manifest SHA-256: `e297880d5a4ac2ec4f04395efbf76e113d7e61c62a977c62a8f0edee1340ae40`.
- Maintenance approval: `0b30462ac4a898a8c5f398114f682bdc0fc0c4a8acab826ef51597734329d127`.
- Spark lifecycle controller SHA-256: `b2867227b14f3678824cdb214bcea6c858c0430beaf7c4d028c4775db785549a`.

The operator activated the matching restricted approval on both Jetsons. Installation
used the exact approved release and existing site commissioning/authentication.
The installer retained rollback checkpoints; old operator scripts were backed up.
Only Web started during installation, device execution stayed stopped, and both
Jetson units remained disabled at boot. The new packaged shortcuts were installed
from the verified release. No application rollback was needed or exercised.

The review question was whether OCUDU can prepare, operate and clean up its own
runtime after initial site configuration. The call paths are documented in the
[development validation](2026-09-27-independent-lifecycle.md). Existing services
were stopped through their own lifecycle entry points to release shared resources.
After that boundary, OCUDU start/stop required no external preparation script,
manual data-route insertion or manual maintenance-mode exit. No recovery job or
modem reset was invoked. Existing management profiles remained site prerequisites.

## Hardware results

| Operation, seconds including SSH | Spark | Jetson A | Jetson B |
| --- | ---: | ---: | ---: |
| Upgrade | Script replacement | 12.45 | 11.70 |
| First start | 36.43 | 2.58 | 2.63 |
| Repeated start | 0.85 | 1.27 | 1.86 |
| Stop | 2.92 | 1.47 | 1.37 |
| Repeated stop | 0.63 | 1.35 | 1.22 |
| Start again from fully stopped | 36.36 | 3.74 | 3.39 |
| Final stop | 3.55 | 1.59 | 1.49 |

Service-start timings do not mean that the UE was already connected. Both devices
had fresh verified evidence by the first observation, 99.8 seconds after the first
Spark start began. After the complete stop/start cycle, both were again verified
at 106.7 seconds from Spark start; the reconnect observer itself took 22.3 seconds.
These are sampled upper bounds, not exact registration latencies.

- Both starts: all 12 Open5GS containers healthy, one successful N2 NG Setup,
  and healthy Spark monitoring. Core evidence showed two registered, connected
  subscribers with active PDU sessions and distinct address hashes.
- Each Jetson: fresh registration, active PDU, verified data path, protected
  management, observation enabled and automatic recovery paused.
- Both devices, before and after the full cycle: gateway, UPF, ext-DN and public
  ICMP plus ext-DN HTTP passed, bound to each modem interface. Wi-Fi was not used
  to substitute for cellular data acceptance.
- Completed stability windows: 61.1 and 60.8 seconds, seven samples each, with
  both devices passing throughout. Evidence age was at most 20 seconds per check.
- Repeated start preserved all service PIDs and monotonic start timestamps;
  restart counters remained zero. Repeated stop returned success.
- Each Jetson created one owned host route, reused existing correct routes,
  removed its route on stop and recreated it on start. Both cleanup checks
  confirmed no protocol-186 routes and exact preservation of other main-table routes.
- Stop released both Jetson listeners and device sockets; Spark had no remaining
  OCUDU project containers or service processes. SSH transport through Wi-Fi was
  confirmed on both devices before installation and during both OCUDU runs.

## Visible exceptions and limitations

The first private core-evidence script assumed every AMF context had an identity.
It failed on one deregistered, idle context without SUPI. The reader was corrected
to report such contexts separately, without changing application or core data.
The two identified active sessions passed; the next full start had no unidentified
context. No production identity or address is recorded here.

An initial stability attempt reached 54 seconds before a status read collided with
the maintenance helper's exclusive lock during repeated start. This interrupted
the observer, not the running services. The interrupted window was not accepted;
the completed windows ran after all lifecycle writes ended. This enforces the
documented rule against concurrent maintenance calls; no permission or lock was bypassed.

This validates upgrades of two already commissioned installations and two bounded
OCUDU runs. Fresh 0.6.0 password setup/commissioning, hardware rollback, unplug
fault injection, five-cycle endurance and throughput stress testing were not
performed. Prior unit and isolated Linux tests remain separate evidence.
Private operation logs and observations are retained under ignored
`local/independent-lifecycle-20260927/`. No subscriber import or authentication-state
rollback was performed.

## Final state

Both Jetsons retain release 0.6.0 and the matching maintenance approval; Spark
retains its new lifecycle scripts. All OCUDU services are stopped, Jetson boot
startup remains disabled, and no owned routes remain. The original OAI runtime
was restored after acceptance: Spark service readiness took 23.65 seconds,
and the two Console starts took 13.00 and 14.78 seconds. Both expected active
sessions were observed 233.5 seconds after Spark restoration began, within the
300-second limit. Final Console health, distinct core session addresses, and
modem-bound gateway, UPF and public probes passed on both devices. No reset was
used to accelerate the second device's reconnection.

Documentation and release-boundary audits and `git diff --check` passed. The
accepted package was not changed during deployment; only the private evidence
reader was corrected. This result does not close the broader fault-matrix,
fresh-install, rollback or endurance roadmap gates.

## Subsequent activation

At the user's subsequent request on the same day, OCUDU was started and left
running. Spark startup took 36.39 seconds; the two Console starts took 3.21 and
3.53 seconds. All 12 core containers were healthy and N2 was ready. Both devices
provided fresh registration and active-PDU evidence; each passed modem-bound
gateway, UPF, ext-DN, public ICMP and ext-DN HTTP checks. Management transport
selected Wi-Fi on both devices. Observation remains enabled with automatic
recovery paused; boot-start settings were unchanged. The release and approval
identities above still apply. This activation supersedes the stopped OCUDU state
at the end of the earlier acceptance run.
