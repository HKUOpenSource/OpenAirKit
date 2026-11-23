# Jetson Console setup

## Prerequisites

Use Linux ARM64, Python 3.10, systemd, NetworkManager and the supported RM520N
modem. Wi-Fi must have a unique address and one fallback IPv4 gateway;
Tailscale must route the configured Spark management address. The modem must
have its own RNDIS DHCP address. OCUDU validates these prerequisites and never
replaces an administrator-owned default route or stops an external service.
Port `127.0.0.1:8878` and the discovered AT port must be free.

An RNDIS DHCP lease and an active `CGACT` context do not by themselves prove
host-data forwarding. On the verified RM520N QMAP firmware, inspect the default
WWAN and MPDN rule/status association with the selected data profile. The current
Console configures the data context but does not create QMAP rules or enable
the global automatic-dial gate. Inspect `AT+QMAPWAC?` separately from each rule's
automatic-call flag. Audit any
missing association separately against the vendor manual; retain existing
profiles and other rules. See the validation record below for the observed
registered-but-no-data failure and the bounded site repair procedure.

Match `device.at_interface_number` to the actual USB layout before commissioning.
The example uses `04`: RNDIS occupies interfaces `00/01`, followed by serial
functions DIAG, GNSS, AT and modem at `02..05`. A layout with serial functions at
`00..03` and data at `04` uses AT interface `02`. Discovery checks this topology
and rejects a mismatched or unknown layout before opening a serial port; Linux
`ttyUSB` numbering alone does not identify the AT function.
See the [RNDIS discovery validation record](acceptance/2026-10-16-jetson-rndis-at.md)
for the observed layout and remaining hardware checks.

Configure the site's NetworkManager profiles once, if necessary. Review active
profiles with `nmcli -f NAME,UUID,TYPE,DEVICE connection show --active`. Keep the
management Wi-Fi default available. Existing defaults must have metrics above 10;
metrics 5 and 10 and protocol 186 are reserved for application-owned defaults.
The modem profile may have `ipv4.never-default` enabled or disabled. Applying a connection profile can interrupt that
link; perform initial network setup through a local management terminal. These
settings are site prerequisites, not actions borrowed from another project.

The release contains a verified manifest, ARM64 CPython 3.10 offline wheels,
frontend, installer, lifecycle scripts and license material. Production config
belongs outside the unpacked release. From release 0.6.0, lifecycle scripts
are included in the verified package.

## Install and commission

From the unpacked Jetson release, verify and install:

```sh
python3 -I -B deploy/manage.py verify
python3 -I -B deploy/manage.py preflight
sudo bash deploy/install-jetson.sh
```

The installer prompts for a new private Console password on a fresh installation.
It installs under `/opt/agentic-ocudu/jetson`, starts only the loopback Web service,
and leaves both systemd units disabled at boot. The install shell wrapper already
selects `install`; do not append another `install` or `preflight` argument.

Commissioning binds this installation to its own SIM and management interfaces.
First stop OCUDU, then replace the documentation-only address below with Spark's
actual management address:

```sh
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py stop
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py commission \
  --spark-address 192.0.2.20 --wifi-interface auto
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py start
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py status
```

`commission` selects the installed application Python environment automatically;
no modem dependencies need to be installed into system Python. It refuses a busy
AT port, preserves an existing different SIM binding, and does not start services
or issue modem configuration writes. It replaces the old takeover command.
A failed commissioning attempt leaves the installed application available for
inspection; correct the reported prerequisite and rerun commissioning, not installation.

`start` prepares the configured data-probe routes and a Wi-Fi fallback default,
starts the two services, and resumes observation with automatic modem recovery paused.
Two fresh successful cellular samples, including Internet, select cellular as the
IPv4 default. Two failed samples select Wi-Fi; stale evidence or loss of registration,
PDU or data interface selects Wi-Fi immediately at the next reconciliation.
This routing policy operates independently of the automatic modem recovery switch.
The kernel need not support policy routing. Tailscale may reconnect during a switch;
the Wi-Fi fallback is not an independent, guaranteed management channel. SIM registration and
PDU/data-path readiness are reported separately; no forced reconnect is part of start.

## Operator access and verification

Administrators can use the installed manager directly. For passwordless operator
shortcuts, build and approve the matching release with the repository's
[restricted maintenance bundle](../deploy/maintenance/README.md), then copy the
three packaged scripts as described in [Jetson operations](jetson-operations.md).
The maintenance helper upgrades existing installations; it is not the fresh
installation/password setup path. Keep approval and application releases matched.

Open the UI through an SSH tunnel to `127.0.0.1:8878`. Check services, active fresh
observation, SIM, registration, PDU and modem-bound data probes separately.
Test a full OCUDU stop/start, including route cleanup, before enabling routine use.
Both services remain disabled at boot until an administrator explicitly changes that.

## Opt-in boot coordination

Enabling the two platform units alone does not complete boot commissioning:
executor shutdown deliberately pauses modem recovery, and USB enumeration/DHCP
may not be ready when systemd first starts the executor. The optional
[`boot_connect.py`](../deploy/jetson/boot_connect.py) coordinator supports a
reviewed, site-specific administrator installation alongside a pinned release.
It is not enabled by the default installer.

The device unit must wait for supported USB topology, RNDIS DHCP and management
Wi-Fi/Tailscale readiness before its existing guards run. Bind the dedicated
NetworkManager profile to the RNDIS driver with no stale interface-name or MAC
binding, autoconnect enabled and `ipv4.never-default=yes`. The platform still
owns verified cellular promotion and Wi-Fi fallback. Prevent ModemManager from
owning this dedicated lab modem; preserve NetworkManager and Wi-Fi profiles.

The root-owned `/etc/aoc-v2-jetson/boot.json` records the approved release/device
hashes, SIM commitment, USB speed and protected modem settings. It contains no
SIM authentication keys. The boot coordinator validates identity and settings,
waits for natural lab registration, permits at most one explicit lab selection
if needed, then runs one standard Device Setup and requires 120 seconds of fresh
interface/source-bound cellular data with automatic recovery active. It never
reboots the host or changes USB speed, SIM files, bands or QMAP. Unknown command
completion blocks further commands. Each boot has a durable private journal;
redacted status is readable at `/var/lib/aoc-v2-jetson-boot/public/status.json`.

Verify units and boot IDs, actual USB speed, lab registration/session, cellular
ordinary routing and independent Wi-Fi access after a real reboot. With two
UEs, configure and reboot only one, complete acceptance, then proceed to the
other. Do not equate a successful service enablement with tested boot recovery.
