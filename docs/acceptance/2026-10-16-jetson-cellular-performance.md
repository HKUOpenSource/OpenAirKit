# Jetson cellular performance — 2026-10-16

[简体中文](2026-10-16-jetson-cellular-performance.zh-CN.md)

## Result and scope

A policy-aligned follow-up completed **600 seconds**, including 120-second
measurements of **9.73 Mbps uplink** and **59.71 Mbps downlink**. Both cellular
probe paths returned **600/600** replies. All sampled ordinary defaults selected
cellular. The existing cellular-preferred / Wi-Fi-fallback policy was preserved;
actual failure-triggered switching was not injected or timed.

The initial three paired TCP rounds had median receiver goodput of **9.63 Mbps
uplink** and **60.08 Mbps downlink**. That first observation stopped after
**359.45 seconds** when an additional continuous-Wi-Fi guard detected carrier
loss. Continuous management availability was not established. The initial
attempt and the later policy clarification are recorded separately below.

Environment: Jetson Orin Nano / RM520N-GL / RNDIS, USB 3 negotiated at
5000 Mbps; Spark / B210 / OCUDU / Open5GS, n78, 20 MHz, 1T1R. Application
0.6.2, source base `65cb1bdf050ff2549fb494a8e4695c78bb1de0bd` with the AT
discovery correction documented in the [access record](2026-10-16-jetson-rndis-at.md).
The deployed Jetson manifest SHA-256 was
`8c8308681da94eec2553d254c0ec1edae7359246de165c8dfe840013f7eef068`.
Test window: approximately 16:57:50–17:03:50, Asia/Shanghai.

## Question, path and containment

Question: what TCP goodput and short-term continuity does the commissioned
cellular path provide while preserving management Wi-Fi? No `.codegraph/`
index existed. This operation changed no product source.

Path: Jetson iperf client → RNDIS → Quectel NAT → experimental NR cell →
gNB → UPF → temporary server on Spark's N6 bridge address. This measures the
laboratory user-data path, excluding public Internet capacity.

- Official ESnet iperf **3.22** was built in private user directories on both
  devices, without system installation or new privileges. Source SHA-256:
  `1c0d0fb02c52626111d6e132db80edfbf27bbaff8bd9245df2a371dcb0b35a92`.
