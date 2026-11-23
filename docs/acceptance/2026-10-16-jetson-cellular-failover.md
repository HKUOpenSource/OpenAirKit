# Jetson automatic cellular / Wi-Fi switching — 2026-10-16

[简体中文](2026-10-16-jetson-cellular-failover.zh-CN.md)

## Result

**One real gNB outage passed the bounded fallback/failback check.** The existing
platform changed the ordinary IPv4 default to Wi-Fi approximately **11 seconds**
after the stop request. After the start request, cellular data returned in
approximately **61 seconds**, then the default changed back to cellular about
**23 seconds later**: **84 seconds** from start request to failback overall.

The independent management SSH session stayed connected through the cycle and
exited normally after observation. The Wi-Fi gateway replied to all **174**
probe sequences recorded in the approximately 174-second fault/recovery window.
Wi-Fi-bound public ICMP had some losses; this is not a claim that all management
network packets were lossless.

The gNB's configuration was preserved, core and platform services stayed active,
and cellular connectivity remained healthy for 30 seconds after failback.
No second outage, manual route switch or manual modem recovery was performed.

## Environment, question and call path

Environment: Jetson Orin Nano, RM520N-GL, USB 3 / RNDIS; DGX Spark, B210,
OCUDU / Open5GS, n78 / 20 MHz / 1T1R. Platform 0.6.2, source base
`65cb1bdf050ff2549fb494a8e4695c78bb1de0bd` with the AT discovery correction
in the [access record](2026-10-16-jetson-rndis-at.md). Deployed Jetson manifest
SHA-256: `8c8308681da94eec2553d254c0ec1edae7359246de165c8dfe840013f7eef068`.

Question: does the deployed cellular-preferred default actually fall back on
radio loss and return after recovery, while retaining independent management?
No `.codegraph/` index existed. The relevant source path was
`Agent.reconcile_routes → apply_route → network.managed_defaults`, with data
evidence from sampling and `Network.probe`. No product source was changed.

