# Jetson troubleshooting

## Web service fails (`203/EXEC`, permission denied, or port 8878 busy)

- **Port `127.0.0.1:8878` conflict**: Check `ss -tlnp | grep 8878`. If a legacy
  console service is still enabled or running, disable and stop the conflicting
  unit while keeping its directory backup separately for rollback, then rerun
  `aoc-maintain start`.
- **`status=203/EXEC` or `PermissionError` on `web.json`**: When upgraded under a
  restrictive `umask 077`, older installers could create `venv/` as `0700` or
  `/etc/aoc-v2-jetson/web.json` as `0600`. `deploy/jetson/manage.py` in `0.6.2+`
  enforces `0o022` for `venv` and explicit `os.chmod(..., mode)` in
  `private_write()`. Ensure `venv` allows non-root read/execute (`0755`/`0644`,
  no group/world write) and `web.json` is `0640 root:aoc-v2-jetson-web`.

## Executor unavailable or USB discovery rejected

Check both units with `/usr/local/sbin/aoc-maintain status` (or `manage.py status`),
then inspect `journalctl -u aoc-v2-jetson-device.service`. Confirm the release
path exists, `/etc/systemd/system/aoc-v2-jetson-device.service.d` is `0755` if
drop-ins are installed, and `device.at_interface_number` matches the active
RM520N USB topology:

- RNDIS (`rndis_host` at `00/01`, serials `02..05`) requires `"04"`.
- ECM (`cdc_ether` at `04` or `0a`, serials `00..03`) requires `"02"`.

If `hardware.discover()` reports `Configured AT interface differs from USB layout; expected 02`
or `04`, update `/etc/aoc-v2-jetson/device.json` while services are stopped and
verify with `aoc-maintain start`. Remember to recompute `/etc/aoc-v2-jetson/boot.json`
if `boot_connect.py` is enabled.

## Serial device occupied

Enter maintenance, stop the current owner and verify the process has released
the discovered AT device (`fuser /dev/ttyUSB*`). The executor uses a process lock
and exclusive serial open; deleting the lock without checking the process can
create two writers. Also ensure `ModemManager.service` remains disabled/masked.

## Registration or PDU failure

Read SIM state, serving cell, `C5GREG`, context definitions, activation and
address evidence in that order. A registered modem with `0.0.0.0` does not have
a valid data session. Reconnect once only after configuration readback matches
the network contract.

## Data path or diagnostic target failure

Confirm the current modem interface, its IPv4 address, route to the configured
probe target and the protected management route. Run probes bound to that
interface; an unbound ping may have used Wi-Fi and is insufficient. Read
registration, PDU, lab policy and management protection independently. A failed
UPF or ext-DN ping does not mean registration was lost. The ext-DN container
serves a fixed small `/health` response on TCP 8080; it has no throughput
listener.

## Boot coordinator stopped or skipped

Inspect `journalctl -u aoc-v2-jetson-boot.service` and
`/var/lib/aoc-v2-jetson-boot/public/status.json`. Common causes include
`device_sha256` / `manifest_sha256` drift in `/etc/aoc-v2-jetson/boot.json`
after an application upgrade (always refresh `boot.json` after `manage.py install`),
or an interrupted prior run that left `maintenance=true` or `uncertain-selection.json`
for operator review.
