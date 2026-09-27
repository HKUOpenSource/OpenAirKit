# Jetson Console setup

## Prerequisites

Use Linux ARM64, Python 3.10, systemd, NetworkManager and the supported RM520N
modem. Wi-Fi must have a unique address and the preferred IPv4 default route;
Tailscale must route the configured Spark management address. The modem must
have its own RNDIS DHCP address. OCUDU validates these prerequisites and never
replaces an administrator-owned default route or stops an external service.
Port `127.0.0.1:8878` and the discovered AT port must be free.

Configure the site's NetworkManager profiles once, if necessary. Review active
profiles with `nmcli -f NAME,UUID,TYPE,DEVICE connection show --active`. Keep the
management Wi-Fi profile as the preferred default and the modem profile's
`ipv4.never-default` enabled. Applying a connection profile can interrupt that
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

`start` prepares only the configured data-probe routes, starts the two services,
and resumes observation with automatic recovery paused. SIM registration and
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
