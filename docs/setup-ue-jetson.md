# Jetson Console setup

[简体中文](setup-ue-jetson.zh-CN.md)

> [!TIP]
> For hardware BOM (including mounting the **Quectel RM520N-GL** on the
> **[Waveshare SIM8262E-M2 5G for Jetson Orin](https://www.waveshare.net/shop/SIM8262E-M2-5G-for-Jetson-Orin.htm)**
> carrier board) and the 0-to-1 bring-up sequence, start with
> [Hardware & Topology](hardware-and-topology.md) and the
> [End-to-End Quickstart](quickstart.md).

## Prerequisites

Use Linux ARM64, Ubuntu 22.04, Python 3.10, systemd, NetworkManager and the
supported **Quectel RM520N-GL** modem (mounted on the Waveshare Jetson Orin
M.2 5G carrier board over USB 3.0). Wi-Fi must have a unique address and one
fallback IPv4 gateway; Tailscale must route the configured Spark management
address. The modem must obtain its own RNDIS or ECM (`cdc_ether`) DHCP address.
OCUDU validates these prerequisites and never replaces an administrator-owned
default route or stops an external service. Port `127.0.0.1:8878` and the
discovered AT port must be free (stop and disable any conflicting local console
or ModemManager service owning port `8878` or the AT serial port beforehand).

A modem DHCP lease and an active `CGACT` context do not by themselves prove
host-data forwarding. On verified RM520N QMAP firmware, inspect the default
WWAN and MPDN rule/status association with the selected data profile. The current
Console configures the data context but does not create QMAP rules or enable
the global automatic-dial gate. Inspect `AT+QMAPWAC?` separately from each rule's
automatic-call flag. Audit any missing association separately against the vendor
manual; retain existing profiles and other rules. See
[acceptance/2026-10-16-jetson-rndis-at.md](acceptance/2026-10-16-jetson-rndis-at.md)
for the observed registered-but-no-data failure and bounded site repair.

Match `device.at_interface_number` in `/etc/aoc-v2-jetson/device.json` to the
actual USB layout before commissioning or upgrading. `aoc_jetson.hardware.discover()`
validates these three RM520N layouts before opening any serial port (Linux
`ttyUSB` numbering alone does not identify the AT function):

| USB Data Function | Data `bInterfaceNumber` | Serial `bInterfaceNumber` (`DIAG/GNSS/AT/Modem`) | Required `at_interface_number` |
| --- | --- | --- | --- |
| `rndis_host` (RNDIS) | `00/01` | `02`, `03`, `04`, `05` | `"04"` |
| `cdc_ether` (ECM) | `04` | `00`, `01`, `02`, `03` | `"02"` |
| `cdc_ether` (ECM) | `0a` | `00`, `01`, `02`, `03` | `"02"` |

Configure the site's NetworkManager profiles once, if necessary. Review active
profiles with `nmcli -f NAME,UUID,TYPE,DEVICE connection show --active`. Keep the
management Wi-Fi default available. Existing defaults must have metrics above 10;
metrics 5 and 10 and protocol 186 are reserved for application-owned defaults.
The modem profile may have `ipv4.never-default` enabled or disabled. Applying a
connection profile can interrupt that link; perform initial network setup through
a local management terminal.

The 0.6.2 release contains a verified manifest, ARM64 CPython 3.10 offline
wheels, frontend, installer (`deploy/manage.py`), lifecycle scripts and license
material. Production config belongs outside the unpacked release. From 0.6.2,
`manage.py` temporarily applies `os.umask(0o022)` while building `venv/` and
explicitly sets `os.chmod(..., mode)` in `private_write()`, keeping `venv/` and
`web.json` (`0640 root:aoc-v2-jetson-web`) readable by the unprivileged web user
even when invoked under `umask 077`.

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
or issue modem configuration writes. A failed commissioning attempt leaves the
installed application available for inspection; correct the reported prerequisite
and rerun commissioning, not installation.

`start` prepares the configured data-probe routes and a Wi-Fi fallback default,
starts the two services, and resumes observation with automatic modem recovery paused.
Two fresh successful cellular samples, including Internet, select cellular as the
IPv4 default. Two failed samples select Wi-Fi; stale evidence or loss of registration,
PDU or data interface selects Wi-Fi immediately at the next reconciliation.
This routing policy operates independently of the automatic modem recovery switch.

## Operator access and verification

Administrators can use the installed manager directly. For passwordless operator
shortcuts, build and approve the matching release with the repository's
[restricted maintenance bundle](../deploy/maintenance/README.md), then install the
three lifecycle scripts as described in [Jetson operations](jetson-operations.md).
The maintenance helper upgrades existing installations; it is not the fresh
installation/password setup path. Keep approval and application releases matched.

Open the UI through an SSH tunnel to `127.0.0.1:8878`. Check services, active fresh
observation, SIM, registration, PDU and modem-bound data probes separately.
Test a full OCUDU stop/start, including route cleanup, before enabling routine use.
Both services remain disabled at boot until an administrator explicitly enables
the site-specific configuration below.

## Opt-in boot coordination

Enabling the two platform units alone does not complete boot commissioning:
executor shutdown deliberately pauses modem recovery, and USB enumeration/DHCP
may not be ready when systemd first starts the executor. The optional
[`boot_connect.py`](../deploy/jetson/boot_connect.py) coordinator supports a
reviewed, site-specific administrator installation outside the immutable release
(`/opt/agentic-ocudu/jetson/boot_connect.py`); the default installer does not
enable it.

To enable opt-in boot coordination on a commissioned host:

1. **Prevent ModemManager ownership** and keep NetworkManager configured for
   management Wi-Fi and modem DHCP (`ipv4.never-default=yes` on the modem profile;
   foreign default metrics strictly above 10).
2. **Test modem read-only compatibility while `aoc-v2-jetson-device.service` is stopped**
   (so the AT port is free): confirm `boot_connect.Serial` + `configuration()`
   (`AT+CGDCONT?`, `AT+QMAPWAC?`, `AT+QMAP="MPDN_rule"`, `AT+QCFG="usbnet"`,
   `AT+QCFG="usbspeed"`, `AT+QNWPREFCFG="nr5g_band"`,
   `AT+QNWPREFCFG="nr5g_disable_mode"`, `AT+QNWPREFCFG="mode_pref"`) and
   `usb_speed()` succeed cleanly on the target RNDIS or ECM firmware.
3. **Write `/etc/aoc-v2-jetson/boot.json` (`0600`, root-owned) after installing the pinned release**,
   because `manage.py install` updates `device.json["release"]` and `revision`.
   `boot.json` records `schema`, post-install `device_sha256`, `manifest_sha256`,
   `sim_sha256`, `usb_speed_mbps`, and `modem_configuration` (zero SIM keys).
   Create state directories `/var/lib/aoc-v2-jetson-boot/private` (`0700`) and
   `/var/lib/aoc-v2-jetson-boot/public` (`0755`).
4. **Install the systemd drop-in and oneshot boot unit**:
   - `/etc/systemd/system/aoc-v2-jetson-device.service.d/boot-ready.conf`
     sets `TimeoutStartSec=360`, resets `ExecStartPre=`, and chains
     `boot_connect.py ready` → `site_guard.py` →
     `network_entry.py --config /etc/aoc-v2-jetson/device.json --action fallback`
     so USB topology, modem DHCP, Wi-Fi and Tailscale are ready before
     `device_entry.py` starts.
   - `/etc/systemd/system/aoc-v2-jetson-boot.service` (`Type=oneshot`,
     `After=aoc-v2-jetson-device.service aoc-v2-jetson-web.service`) waits up to
     30 s for `/run/aoc-v2-jetson/device.sock` and runs
     `/usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/boot_connect.py connect`
     (`TimeoutStartSec=1200`), permitting at most one explicit PLMN selection if
     needed, running one standard Device Setup, and requiring 120 seconds of
     fresh bound cellular proof with `recovery_paused=false`.

Each boot creates a durable private journal keyed by host `boot_id` (refusing
same-boot replay) and writes redacted status to
`/var/lib/aoc-v2-jetson-boot/public/status.json`. Verify units and boot IDs,
actual USB speed, lab registration/session, cellular ordinary routing and
independent Wi-Fi access after a real cold reboot. With two UEs, configure and
reboot only one, complete acceptance, then proceed to the other. Do not equate
service enablement with tested cold-boot recovery.
