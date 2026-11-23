# Jetson RNDIS AT interface discovery — 2026-10-16

[简体中文](2026-10-16-jetson-rndis-at.zh-CN.md)

## Scope and source

- Environment: Jetson Orin Nano, Linux ARM64 / Python 3.10, RM520N-GL over USB 3,
  firmware `RM520NGLAAR03A03M4G`, NetworkManager 1.36.6.
- Application: 0.6.2; source base `65cb1bdf050ff2549fb494a8e4695c78bb1de0bd`
  plus uncommitted AT discovery changes.
- Corrected content-addressed release: `d9e26be64b45c6b9`.
- Corrected manifest SHA-256:
  `8c8308681da94eec2553d254c0ec1edae7359246de165c8dfe840013f7eef068`.
- This record contains redacted results only. Private configuration, SIM
  identifiers, credentials and original logs remain outside the repository.

## Question, call path and impact

Question: why does commissioning time out on `AT` after successfully creating
an RNDIS data interface?

There was no `.codegraph/` index in this checkout. Source inspection followed
`manage.commission → hardware.discover → Modem.fingerprint → Modem.open`.
The service's `site_guard` and `network.inspect` also use `hardware.discover`.

Observed USB layout after RNDIS activation:

| Interfaces | Function |
| --- | --- |
| `00/01` | RNDIS control / data, bound to `rndis_host` |
| `02` | DIAG, first serial function |
| `03` | GNSS, second serial function |
| `04` | AT, third serial function |
| `05` | Modem, fourth serial function |

The previous fixed AT interface `02` selected DIAG in this layout. The corrected
example uses `04`. Configuration permits the two supported explicit values,
`02` and `04`; discovery verifies the complete serial/data layout and rejects a
mismatch before any serial port is opened. Serial-first layouts with data at
`04` retain AT interface `02`. Unknown layouts and multiple matching modems are
rejected. Selection does not depend on the Linux `ttyUSB` numbering.

The site bootstrap also encountered an `nmcli` error when assigning
`connection.uuid` in a connection creation command. Loading a dedicated keyfile
with the fixed UUID resolved this; its driver match and `never-default` setting
were verified through the device's libnm. This site bootstrap is private and is
not a new repository deployment entry point.

## Completed checks

- `make test-jetson-backend`: **106 tests passed**, including six new USB topology
  cases and explicit configuration validation for supported AT interfaces.
- `make docs-audit`: passed; `git diff --check`: passed.
- The corrected ARM64 package passed manifest and content verification locally
  and on the Jetson.
- Real, read-only discovery selected the AT port corresponding to USB interface
  `04` and the data interface under the same physical modem.
- The same live topology with configuration `02` was rejected with an expected
  interface `04` error. This test opened no serial ports.
- RNDIS was enumerated and obtained its local IPv4 address during site setup.
  Management Wi-Fi remained available. SIM identity matched the experimental
  card without exporting its value.

## Deployment and remaining validation

The initial Web installation responded with HTTP 200, but commissioning stopped
on the incorrect AT interface. The corrected release was then installed with
the existing login preserved, and AT queries succeeded through interface `04`.

Restoring ModemManager after the earlier failure had caused NetworkManager to
remove the ordinary Ethernet device and expose a broadband modem instead.
The bounded site handoff reannounced the network device, then rebound only that
modem's RNDIS network function once. The serial interfaces, modem power,
NetworkManager daemon and management Wi-Fi were not restarted. The Ethernet
profile then activated and commissioning succeeded.

Both platform services are active. The authenticated Console displayed fresh
SIM, host RNDIS interface and management fallback checks as healthy. Its
independent access checks reported **not registered**, **PDU inactive** and
**lab policy mismatch**; the observed n1 serving cell was not the target n78
cell. The bootstrap's immediate post-start report had captured the cached
maintenance snapshot; subsequent live Console evidence confirms observation
resumed. Automatic modem recovery remains paused.

RNDIS DHCP and Web health do not prove NR registration, AKA/SQN synchronization,
a valid PDU session, or bound data connectivity. Those checks and the full
lifecycle acceptance test remain pending. No rollback of the corrected release
has been performed on hardware. No SIM or core credentials were modified during
this platform deployment.

## Bounded radio inspection

A subsequent maintenance inspection confirmed that the inserted SIM matched the
commissioned card, was ready, and that modem capability, carrier policy and
enabled SA bands included n78. SA was not disabled. After confirming QSCAN mode
support, one NR-only extended scan returned a normal `OK` terminal response and
12 PLMN/cell records, including commercial n78 cells. None matched the target
laboratory cell. A scan with an inserted SIM is not definitive proof that the
gNB is not transmitting.

