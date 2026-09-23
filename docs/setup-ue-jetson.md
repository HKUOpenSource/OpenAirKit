# Jetson Console setup

## Prerequisites

Use an ARM64 host with Python 3.10, systemd, NetworkManager and the supported
RM520N modem. Confirm the Wi-Fi and Tailscale management interfaces before any
route change. Port `127.0.0.1:8878` must be free, and no other process may own
the modem serial port.

The release must contain `RELEASE-VERSION`, a verified manifest, locked Python
dependencies, an offline wheelhouse and third-party license material. Keep
production configuration outside the unpacked release.

## Install

From the unpacked Jetson release:

```sh
sudo ./deploy/install-jetson.sh preflight
sudo ./deploy/install-jetson.sh install
sudo /opt/agentic-ocudu/jetson/current/venv/bin/python -I \
  /opt/agentic-ocudu/jetson/current/deploy/manage.py status
```

The install target is `/opt/agentic-ocudu/jetson`. Installation leaves
`aoc-v2-jetson-device.service` and `aoc-v2-jetson-web.service` disabled at
boot. Review the preflight management-interface result before starting them.

## Verify

Start the platform with the installed manager and open the UI through an SSH
tunnel to `127.0.0.1:8878`. Verify login, health, SSE updates, modem discovery,
registration, the data PDU and the bound data path separately. Run a short
bound connectivity check only after the route view names the modem interface.

Use [Jetson operations](jetson-operations.md) for maintenance and rollback, and
[Jetson troubleshooting](troubleshooting-ue-jetson.md) if discovery or data
verification fails.
