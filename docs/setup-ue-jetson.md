# Jetson Console Setup

[简体中文](setup-ue-jetson.zh-CN.md)

This guide covers installing, commissioning, and optionally enabling unattended
cold-boot attachment for **Jetson Console** on **Jetson Orin** paired with a
**Quectel RM520N-GL** modem mounted on the
**Waveshare SIM8262E-M2 5G for Jetson Orin** expansion board.

## Prerequisites

<table>
  <tr>
    <td align="center" valign="bottom" width="33%"><img src="assets/hardware/jetson-orin-nano.webp" width="145" alt="Jetson Orin Nano" /><br/><sub><b>Jetson Orin Nano</b></sub></td>
    <td align="center" valign="bottom" width="33%"><img src="assets/hardware/waveshare-m2-5g-carrier.webp" height="90" alt="Waveshare M.2 5G Carrier" /><br/><sub><b>Waveshare M.2 Carrier (C for RM5XX)</b></sub></td>
    <td align="center" valign="bottom" width="33%"><img src="assets/hardware/quectel-rm520n-gl.webp" height="90" alt="Quectel RM520N-GL" /><br/><sub><b>Quectel RM520N-GL</b></sub></td>
  </tr>
</table>

- **Host & OS**: Jetson Orin (ARM64, Ubuntu 22.04, Python 3.10, `systemd`, `NetworkManager`).
- **Modem & USB**: Quectel RM520N-GL seated in the Waveshare carrier over USB 3.0; `ModemManager.service` stopped and disabled; loopback port `127.0.0.1:8878` free. Confirm `device.at_interface_number` in `/etc/aoc-v2-jetson/device.json` matches your RNDIS/ECM USB interface layout per [Hardware Notes](reference/hardware-notes.md).
- **Management network**: An active out-of-band Wi-Fi uplink with an IPv4 fallback gateway and a `tailscale0` route reaching Spark's management address. Keep any administrator-owned default route metrics strictly above `10` so Jetson Console's protocol-186 routing (`metric 5` Wi-Fi / `metric 10` cellular) operates without interfering with external NetworkManager profiles.

## 1. Install and Commission

Build the ARM64 release archive with `make build-jetson-release`, transfer and
unpack it on Jetson Orin, and run archive verification, host preflight checks,
and installation (initial installation prompts interactively for a new Console
password):

```sh
python3 -I -B deploy/manage.py verify
python3 -I -B deploy/manage.py preflight
sudo bash deploy/install-jetson.sh
```

The installer deploys the runtime into `/opt/agentic-ocudu/jetson`, starts the
loopback Web UI service, and leaves both systemd units disabled at boot.

Next, stop Jetson Console, commission it with Spark's actual management IPv4
address (substituting the real Tailscale address for the RFC 5737 documentation
placeholder `192.0.2.20`), and start the services:

```sh
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py stop
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py commission \
  --spark-address 192.0.2.20 --wifi-interface auto
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py start
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py status
```

`commission` binds this installation to the inserted USIM identity fingerprint
and management interfaces using the deployed application runtime.

## 2. Verify via Web Console

1. Open an SSH tunnel to `127.0.0.1:8878` and sign in to **Overview** / **Device Setup**.
2. Execute **Device Setup** and confirm USIM readiness, NR SA registration, active IPv4 PDU, verified bound data probes, `management_protected = true`, and automatic switching to cellular preferred egress after consecutive clean probes.
3. Validate one complete `manage.py stop` and `manage.py start` cycle (including route cleanup) prior to routine operation.

To configure passwordless operator wrappers (`~/aoc-ops/jetson/start.sh`),
deploy the matching maintenance package per [Maintenance Helper](../deploy/maintenance/README.md)
and follow [Jetson Operations](jetson-operations.md).

## 3. Opt-in Boot Coordination

To enable unattended cold-boot attachment (`deploy/jetson/boot_connect.py`
installed at `/opt/agentic-ocudu/jetson/boot_connect.py`):

1. **Validate read-only AT compatibility** while `aoc-v2-jetson-device.service` is stopped, using the AT queries and USB checks documented in [Hardware Notes](reference/hardware-notes.md#quectel-rm520n-gl-qmap-and-mpdn-firmware-check).
2. **Generate `/etc/aoc-v2-jetson/boot.json` (`0600`, root-owned)** *after* application installation so `device_sha256`, `manifest_sha256`, `sim_sha256`, `usb_speed_mbps`, and `modem_configuration` match the active installation (without storing subscriber keys). Create `/var/lib/aoc-v2-jetson-boot/private` (`0700`) and `/var/lib/aoc-v2-jetson-boot/public` (`0755`).
3. **Install the systemd drop-in and oneshot boot unit**:
   - `/etc/systemd/system/aoc-v2-jetson-device.service.d/boot-ready.conf`: sets `TimeoutStartSec=360`, clears `ExecStartPre=`, and chains `boot_connect.py ready` -> `site_guard.py` -> `network_entry.py --config /etc/aoc-v2-jetson/device.json --action fallback` so USB enumeration, modem DHCP, Wi-Fi, and `tailscale0` settle before `device_entry.py` starts.
   - `/etc/systemd/system/aoc-v2-jetson-boot.service` (`Type=oneshot`, `After=aoc-v2-jetson-device.service aoc-v2-jetson-web.service`): waits up to `30 s` for `/run/aoc-v2-jetson/device.sock` and invokes `/usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/boot_connect.py connect` (`TimeoutStartSec=1200`) to execute one Device Setup sequence and confirm sustained cellular connectivity with automatic recovery enabled.
4. **Verify via an unattended cold reboot**: inspect systemd units, `boot_id`, `/var/lib/aoc-v2-jetson-boot/public/status.json`, cellular default egress, and out-of-band Wi-Fi/`tailscale0` management reachability. When provisioning multiple UEs, validate one host per cold reboot.
