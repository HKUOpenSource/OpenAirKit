# Jetson Troubleshooting

[简体中文](troubleshooting-ue-jetson.zh-CN.md)

Use the symptom-based checks below when diagnosing issues on **Jetson Orin**.

## Web Service Fails to Start (`8878` Conflict or Permissions)

- **Port `127.0.0.1:8878` occupied**: Run `ss -tlnp | grep 8878`, stop/disable any conflicting console unit holding the port, and rerun `aoc-maintain start`.
- **Service permission errors (`203/EXEC`)**: Confirm the installed `venv/` is readable/executable by the non-privileged service account (`0755`/`0644`, no group/world write) and `/etc/aoc-v2-jetson/web.json` has `0640 root:aoc-v2-jetson-web`.

## Device Executor Fails or USB Discovery Rejected

- Run `/usr/local/sbin/aoc-maintain status` (or `manage.py status`) and inspect `journalctl -u aoc-v2-jetson-device.service`.
- Verify `device.at_interface_number` in `/etc/aoc-v2-jetson/device.json` matches the active RNDIS or ECM USB interface layout documented in [Hardware Notes](reference/hardware-notes.md#quectel-rm520n-gl-usb-interface-layouts). Update `device.json` while services are stopped, and refresh `/etc/aoc-v2-jetson/boot.json` if boot coordination is enabled.

## AT Serial Device Occupied

- Enter Maintenance mode (or stop `aoc-v2-jetson-device.service`), confirm no external process holds the discovered AT port (`fuser /dev/ttyUSB*`), and verify `ModemManager.service` stays disabled and masked. Leave `/var/lib/agentic-ocudu/v2-ue/serial.lock` untouched while any process holds the port.

## Registration or Data PDU Failure

- Inspect Overview layers in sequence: SIM -> serving cell -> `C5GREG` registration -> context definition -> PDU activation -> interface IPv4 address.
- If a registered modem with an active IPv4 address forwards no traffic, inspect QMAP WWAN / MPDN bindings per [Hardware Notes](reference/hardware-notes.md#quectel-rm520n-gl-qmap-and-mpdn-firmware-check).

## Data Path or Diagnostic Target Failure

- Verify the modem interface IPv4 address, bound host routes, and `management_protected` state (`Wi-Fi` + `tailscale0`). Always bind manual tests to the modem interface (e.g. `ping -I <modem-if> ...`); unbound pings route over Wi-Fi when cellular is not selected.
- Check core `ext-DN` HTTP `/health` (TCP `8080`) reachability separately from registration state.

## Boot Coordinator Stopped or Skipped

- Inspect `journalctl -u aoc-v2-jetson-boot.service` and `/var/lib/aoc-v2-jetson-boot/public/status.json`.
- **Checksum mismatch after upgrade**: Refresh `/etc/aoc-v2-jetson/boot.json` after running `manage.py install` so `device_sha256` and `manifest_sha256` match the active release.
- **Gateway ICMP rate limiting**: Check management Wi-Fi association and upstream gateway ICMP policy if multi-probe retries fail despite an active management link.