A read-only `EF.FPLMN` query also found the target PLMN in the SIM's forbidden
list. Its origin and age were not established. This requires investigation as a
potential automatic-selection obstacle; the modem's handling of this entry for
the programmed home network was not verified. It does not establish a rejection
by the current core or an authentication-key mismatch. See [3GPP TS 31.102 section 4.2.16](https://www.etsi.org/deliver/etsi_ts/131100_131199/131102/17.08.00_60/ts_131102v170800p.pdf).

No SIM update, band/mode configuration write, cell lock or modem restart was
performed. Maintenance mode was exited after the completed scan. Fresh Console
evidence showed serial ownership resumed and management fallback healthy;
registration and the data PDU remained unverified. Spark RF evidence and target
selection still require investigation before attempting data connectivity.

A separate read-only Spark export confirmed a fresh scheduler feed, N2
association, healthy core containers and a USB 3 B210 connection. No UE radio
contexts were reported. The complete current gNB log, spanning approximately
15 hours, contained 46,948 RF underflow and 237 late events, with underflows
also present in the minutes immediately preceding inspection. These totals are
not per-second rates; two short subsequent collector windows reported zero
new events. Warning-level PHY/RRC logging cannot prove an absence of random
access attempts.

The CPU governors were already set to performance and the binary was built in
Release mode. All observed gNB threads allowed every CPU, including both core
types. This motivates a bounded CPU-affinity experiment; neither these
observations nor the aggregate CPU utilization establish its root cause.

The one-shot affinity experiment recorded 17 underflows during a 30-second
baseline and 536 underflows plus 39 late events during the 60-second trial.
This assignment was not adopted. The script and its independent watchdog both
restored the original masks, and a separate SSH readback confirmed every
original thread mask. The gNB PID was unchanged. The final log read had not yet
covered the restored observation interval, so its zero event count was not
treated as proof of recovery. No permanent affinity configuration was written.

## B210 transport isolation

The installed official UHD benchmark completed 30 seconds of simultaneous
single-channel TX/RX at 23.04 Msps with `sc12` on the wire. It reported zero
underruns, overruns, dropped samples, late commands, timeouts and sequence
errors. The original gNB restarted successfully, its generated configuration
was byte-for-byte preserved, and N2 readiness passed. The core and SIM were not
modified. The operator confirmed that the antennas cover the laboratory
frequency.

This benchmark used the tool's default `fc32` host format. Inspection of the
deployed OCUDU source showed that its UHD streamer instead uses `sc16` host
samples. The result therefore establishes short-duration throughput for the
tested conversion path, not all gNB conversion or deadline behavior. A
subsequent fresh Jetson Console observation still showed no verified target
cell, registration or data PDU. The remaining format path and air-interface
validation must not be inferred from the benchmark's zero error counters.

The subsequent native-format comparison used `sc16` host samples with each of
`sc12` and `sc16` on the wire for 15 seconds. Both completed with all reported
error counters zero. In the actual gNB, the 60-second `sc12` baseline recorded
41 underflows; the 90-second `sc16` observation recorded 44. Neither recorded
overflows or late events in those windows. Logs were flushed by stopping the
service before counting. The short comparison did not eliminate the problem
or establish a format fault. Its temporary unit override was removed, the
original `sc12` service restarted, and configuration preservation was verified.

## SIM selection metadata

A further inspection read file metadata before bounded READ BINARY operations.
It confirmed MNC length 2, a programmed IMSI home network matching the target,
and a 90-byte forbidden-PLMN file containing the target. The equivalent-home
service was available; that 12-byte file was read successfully but was not
fully decoded by the strict PLMN parser, so its membership remains unresolved.
Home/operator priority lists retained vendor-network entries. The user priority
file was not read because metadata failed the bounded-file checks.

The helper passed 11 offline parsing and command-boundary checks. No SIM
updates, authentication commands, active scans or modem configuration writes
were issued. Platform observation resumed. The next proposed operation is a
separate, explicitly authorized target-slot correction; it has not been
performed as part of these read-only checks.

## Authorized target forbidden-entry correction

The operator subsequently explicitly authorized and executed a separate
correction. The helper backed up the 90-byte forbidden file privately, updated
only the target's three-byte slot to the unused value, and read it back. The
other 87 bytes were unchanged. No IMSI, authentication keys, PIN/ADM, other SIM
files or core configuration were changed, and no direct SIM authentication or
administrative-code command was sent. The helper passed 17 offline checks.

The reviewed CFUN 0/1 functionality refresh completed and full functionality was
confirmed. The script then stopped during post-refresh verification, before
sending its authorized NR scan; that scan was not attempted. Sampling resumed.
The original operation ledger and private backup were retained; the SIM update
was not retried. Persistence after the refresh still requires a fresh file read.

The additional equivalent-home bytes showed both decodable entries and a
malformed three-byte entry; no correction to that separate file was attempted.
After restoring the local SSH tunnel, fresh Console evidence again showed the
SIM and host RNDIS interface healthy, management fallback verified, a commercial
n1 cell in limited service, no 5GS registration and no valid data PDU.

The read-only follow-up confirmed the same commissioned SIM, readiness and full
radio functionality. The forbidden file reported through the AT interface was
now 60 bytes, rather than the earlier 90; the target was absent. The underlying
reason for the reported size difference was not established. The old fixed-size
post-refresh read was therefore not a reliable verification method.

The previously unsent, explicitly authorized NR scan then completed normally.
It reported the laboratory PLMN on n78, PCI 666, SSB ARFCN 643104 at approximately
−69 dBm. No additional SIM updates or functionality refreshes were performed,
and observation resumed. This proves target-cell visibility in this scan, not
camping, registration, AKA/SQN synchronization or a valid data PDU.

GitHub's default `main` ref was checked read-only and matched the local source
base recorded above. The standard setup/operations/access-policy documentation
and `Agent.create → launch → execute` path were reviewed before continuing via
the authenticated Console's Device Setup task. The standard flow preserves
observe-only radio selection and independently verifies registration, PDU and
interface-bound data connectivity.

The authenticated Device Setup task completed inspection, management protection,
baseline capture and radio preservation, then failed its 120-second Register
deadline. Data PDU configuration, data-path verification and route promotion
were not executed. Cleanup confirmed Wi-Fi egress and management protection
with zero route mutations. AMF metrics showed one connected gNB and zero initial
registration requests, authentication requests and RAN UEs at that observation.
This places the observed failure before AMF registration processing; it does not
prove that no PRACH or RRC attempts occurred.

The operator chose one field trial of explicit laboratory PLMN selection before
adding any selection feature to the product. A separate private helper was
prepared to check the commissioned SIM, current forbidden list, idle platform,
management protection and automatic operator mode, send the target selection
once, collect registration/cell evidence, then restore automatic selection.
No direct SIM update, band/RAT preference, CFUN or PDU command is included.
Uncertain command completion retains maintenance and sends no additional
commands. Twelve offline cases cover restoration, selection/query/restoration
timeouts, rejected selection, incorrect target evidence and command boundaries;
Python 3.10 syntax was checked. This is preparation, not a completed trial.

The vendor's [AT command manual](https://forums.quectel.com/uploads/short-url/x7O7XpZA1jJboG9xct7VxaeWLXx.pdf),
section 5.1, specifies access technology 12 for selecting NR SA, a 180-second
maximum response time and persistent NVM storage for COPS writes. The helper
therefore records intent before sending and explicitly restores automatic
selection instead of treating the command as an ephemeral query.

The operator reported that the first invocation stopped. No exported trial
report was present, while both platform services were active. Offline review
reproduced a helper preflight defect: the optional `simulation` field was
indexed as mandatory although production configuration omits it. A revised
private helper uses the same absent-is-false interpretation as `Agent`, retains
the original once-only ledger and passes 14 checks including the repository's
actual example configuration. Its uploaded hash and Jetson Python syntax were
verified. The terminal traceback is still required to identify the observed
failure; no subsequent operator-selection command has been sent. The operator
then supplied a traceback pointing to the original helper's mandatory
`config['simulation']` access, confirming it stopped before maintenance or any
operator-selection command. The revised helper may therefore continue the
still-unperformed single trial under the unchanged once-only guard.

The single field trial completed at approximately 16:00 local time. Its manual
selection command returned `+CME ERROR: 30`; the immediate sample showed the
target n78 cell in limited service without 5GS registration. The helper then
restored automatic selection successfully. The post-restoration sample reported
`C5GREG: 0,5`, operator mode 0 on the laboratory PLMN with access technology 11,
and NR SA on PCI 666 / SSB ARFCN 643104, approximately −70 dBm. Observation
resumed. Thus the manual command's failure and the later successful registration
are distinct outcomes; the trial's pre-restoration registration flag is not the
final modem state.

AMF metrics changed from zero to one initial registration request and one
success, with two authentication requests and one failure labelled cause 21;
no authentication rejection was reported. No direct SIM, band/RAT preference,
CFUN or PDU write was sent by this helper. The Console subsequently confirmed
fresh registration, matching lab policy and protected management, while the
data PDU remained inactive. A new standard Device Setup task was therefore
started to configure and independently verify the data path.

That standard task completed registration and configured/activated the data
DNN on CID 5 with an IPv4 address in the expected pool. It then failed the UPF
and test-network path checks; automatic default-route promotion was not reached
and cleanup kept protected Wi-Fi egress. Fresh Console evidence continued to
show registered 5GS, matched NR SA policy and an active data PDU.

Bound host probes reached the modem's RNDIS gateway, but the gateway itself
returned network unreachable for the UPF probe. Host routes for diagnostic
targets used that gateway on the RNDIS interface. UPF metrics showed one session
and an `oai` QoS flow while both N3 data packet counters remained zero; Spark's
IPv4 forwarding was enabled. This narrows the next investigation to the modem's
host-data forwarding/session association before assuming a core NAT failure.
It does not yet establish a specific QMAP rule defect.

A read-only QMAP session-association helper was prepared and uploaded. Its fixed
queries inspect context/activation/address evidence, default WWAN, MPDN rules,
connection status and automatic-call associations; no rule mutation, SIM update,
scan, CFUN or PDU activation is permitted. Five offline checks cover rejected
write/scan commands, terminal errors and timeout handling. The uploaded hash and
Jetson Python syntax were checked. Execution requires the operator's existing
sudo terminal; there is no new privileged remote access path.

That inspection completed with observation resumed. Registration and target-cell
evidence remained healthy; the selected `oai` profile 5 was active with a valid
pool address. All four MPDN rules and connection states were empty/disabled,
while default WWAN reported disconnected profile 1 with no IPv4 address. This
establishes the missing default QMAP data-call association, independently of
the active modem PDU context. `QNETDEVSTATUS: 0` is retained as raw evidence and
is not alone interpreted as disconnection, since its leading field controls
status reporting. Source review followed `Agent.ensure_data → Modem.write
(context/activate) → CGDCONT/CGACT`; no MPDN rule is created on that path.

The vendor manual's section 12.8 identifies rule 0 / VLAN 0 as the physical
default data call and describes the persistent rule command and disable action.
A private repair helper was prepared to bind only unused rule 0 to profile 5,
VLAN 0, with IP passthrough disabled and automatic data call enabled. It backs
up fresh state privately, requires the commissioned SIM and current target
registration, checks the exact firmware capability and unchanged empty rules,
and sends the configuration once. It retains the rule only after exact readback,
valid matching profile/WWAN addresses, preserved context definitions, healthy
required bound probes and management protection. Otherwise it disables only the
owned rule if command completion and current rule contents are known; ambiguous
completion retains maintenance without further commands or retries. No SIM,
frequency/RAT, CFUN, other context, VLAN or host-route command is included.
Fourteen offline checks cover successful binding, delayed connection, preexisting
or changed rules, rejected writes, command boundaries, timeout paths and rollback
failure. Python 3.10 syntax was checked. This records preparation, not successful
application or a connected data path.

The first repair invocation stopped during preflight with `write_attempted`
false and sampling resumed. The fresh default-rule row was profile 0 / VLAN 0 /
IPPT 0 / automatic-call flag 1, whereas the earlier read-only inspection had
reported flag 0. The underlying reason for that flag difference was not
established. Both snapshots still showed no configured profile, no MPDN
connection and no default WWAN address. The initial all-zero rule guard was
therefore too restrictive; no QMAP configuration command had been sent.

The revised private helper recognizes an unconfigured default profile with
either Boolean automatic-call flag and independently requires disconnected,
unaddressed QMAP state. Secondary rules must remain exactly empty. Its separate
once-only ledger is linked to the retained original ledger and continuation is
refused unless the prior invocation is confirmed stopped before any write and
sampling resumed. Rollback verifies an unconfigured rule and disconnected data
call rather than assuming that an unconfigured rule always reports flag zero.
Twenty-one offline tests include the exported real-device preflight fixture,
connected/addressed call rejection, continuation guards and post-write timeout
handling. The write surface remains the same target rule and its disable action.

The revised binding attempt acknowledged the rule write and read back exactly
rule 0 / profile 5 / VLAN 0 / no IP passthrough / automatic call enabled.
However, MPDN status remained disconnected and default WWAN had no IPv4 address
throughout the bounded observation. The helper timed out before host probes or
commit, disabled its owned rule once, verified the unconfigured/disconnected
state and resumed observation. The attempted rule was not left enabled.

SMF creation counters remained unchanged from the earlier successful CGACT
session, and UPF N3 data packet counters remained zero. This does not identify
the failure cause, but there is no new session-creation evidence at the core in
those counters. The automatic-call gate, data-interface mode, profile mapping
and possible contention with the existing AT-activated session remain separate
hypotheses. No rule reapplication, context deactivation or reboot followed.

A further read-only helper was prepared to inspect `QMAPWAC`, USB/PCIe data
interface selection, profile summaries and active MBN identity after confirming
the prior rollback. Optional profile fields are not exported; only profile ID,
PDU type and APN are retained. Seven offline checks cover write/scan rejection,
timeouts, unsupported commands and credential-field exclusion. The vendor's
[RM520N support response](https://forums.quectel.com/t/rm520n-registration-and-ecm-not-working/33820/4)
also requests the `QMAPWAC?` query. This supplies a documented diagnostic query,
not evidence that this device's gate is disabled or permission to change it.

The completed dial-policy inspection now confirms `QMAPWAC: 0`, USB data
interface `0,0`, PCIe mode 0, RNDIS mode 3 and physical VLAN 0. Registration and
the AT-activated profile 5 PDU remain healthy, while default QMAP WWAN remains
disconnected after the verified rollback. The current firmware rejects the
optional QWDS profile-summary query; a second profile mapping was not established
through that command. The active MBN is the carrier-specific CT profile; no MBN
change was made. Observation resumed without configuration changes or reboot.

The operator recalled a previous success after reducing Jetson USB3 to USB2 but
could not recall how it was done. Current sysfs/USB topology shows 5000 Mbps;
RNDIS link counters show no RX/TX errors or drops in the read snapshot. This
neither confirms nor excludes a USB-speed problem. The initial modem inventory
also recorded speed setting `312`; it is separate from the negotiated rate.
The vendor manual documents that the `20` speed setting requires a modem reboot
and persists. No speed change was sent. A future speed comparison must record
the actual negotiated rate and avoid conflating it with dial-policy changes.

A separate commissioning helper was prepared to keep the current USB3 baseline,
set only the existing data-profile rule and the global automatic-dial gate, then
send at most one modem reboot. The vendor's
[RM520N restart guidance](https://forums.quectel.com/t/quectel-rm520n-gl-and-automatic-connection-to-the-network-at-cfun-1/55623)
states that enabling QMAPWAC requires restart. The helper privately records the
baseline and durable command intents, requires changed USB enumeration before
reopening the modem, checks the commissioned SIM and retained configuration,
and observes registration/data-call evidence before bound probes. Existing user
profile definitions in the supported CID range must remain unchanged; firmware
reserved context inventory is retained as evidence. The intended dial settings
persist even if subsequent data verification fails; the helper does not repeat
configuration/reboot or automatically undo uncertain settings. Incomplete
postboot verification retains maintenance. Ten offline tests cover exact write
boundaries, refusal of occupied rules, failed commands and the one-reboot guard,
including loss of USB during transmission. This new write/reboot scope has been
prepared for operator review; it has not been executed.

The operator explicitly approved and started that configuration/reboot scope.
Both intended configuration writes were acknowledged and read back before the
single reboot. USB re-enumeration was confirmed, still at 5000 Mbps; the modem
presented a different host Ethernet identity and DHCP completed on the newly
discovered interface. AMF initial registration successes increased to two.
The commissioning helper then stopped when the bootstrap `AT` inside the
postboot serial open timed out; it retained maintenance as designed. This does
not yet establish the cause of the AT timeout or verify postboot QMAP values.
No second configuration write sequence or reboot was sent.

Read-only topology inspection found the same RNDIS/serial interface layout and
ModemManager remained inactive. A separate completion inspector was prepared
with a 12-second read-only bootstrap timeout. It requires the retained ledger to
confirm that the reboot already occurred and the postboot check is outstanding;
it cannot configure or reboot the modem. It checks the commissioned SIM, saved
gate/rule, USB settings and user profile definitions before resuming observation
and the platform's existing diagnostic-route preparation for the newly
discovered interface. Seven offline checks cover the continuation guard,
extended AT timeout and rejection of all modem mutations. This continuation
remains pending; no working data path has been claimed.

## Final online acceptance

The read-only completion inspector subsequently passed all postboot checks and
resumed observation. The commissioned SIM remained ready and registered on the
target NR SA cell. QMAPWAC was enabled, rule 0 retained profile 5 / VLAN 0 /
no IP passthrough / automatic call, MPDN status was connected and the default
IPv4 WWAN address matched profile 5 in the expected pool. USB mode and stored
speed setting were preserved, actual negotiation remained 5000 Mbps, and the
supported user profile definitions were unchanged. No further modem write or
reboot was performed by the inspector.

Independent host probes bound to the newly discovered RNDIS interface reached
the UPF, ext-DN and public probe addresses, each with three of three ICMP replies.
HTTP to ext-DN's internal health endpoint, bound to the RNDIS source address,
returned the expected fixed response. These checks exclude management Wi-Fi as
the source of the asserted cellular data success. The Console showed registered
5GS, an active IPv4 `oai` session on CID 5, matching lab policy, verified
management fallback and all data-path checks healthy. Its route policy promoted
IPv4 egress to cellular after fresh successful samples.

A new standard Device Setup task then completed all eight steps, including data
verification and automatic-routing enablement, at approximately 16:48 local time.
Its successful completion also releases the platform's recovery pause under
the existing task contract. The subsequent overview remained connected with
protected management and cellular egress. The old failed tasks and one-shot
operation ledgers were retained. Screenshots and raw probe results remain in
private storage outside Git.

The modem reboot selected a new host Ethernet identity. NetworkManager used an
automatically generated wired connection with a DHCP default metric above the
application's owned metrics; the original management Wi-Fi route remained.
The application's existing guard accepts such administrator/NetworkManager
defaults and uses its owned preferred/fallback routes. No unrelated connection
was modified for this acceptance.

UPF's two exported N3 packet counters still read zero after the successful bound
ICMP and HTTP checks. Those counter values are therefore insufficient negative
evidence for absence of user traffic in this deployment; the earlier diagnostic
inference must be read with this limitation. The counters' instrumentation was
not repaired during access setup. This acceptance covers registration and basic
IPv4 connectivity, not a throughput benchmark, sustained soak test, injected
radio/core failure recovery or whole-host reboot. The successful path used
USB3; a USB2 comparison was not required or performed.

Subsequent throughput measurements and the interrupted management-continuity
test are recorded separately in the
[cellular performance record](2026-10-16-jetson-cellular-performance.md).

## Second UE deployment and selection investigation

A second Jetson with the same modem model and firmware received the verified
release listed above and a separately provisioned experimental SIM. The private
bootstrap retained user profiles 1–4, added the data DNN on profile 5, associated
QMAP rule 0 with that profile, enabled automatic dialing, and switched to RNDIS
with one modem reboot. USB negotiation remained 5000 Mbps. Both platform
services are active; SIM identity/readiness and host RNDIS DHCP passed. These
checks do not constitute successful radio/data acceptance.

The investigation asks why automatic selection leaves the laboratory cell after
successful temporary data connectivity. With no CodeGraph index present, the
existing `hardware.discover → Modem.open`, registration/serving-cell parsers,
and platform status/probe/routing evidence were reused. This work uses private
site helpers and does not add a product selection API or change the first UE.

One explicit-selection trial confirmed the target n78 / PCI 666 cell, two fresh
sets of interface-bound gateway/UPF/ext-DN/public probes, and cellular default
routing. It then stopped at an overly strict whole-response configuration
comparison and restored automatic selection. The failed post-comparison values
were not exported, so the exact cause of that comparison failure remains
unresolved. A revised semantic comparison passed preflight, but its subsequent
selection command was rejected; that revision did not retain the rejection code.
It also confirmed automatic-selection restoration.

A subsequent read-only inspection confirmed the second SIM's target home PLMN,
two-digit MNC, and absence of the target from its forbidden list. Parsed radio,
USB and QMAP configuration values matched the preserved baseline. Equivalent-home
and user-priority decoding remained incomplete; no further SIM correction was
performed.

The operator then authorized a bounded NR5G-only / SA-n78-only policy trial.
Both settings were acknowledged and read back. Automatic registration did not
produce the required complete target-cell evidence within the observation
window. The single fallback selection without an access-technology argument
returned `+CME ERROR: 30` (no network service in the vendor manual). The helper
confirmed restoration of AUTO mode, the complete original SA band list and
automatic operator selection; parsed rollback configuration differences were
empty. Observation resumed, Wi-Fi management remained connected, and ordinary
egress used Wi-Fi. Second-UE network acceptance remains **incomplete**.

The private NR policy helper passed 20 offline tests. It performed no SIM,
USB, data-profile or core writes and no modem reboot. A separate read-only
first-UE check still passed two of two bound UPF probes with cellular default
routing. Core aggregate registration successes increased during the NR trial,
but aggregate counters cannot associate a success with the second UE's final
state. The ten-test read-only core log classifier then completed. Direct identity
matches associate four registration-complete records with the second UE in its
45-minute window; the most recent was at 20:49:35 local time. Nearby release
records lacked same-line identity, and the exported categories did not retain
release reasons, so they cannot establish why stable attachment failed.

The first UE's successful saved readbacks and the second UE baseline match for
RNDIS mode, stored USB speed, QMAP rule inventory and the automatic-dial gate.
Both use the same verified release, CID 5 and IPv4 data DNN. The first UE's saved
radio-policy inspection also reports AUTO, the same complete SA band list and
SA enabled. This comparison uses saved evidence rather than a disruptive fresh
serial inspection of the working first UE.

At the operator's request to reuse the first UE's procedure, the second UE ran
one standard Console Device Setup task through `Agent.create → launch → execute`.
The task completed inspection, management protection, baseline saving and radio
preservation, then failed Register's deadline at 21:03:34 local time. The later
PDU, data-verification and route-promotion steps were not executed. Cleanup
confirmed Wi-Fi egress and protected management with zero route mutations; two
independent Wi-Fi gateway probes also passed during the task. No permanent
radio-policy change or further explicit selection was performed by this task.
The supplemental read-only release-detail classifier passed 17 tests and
completed on hardware. Its gNB log window reported four RLF detections with
`MAC max KOs reached`, each followed by an approximately four-second release
timer and NGAP context release. The corresponding registration-to-RLF intervals
were approximately 4.2, 33.7, 5.8 and 4.2 seconds. The time correspondence is
strong evidence of radio-link failure around the second UE's registrations;
radio identifiers alone are not subscriber identities.

Inspection of the deployed OCUDU commit's
`lib/mac/mac_sched/rlf_detector.h → mac_ue_radio_link_notifier → DU UE controller`
shows that consecutive HARQ-ACK failures, CRC failures or undecoded CSI can all
produce the same DU warning. Their detailed MAC cause is logged at info level,
which the current all-warning / NGAP-info configuration does not retain. The
export counted 2,489 underflow and 18 late matches in the specified timestamp
window; these are event counts, not proof of causation or rates. No RLF threshold
or radio configuration was changed. The ten-test read-only monitor-history extractor subsequently completed using
SQLite `mode=ro` and `query_only=ON`. It exported 600 samples for the continuing
radio context and 12 samples across the four short-lived contexts, with no
subscriber identity or session/authentication-table export. Several active
short-lived-context windows reported CQI 15, gNB uplink SINR around 26–28 dB,
and zero downlink and uplink transport-block errors. Other windows had initial
uplink errors. Measurements later became absent; one later window had five
uplink errors, 100% observed uplink BLER and approximately −25 dB SINR. Sampling
intervals and missing transport blocks prevent determination of the exact
consecutive-failure trigger. Inactive-window placeholder RSRP values were not
interpreted as measured RF attenuation.

Read-only host comparison found identical USB 5000 Mbps negotiation, runtime
power control `on`, active runtime state and zero accumulated USB suspended time
on both modems. No USB power/speed setting was changed.

A bounded private MAC-info capture helper was prepared and uploaded. Fifteen
offline cases cover restoration, foreign overrides, pending control jobs,
configuration preservation and actual detached-watchdog recovery after parent
pipe EOF. The same built OCUDU binary passed dry-run parsing of the logging
options with a synthetic configuration; no RF device was opened. The proposed
trial changes only MAC verbosity with hex dumping disabled, observes four
minutes, then restores the original command/configuration. It requires two gNB
restarts and therefore explicit operator approval for interruption of the first
UE's cellular link. The operator approved and executed the bounded capture. The four-minute
window started at 21:24:26 local time; the original service command, configuration
and drop-ins were restored by 21:28:32, with both restoration checks true. Within
the window, one explicitly authorized standard Recover task on the second UE
failed its Reconnect once deadline. Core aggregate registration counts did not
increase in the observed window. No detailed MAC RLF cause was exported, so this
trial did not reproduce a target registration and subsequent failure from which
to determine the trigger. It does not identify or eliminate ACK, CRC or CSI as
the earlier trigger.

The chat was interrupted during the capture. On resumption, independent SSH
checks confirmed the original gNB running, the temporary logging override absent,
both Jetson platforms active, both management Wi-Fi links connected, and the
first UE back on cellular default routing with two of two bound UPF replies.
The first UE's exact reacquisition time was not measured in this trial. The
second UE continued using Wi-Fi with network acceptance incomplete.

A separate read-only modem-policy inspector was prepared and verified on both
Jetsons, with ten tests covering query boundaries, unsupported responses,
bootstrap/query timeouts and blocked mutations. It will compare previously
uncollected MBN and modem sleep settings rather than assume that identical
hardware and software versions imply identical saved policies. It does not
select or deactivate an MBN, set a sleep mode, select a network, reboot, or write
a SIM. Administrator execution completed on both hosts, and both platforms
resumed collection. The complete MBN inventory, selected/active operator profile,
automatic MBN selection, AUTO network mode, SA band list and SA-enable policy
matched. Both returned `QSCLK: 0,0`; PSM and eDRX queries returned unsupported
errors, so their enabled/disabled state was not inferred. The first UE was
registered on the lab cell while the second remained searching with commercial
limited service. There is no observed MBN or sleep-policy difference to copy.

A private second-UE USB2 comparison helper passed 24 offline tests, including
simulated complete execution, known-failure restoration, unknown-command stop,
cross-bus USB enumeration, stale/wrong-interface data rejection and a full
120-second acceptance interval. The call path is fixed-command gate → durable
intent → USB speed setting → one modem restart → topology/identity discovery →
preservation checks → target registration → existing platform preparation and
bound probes. The existing platform owns ordinary route promotion and fallback;
the helper does not edit host default routes, the radio stack or the first UE.

The manufacturer's [RM520N-series AT manual, section 3.3.8](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/6382/Quectel_RG520NRG525FRG5x0FRM5x0NRM521F_Series_AT_Commands_Manual_V1.0.pdf)
defines saved USB2 mode `20`, effective after a modem restart. The proposed trial
requires actual 480 Mbps negotiation and the same physical modem and SIM;
stored mode alone cannot pass. It observes automatic registration first, then
permits at most one explicit lab selection. Success retains USB2. Known failure
restores the original USB mode and automatic selection if needed, using at most
one additional modem restart; uncertain completion blocks further sends and
retains maintenance. Reboot and possible selection are additional interventions,
so success would support a practical configuration, not isolate USB speed as the
sole cause. The operator approved and executed this trial. Actual USB negotiation
changed to 480 Mbps with cross-bus enumeration and the same modem/SIM identity.
Postboot preservation initially passed. The bounded manual lab-selection command
returned terminal `CME ERROR: 30`, but subsequent read-only evidence nevertheless
showed registration on the intended NR SA cell, CID 5 active and QMAP connected
with a core-assigned IPv4 address. This illustrates why command acceptance and
observed registration are recorded separately.

The final preservation gate detected a difference only in `mode_pref` and stopped
before platform-bound data acceptance. That version retained the differing query
name but omitted its actual final response, so the specific intermediate mode
cannot be reconstructed. The difference followed explicit selection, but its
cause is not established. Automatic selection and the original USB setting were
restored, actual negotiation returned to 5000 Mbps, and strict configuration
differences after rollback were empty. Both modem restarts completed, collection
resumed and maintenance was cleared. Independent Wi-Fi management checks remained
successful. This is not a successful sustained-data test or evidence that USB2
alone resolves the earlier RLF.

A separately journaled second trial was prepared. Its 29
offline tests cover complete simulated success/rollback, the existing USB2 safety
boundaries and the revised preservation gate. Full postboot, final and rollback
readbacks are retained. Only during confirmed manual lab selection may the gate
accept AUTO, NR5G or LTE:NR5G as the observed network-mode value; LTE-only or other
mode changes still stop the trial, as does every other protected configuration
difference. There is no direct network-mode write command. The original trial
must show known command completion and full rollback before the new ledger can
be created. This changes the retention criteria and requires fresh operator
approval; it does not resume or erase the first trial. The operator approved and
executed it. The intermediate mode was recorded as NR5G after explicit lab
selection, and all other protected configuration values matched. Actual USB
negotiation remained 480 Mbps. The trial completed at 22:20:12 local time with
122 seconds of continuous healthy cellular default routing and 12 distinct fresh
probe sets, each bound to the current RNDIS interface and source address. The
gateway, UPF, external data network and configured public probes all passed.
USB2 and the verified manual lab selection were retained; collection resumed.

The standard console Device Setup then ran through
`Agent.create → launch → execute` and completed all eight steps at 22:22:04.
Its report confirmed preserved radio policy, zero radio mutations, valid lab
registration/session and bound data verification. The platform Settings page
subsequently showed maintenance off, commissioning complete and automatic
recovery active. A later independent host check still found actual USB2 and the
ordinary public route using the cellular interface. Bound UPF and public ICMP
checks each received two of two replies, with mean RTTs approximately 25.5 ms and
46.9 ms; a separately Wi-Fi-bound management gateway check received two of two
replies at approximately 3.5 ms. No traffic-rate claim is made from these probes.

The independent Wi-Fi SSH observer had 289 successful samples for Wi-Fi state,
gateway reachability and its protected return path by the trial completion
check. Spark gNB and monitoring services remained active. Independent checks on
the first UE retained its cellular ordinary route and received two of two bound
UPF and configured public replies. A separate ad hoc public destination did not
reply; public reachability claims are limited to the successful tested target.
The first UE and Spark were not reconfigured or restarted by these USB trials.

Both second-UE platform services were active but still disabled for automatic
start at host boot. No service enablement or whole-host reboot was performed.
The temporary Wi-Fi observer was stopped after acceptance; platform collection
and recovery continue running.

The working second-UE configuration therefore combines USB2 with manual lab
selection and observed NR5G preference. Reboot and selection were additional
interventions, so these results do not isolate USB speed as the sole cause of
the earlier failures. Whole-host reboot, the second UE's failover/reacquisition
timing and longer-duration load/performance acceptance remain untested.

## Rolling host-boot commissioning preparation

The operator subsequently requested automatic platform/cellular startup and real
host reboots, strictly one UE at a time while preserving Wi-Fi management.
Read-only comparison confirmed both platform units disabled at boot, both
ModemManager units enabled but inactive, and dedicated RNDIS profiles still bound
to obsolete interface names. The current dynamically named RNDIS interfaces were
using automatically generated NetworkManager connections instead.

The code question was why enabling units alone would not restore automatic
operation. With no CodeGraph index present, source inspection traced
`Agent.serve finally → recovery_paused=True → auto_reconcile early return`, plus
the site guard's dependency on already enumerated USB interfaces. The optional
`deploy/jetson/boot_connect.py` call path is pinned runtime verification → boot
readiness → SIM/configuration check → natural registration or one bounded lab
selection → standard Device Setup → 120-second bound-data acceptance. It does not
change USB speed, SIM files, bands or QMAP, and it does not reboot a host.

The private administrator installer separately backs up and fixes the dedicated
RNDIS profile's stale name binding, keeps raw DHCP defaults suppressed, excludes
ModemManager from this dedicated modem's ownership, enables platform/boot units
and schedules exactly one host reboot only after fresh preboot data and management
checks. Before a reboot request, known setup failure restores its owned changes;
an uncertain reboot request is never repeated. Boot/reboot journals and status
exports contain no SIM authentication material.

Nineteen repository boot tests and six private installer simulations passed.
The first host also passed Python 3.10 parsing, uploaded hash checks, systemd
unit verification and an independent Wi-Fi SSH/gateway check. The second host
still had cellular ordinary routing and bound UPF replies. Only the first host's
installer was initially uploaded; the second installer was withheld until the
first host passed actual reboot acceptance.

The first host completed its real reboot acceptance at 23:24:00 local time.
Its kernel boot identity changed, and both platform units and the boot coordinator
were enabled and successful. Natural lab registration succeeded without a manual
selection command. USB3 remained at 5000 Mbps, protected modem configuration had
no differences, and standard Device Setup completed automatically. The coordinator
then observed 122.7 continuous healthy seconds with 13 fresh bound probe sets,
cellular default routing and automatic recovery active. Independent postboot
checks received two of two UPF, public and Wi-Fi management gateway replies;
the console returned HTTP 200. The dedicated RNDIS profile was selected with no
interface-name binding and raw DHCP defaults still suppressed. The second host's
boot identity remained unchanged and its bound UPF check passed. The second host
had not yet been rebooted at this first-host acceptance checkpoint.

After that checkpoint, the second installer was uploaded and passed hash,
Python 3.10 and systemd unit checks. Its preboot cellular and Wi-Fi checks passed,
then the operator executed the administrator installer. The second host alone
rebooted and completed acceptance at 23:32:48 local time. Its new kernel boot
identity matched the current boot journal; both platform services and the boot
coordinator were enabled and successful. Lab registration was already present
after boot, so the coordinator did not issue a manual selection command. Actual
USB2 remained 480 Mbps, observed mode remained NR5G, and protected modem
configuration had no differences. Standard Device Setup completed automatically,
followed by 122.7 continuous healthy seconds and 13 distinct fresh bound probe
sets with cellular default routing, management verification and automatic
recovery active. The retained selection and radio policy were not rewritten.

Final independent checks on both hosts confirmed their dedicated RNDIS profiles
selected, stale interface-name bindings cleared, raw DHCP defaults suppressed,
ordinary public traffic routed through cellular, and two of two replies for
cellular-bound UPF/public probes and Wi-Fi-bound management gateway probes.
The first host's boot identity remained unchanged during the second host's
reboot. Both local console tunnels were restored over the independent Wi-Fi
management path and returned HTTP 200. No simultaneous host reboot occurred.
SIM and USB configuration writes were zero in both boot installers. This
acceptance covers real host reboot and the bounded postboot checks; it does not
add longer-duration load or second-host failover timing results.

## First UE USB2 migration — 2026-10-17

The operator subsequently requested USB2 for the first UE as well. Read-only
inspection confirmed its existing USB3 and cellular baseline. Its commissioned
boot coordinator pinned both actual USB speed and saved modem configuration;
changing the modem alone would fail the next boot's preservation check. A private,
site-specific one-shot migration therefore backed up the boot configuration and
updated only the saved USB speed and matching boot expectations before restarting
the modem. Device configuration, RNDIS connection and all other pinned modem
settings were protected. No repository runtime source was changed for this step.

Eighteen offline checks covered success, identity and Wi-Fi guards, unknown or
partial commands, different or absent enumeration, preservation failures, data
failure rollback, unknown setup tasks and fixed mutation boundaries. Uploaded
hashes, the installed helper hash and Python 3.10 parsing matched before the
operator executed the administrator script over the independent Wi-Fi SSH path.

The migration completed at 00:01:14 local time on October 17. The same modem
reenumerated at actual 480 Mbps following one modem restart, naturally registered
on the lab network, and completed standard Device Setup. Thirteen fresh bound
probe sets and 123.1 continuous healthy seconds passed with cellular default
routing and automatic recovery active. USB2 and the corresponding boot baseline
were retained; maintenance was off and no platform task remained active. There
were no selection, SIM, band, QMAP or core changes, and no rollback was needed.

Independent final checks on both UEs confirmed actual USB2, cellular ordinary
routing, successful UPF/public and Wi-Fi gateway probes, and HTTP 200 consoles.
Both host boot identities remained unchanged; Spark services remained active.
The temporary Wi-Fi observer was stopped after acceptance. This step restarted
only the first modem, so a new whole-host reboot with its USB2 baseline has not
been tested. The earlier first-UE throughput results were measured with USB3;
no USB2 throughput or simultaneous two-UE load result is inferred here.