The existing policy normally samples every ten seconds, promotes cellular after
two complete fresh successful probe sets and falls back after two failed sets.
Unavailable registration/PDU/interface evidence or evidence older than 20
seconds triggers fallback on the next reconciliation. Diagnostic host routes
remain bound to cellular, so recovery can be detected while Wi-Fi is default.
See [operations](../jetson-operations.md#recovery-and-connectivity).

## Bounded operation and management protection

- The operator ran the prepared one-shot administrator script on Spark. It
  stopped only the owned gNB service; the core and Jetson platform kept running.
  The start request followed approximately 60 seconds after the stop request.
- Before stopping, the script verified the running binary, installed runtime
  manifest and that the renderer would reproduce the existing configuration.
  A detached restoration watchdog was armed before the stop command. It would
  request startup on parent loss or at approximately 70 seconds. In this trial
  it restored the service on the parent's normal request.
- Management used an authenticated SSH connection from the local computer
  through Spark to the Jetson's Wi-Fi address. The connected-network return
  route stayed on Wi-Fi, independently of the experimental cellular default.
  A separate heartbeat kept this same SSH session open throughout the trial.
- The Spark script repeatedly checked the Wi-Fi-side SSH endpoint and a
  restricted, temporary observation endpoint. Management protection failure
  would have requested early radio restoration; none was reported.
- The Jetson observer only read routes, link state and service state and sent
  ICMP probes. The test tools did not write routes, SIM or modem settings.
  The platform itself performed the automatic default-route changes.
- Probe paths were Wi-Fi → gateway, Wi-Fi → public target, cellular → UPF and
  an unbound ordinary-public target without a dedicated diagnostic host route.
  All required baselines passed before injection. The first read-only preflight
  used a nonresponding ordinary target and was retained; it injected no fault.

Private helper SHA-256 values:

| Helper | SHA-256 |
| --- | --- |
| One-shot Spark controller | `ee8e16d1c87106b6cb228330e81a1a85ce3f5bd11d92b4cd883a1894a7096189` |
| Final Jetson observer | `f73aed328d95e767549585e6570e9d2216b2950b426499dcc6664586b3c97bb6` |

## Measured timeline

All route and probe intervals below use the Jetson's monotonic clock. Controller
events were marked on that same observer; Spark's separate monotonic clock was
not subtracted from Jetson timestamps. Routes were sampled approximately once
per second and each reported route transition was followed by another matching
sample. Treat switch timing as approximately **one-second resolution**.

| Milestone | Time, Asia/Shanghai |
| --- | --- |
| gNB stop requested | 17:42:44.796 |
| gNB inactive confirmed to observer | 17:42:45.248 |
| Ordinary default first observed on Wi-Fi | 17:42:55.753 |
| gNB start requested | 17:43:44.831 |
| gNB running confirmed to observer | 17:43:49.750 |
| First successful cellular-bound UPF reply after start | 17:44:45.780 |
| Ordinary default first observed back on cellular | 17:45:08.777 |
| Final healthy observation completed | 17:45:38.876 |

| Interval | Seconds |
| --- | ---: |
| Stop request → Wi-Fi default | **10.96** |
| Confirmed stop marker → Wi-Fi default | 10.51 |
| Start request → first cellular data reply | **60.95** |
| First cellular data reply → cellular default | **23.00** |
| Start request → cellular default | **83.95** |

The approximately 61-second part includes wireless/session/data reacquisition;
those internal stages were not separately timed. It is distinct from the
approximately 23 seconds from first data success to default-route promotion.
The service was inactive for about 64.48 seconds including startup time, despite
the deliberate hold being approximately 60 seconds from stop to start request.

## Evidence and final state

During outage, the platform-owned Wi-Fi default appeared at metric 5 and the
cellular metric-10 default was removed. The existing DHCP defaults remained.
The ordinary-public route read selected Wi-Fi and an independent unbound probe
returned 3/3 replies. After failback, cellular metric 10 was restored, Wi-Fi
remained available and the ordinary-public route selected cellular again.
The RNDIS interface itself stayed present with carrier; this was not simply a
kernel route change caused by deleting its host interface.

All **408** route/service samples, including baseline and recovery, retained
the Wi-Fi management path and active Jetson platform services. Within the
fault/recovery window, recorded probe-sequence outcomes were:

| Probe | Sequences with a reply / observed sequences |
| --- | ---: |
| Wi-Fi gateway | **174 / 174** |
| Wi-Fi-bound public target | 166 / 174 |
| Ordinary public target | 160 / 174 |

These windows are assigned by observation time, with possible boundary effects
of about one probe. The ordinary-public loss includes the expected interruption
before fallback; public-target losses are retained rather than hidden by the
successful SSH session.

The management SSH process exited with code 0 without being replaced. Across
the fault/recovery interval plus five seconds of preroll, 179 sequential remote
heartbeats were retained; their maximum generated interval was about 1.002
seconds. This is a remote heartbeat interval, not a network RTT or a measurement
of subsecond receive stalls at the local computer.

The Console subsequently showed registered 5GS, an active data PDU in the
expected pool, matching laboratory policy, healthy cellular-bound probes and
cellular egress. The PDU received a new address within the configured pool.
A final UPF probe bound to RNDIS returned 3/3, and an interface-bound ext-DN
HTTP request returned its expected health response.

The gNB configuration SHA-256 remained
`01d31327038022cb0c6d7112eebbaf2705468dfe6c535d595bf44ee5a1ab0394`.
The original core and observation services remained active. The detached
watchdog completed and was reaped; the temporary observer endpoint closed,
its ICMP processes exited and the management heartbeat completed normally.
No permanent test service or network change was left behind.

## Validation and limits

The helpers passed 18 offline checks covering preflight gating, event ordering,
watchdog startup on normal request, parent loss and deadline, terminal
detachment and failure reporting. Three separate offline checks covered the
transition-timing calculation. These checks are not hardware results; the live
evidence above establishes this single fault/recovery cycle. Paired-document
audit and diff whitespace checks passed.

This does not establish repeated-outage reliability, every existing application
socket's continuity, an upper bound for future recovery times, Wi-Fi failure
recovery, host/modem reboot behavior or IPv6 switching. Private helper sources,
raw probe output and device-specific addresses remain outside Git. This record
contains no SIM identity, credentials, SSIDs, BSSIDs or real management addresses.
