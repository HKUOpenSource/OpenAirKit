# Jetson Console Setup

[简体中文](setup-ue-jetson.zh-CN.md)

This guide covers installing, commissioning, and optionally enabling unattended
cold-boot attachment for **Jetson Console** on **Jetson Orin** with a
**Quectel RM520N-GL** modem mounted on the
**[Waveshare SIM8262E-M2 5G for Jetson Orin](https://www.waveshare.net/shop/SIM8262E-M2-5G-for-Jetson-Orin.htm)**
expansion board.

## Prerequisites

- **Host & OS**: Jetson Orin (ARM64, Ubuntu 22.04, Python 3.10, `systemd`, `NetworkManager`).
- **Modem & USB**: Quectel RM520N-GL seated in the Waveshare carrier over USB 3.0; `ModemManager.service` stopped and disabled; port `127.0.0.1:8878` free. Verify `device.at_interface_number` in `/etc/aoc-v2-jetson/device.json` matches your RNDIS/ECM USB layout per [Hardware Notes](reference/hardware-notes.md).
- **Management network**: An active Wi-Fi uplink with an IPv4 fallback gateway and a `tailscale0` route reaching Spark's management IP. Keep any administrator-owned default route metrics strictly above `10` so Jetson Console's protocol-186 routing (`metric 5` Wi-Fi / `metric 10` cellular) operates cleanly without altering external NetworkManager profiles.

## 1. Install and Commission

Build the ARM64 archive with `make build-jetson-release`, transfer and extract
it on Jetson Orin, then verify, preflight, and install (a fresh install prompts
interactively for a new Console password):

```sh
python3 -I -B deploy/manage.py verify
python3 -I -B deploy/manage.py preflight
sudo bash deploy/install-jetson.sh
```

The installer places the runtime under `/opt/agentic-ocudu/jetson`, starts the
loopback Web service, and leaves both systemd units disabled at boot.

Next, stop Jetson Console, commission it with Spark's actual management IPv4
address (replacing the RFC 5737 documentation placeholder `192.0.2.20`), and
start services:

```sh
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py stop
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py commission \
  --spark-address 192.0.2.20 --wifi-interface auto
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py start
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py status
```

`commission` binds this installation to its inserted SIM fingerprint and
management interfaces using the installed application environment automatically.

## 2. Verify via Web Console

1. Open an SSH tunnel to `127.0.0.1:8878` and sign in to **Overview** / **Device Setup**.
2. Run **Device Setup** and confirm SIM readiness, NR SA registration, active IPv4 PDU, verified bound data probes, `management_protected = true`, and automatic switching to cellular preference after consecutive clean probes.
3. Verify a complete `manage.py stop` and `manage.py start` cycle (including route cleanup) before routine use.

For passwordless operator shortcuts (`~/aoc-ops/jetson/start.sh`), install the
matching maintenance bundle via [Maintenance Helper](../deploy/maintenance/README.md)
and follow [Jetson Operations](jetson-operations.md).

## 3. Opt-in Boot Coordination

To enable unattended cold-boot attachment (`deploy/jetson/boot_connect.py`
installed at `/opt/agentic-ocudu/jetson/boot_connect.py`):

1. **Confirm read-only AT compatibility** while `aoc-v2-jetson-device.service` is stopped using the AT commands and USB checks documented in [Hardware Notes](reference/hardware-notes.md#quectel-rm520n-gl-qmap-and-mpdn-firmware-check).
2. **Generate `/etc/aoc-v2-jetson/boot.json` (`0600`, root-owned)** *after* completing application installation so `device_sha256`, `manifest_sha256`, `sim_sha256`, `usb_speed_mbps`, and `modem_configuration` match the installed runtime (containing zero SIM keys). Create `/var/lib/aoc-v2-jetson-boot/private` (`0700`) and `/var/lib/aoc-v2-jetson-boot/public` (`0755`).
3. **Install the systemd drop-in and oneshot boot unit**:
   - `/etc/systemd/system/aoc-v2-jetson-device.service.d/boot-ready.conf`: sets `TimeoutStartSec=360`, resets `ExecStartPre=`, and chains `boot_connect.py ready` -> `site_guard.py` -> `network_entry.py --config /etc/aoc-v2-jetson/device.json --action fallback` so USB enumeration, modem DHCP, Wi-Fi, and `tailscale0` are ready before `device_entry.py` starts.
   - `/etc/systemd/system/aoc-v2-jetson-boot.service` (`Type=oneshot`, `After=aoc-v2-jetson-device.service aoc-v2-jetson-web.service`): waits up to `30 s` for `/run/aoc-v2-jetson/device.sock` and executes `/usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/boot_connect.py connect` (`TimeoutStartSec=1200`) to run one standard Device Setup cycle and confirm sustained bound cellular proof with automatic recovery enabled.
4. **Validate with a real cold reboot**: inspect systemd units, `boot_id`, `/var/lib/aoc-v2-jetson-boot/public/status.json`, cellular default routing, and independent Wi-Fi/`tailscale0` management reachability. When commissioning multiple UEs, reboot and verify one UE at a time.