- Every client test used IPv4 TCP, one stream, a 3-second omitted warmup,
  `-B <RNDIS_ADDRESS> --bind-dev <RNDIS_INTERFACE>`, JSON output and finite
  connect/send/receive timeouts. Downlink added `-R`. The strict device bind
  uses `SO_BINDTODEVICE`, as described by the [official manual](https://software.es.net/iperf/invoking.html).
- An invalid-device negative check failed before connecting. Live `ss`
  observations showed the device scope on both control and data sockets.
  All 71 route samples selected RNDIS, and the server observed the UPF's N6
  source. These are independent evidence that test load did not use Wi-Fi.
- The server listened only on the laboratory bridge address at a high port,
  with a bounded lifetime. No firewall rule, default route, network profile,
  modem setting, SIM, core configuration or service lifecycle was changed.
- Separate 1 Hz ICMP streams bound to RNDIS probed UPF and N6; another bound
  to Wi-Fi probed its management gateway. Every approximately five seconds,
  the guard checked interface identity/carrier, route selection, the Wi-Fi
  gateway route and management overlay route. Wi-Fi carrier loss stopped load.
- Initial preflight incorrectly required RNDIS `operstate=up`; this device
  reports `unknown` while `IFF_UP`, `LOWER_UP` and carrier are set. It stopped
  before throughput traffic. The corrected guard used flags/carrier.

## Completed throughput measurements

Each entry is receiver goodput from a completed 30-second measurement after
warmup. TCP retransmissions are the sender's reported counts, not an ICMP loss
percentage or a direct radio-error count.

| Round | Uplink Mbps | Uplink retransmits | Downlink Mbps | Downlink retransmits |
| --- | ---: | ---: | ---: | ---: |
| 1 | 9.63 | 166 | 60.50 | 645 |
| 2 | 9.63 | 156 | 60.08 | 39 |
| 3 | 9.82 | 156 | 59.52 | 474 |
| Median | **9.63** | — | **60.08** | — |

A subsequent intended 120-second uplink was interrupted by the Wi-Fi guard
after about 91 seconds including warmup. It has no completed receiver result
and is excluded from this table. The intended 120-second downlink and remaining
soak window were not executed. The aborted client's zero receiver summary is
incomplete peer reporting, not evidence of zero delivered cellular traffic.

## Continuity and management result

| Bound probe | Replies / sent | Loss | Mean RTT ms | p95 RTT ms | Maximum RTT ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Cellular → UPF | 359 / 359 | 0% | 75.63 | 281 | 413 |
| Cellular → N6 | 359 / 359 | 0% | 75.40 | 281 | 412 |
| Wi-Fi → management gateway | 357 / 359 | 0.56% | 12.27 | 53.7 | 312 |

UPF baseline mean RTT was 26.83 ms. Downlink-load phase means were
206.80 / 210.24 / 257.70 ms, showing a material increase under saturation.
This and the TCP retransmissions warrant further queue/radio investigation;
the test does not identify their cause.

RNDIS kept the same interface identity and accumulated no RX/TX errors or
drops. All 71 Jetson service samples and all 37 Spark service samples were
active. Live Console observations during load showed registered 5GS, an active
data PDU and matching laboratory policy. This sampling does not prove absence
of every transient radio event.

Wi-Fi supplicant logs recorded multiple AP associations and channel changes,
with two disconnect events in the test window. A carrier-down observation at
17:03:50 triggered the guard; NetworkManager then re-associated and recovered
its lease automatically. Additional roaming occurred after load stopped.
The subsequently observed Wi-Fi signal was approximately −75 dBm on 5 GHz.
These observations establish roaming/disconnection, but do not establish its
root cause or a causal relationship to cellular load. No AP pinning, Wi-Fi
restart or other network mutation was attempted.

## Cleanup, checks and limitations

The client, probe processes, temporary server and read-only Spark sampler were
stopped. The server port was confirmed closed. Management Wi-Fi returned to
connected, with **15/15** gateway replies. A fresh cellular-bound UPF probe
returned **3/3**, and cellular-interface-bound ext-DN HTTP returned its expected
health response. gNB, core and platform services remained active.

The helper sources passed Python syntax checks, and raw JSON/ping output was
analysed outside Git. Private artifacts and binaries remain in access-controlled
user work directories; no credentials, real management addresses, SSIDs, BSSIDs,
raw logs or captures are included here. Documentation audit and diff whitespace
checks cover the added paired record.

The interrupted phases were subsequently repeated under the clarified policy
below. Wi-Fi continuity remains a separate management-path observation.
This result does not cover UDP loss/jitter, multiple streams, simultaneous
bidirectional capacity, long-duration reliability or failure recovery. USB 2
was not tested; these completed throughput results used USB 3.


## Policy clarification and completed follow-up

The operator clarified the intended policy: healthy cellular is the ordinary
IPv4 default; unavailable cellular falls back to Wi-Fi. Continuous Wi-Fi carrier
was an additional condition imposed by the first test, not this routing policy.
Its earlier interruption does not invalidate the completed throughput results
or establish that the requested default-route policy failed.

Read-only source inspection followed `Agent.reconcile_routes → apply_route →
network.managed_defaults`. The existing policy promotes cellular after two
complete fresh successful probe sets, falls back after two failed sets, and
falls back on the next reconciliation when registration/PDU/interface evidence
is unavailable or older than 20 seconds. Sampling normally runs every 10 seconds.
See [routing behavior](../jetson-operations.md#recovery-and-connectivity).
Live route reads confirmed the cellular default, retained Wi-Fi gateway route
and management overlay route. No deployed policy or configuration was changed.

A second, separate **600.01-second** observation recorded
Wi-Fi conditions without terminating healthy cellular traffic. It retained
strict cellular socket binding and would stop load if the cellular interface
or test route changed. The window included a 30-second baseline, 120 seconds
of uplink, 120 seconds of downlink, warmup/gaps and a final idle observation.

| Completed measurement | Receiver Mbps | Sender TCP retransmissions |
| --- | ---: | ---: |
| 120-second uplink | **9.73** | 426 |
| 120-second downlink | **59.71** | 3591 |

| Path | Replies / sent | Loss | Mean RTT ms | p95 RTT ms | Maximum RTT ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Cellular → UPF | 600 / 600 | 0.00% | 75.15 | 300.00 | 431.00 |
| Cellular → N6 | 600 / 600 | 0.00% | 71.35 | 300.00 | 430.00 |
| Wi-Fi → gateway | 593 / 599 | 1.00% | 25.15 | 185.00 | 335.00 |

All **119** sampled ordinary-default and test-endpoint routes
selected cellular. Jetson service samples were active, and RNDIS accumulated no
RX/TX errors or drops. Wi-Fi probe loss remained a separate observation;
it was not counted as cellular failure. No five-second sample observed Wi-Fi
carrier down during this second window; shorter events are not excluded.
TCP retransmissions and increased loaded latency remain visible in the results.

The original local SSH Web tunnel exited during this follow-up. The device's
local services and bound cellular probes continued. Recreating only that
loopback tunnel restored a healthy Web/device response and fresh registered,
active-PDU Console evidence. The cause of the tunnel exit was not determined;
this observation does not prove uninterrupted remote management transport.

After completion, the temporary throughput server and its sampler were stopped,
the listening port was closed, and no iperf load remained on the Jetson.
The existing default remained cellular with Wi-Fi available as fallback.
No radio, modem, platform or core service was restarted. The existing 106 Jetson
backend tests passed; paired-document audit and whitespace checks passed.

This completes the bounded cellular throughput/continuity observation under
the clarified policy. No deliberate cellular outage was injected, so actual
on-site Wi-Fi failover and return-to-cellular timing remain unmeasured.
Specific connected-network and management routes retain their usual precedence;
IPv6 failover is outside the implemented policy.

A subsequent, explicitly authorized real gNB outage verified both automatic
transitions; its measured timing and management evidence are in the
[failover record](2026-10-16-jetson-cellular-failover.md).
