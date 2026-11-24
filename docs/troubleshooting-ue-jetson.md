# Jetson Troubleshooting

[简体中文](troubleshooting-ue-jetson.zh-CN.md)

Use the symptom-based checks below when diagnosing issues on **Jetson Orin**.

## Web Service Fails to Start (`8878` Conflict or Permissions)

- **Port `127.0.0.1:8878` occupied**: Run `ss -tlnp | grep 8878`, stop and disable any conflicting unit holding the port, and re-run `aoc-maintain start`.
- **Service execution error (`203/EXEC`)**: Verify the installed `venv/` tree is readable and executable by the unprivileged service user (`0755`/`0644`, no group/world write bits) and `/etc/aoc-v2-jetson/web.json` is `0640 root:aoc-v2-jetson-web`.

## Device Executor Fails or USB Discovery Rejected

- Run `/usr/local/sbin/aoc-maintain status` (or `manage.py status`) and inspect `journalctl -u aoc-v2-jetson-device.service`.
- Verify `device.at_interface_number` in `/etc/aoc-v2-jetson/device.json` matches the active RNDIS or ECM USB interface layout documented in [Hardware Notes](reference/hardware-notes.md#quectel-rm520n-gl-usb-interface-layouts). Update `device.json` while services are stopped, and refresh `/etc/aoc-v2-jetson/boot.json` if boot coordination is enabled.

## AT Serial Device Occupied

- Enter Maintenance mode (or stop `aoc-v2-jetson-device.service`), confirm no external process holds the discovered AT port (`fuser /dev/ttyUSB*`), and verify `ModemManager.service` stays disabled and masked. Never remove `/var/lib/agentic-ocudu/v2-ue/serial.lock` while a process holds the serial device.

## Registration or Data PDU Failure

- Inspect **Overview** layers sequentially: USIM -> serving cell -> `C5GREG` registration -> context definition -> PDU activation -> interface IPv4 address.
- If a registered modem with a valid IPv4 lease passes no host traffic, verify QMAP WWAN / MPDN bindings per [Hardware Notes](reference/hardware-notes.md#quectel-rm520n-gl-qmap-and-mpdn-firmware-check).

## Data Path or Diagnostic Target Failure

- Verify the modem interface IPv4 address, bound host routes, and `management_protected` state (`Wi-Fi` + `tailscale0`). Always bind manual probes to the modem interface (for example, `ping -I <modem-if> ...`); unbound tests egress over the out-of-band Wi-Fi gateway when cellular preference is inactive.
- Check core `ext-DN` HTTP `/health` (TCP `8080`) reachability separately from NR registration state.

## Boot Coordinator Stopped or Skipped

- Inspect `journalctl -u aoc-v2-jetson-boot.service` and `/var/lib/aoc-v2-jetson-boot/public/status.json`.
- **Checksum mismatch after upgrade**: Regenerate `/etc/aoc-v2-jetson/boot.json` after `manage.py install` so `device_sha256` and `manifest_sha256` match the active release.
- **Gateway ICMP rate limiting**: Inspect management Wi-Fi association and upstream gateway ICMP policies if multi-probe retries fail despite an active management link.
