# Jetson Console operations

## Service lifecycle

For normal local operation, use the separately deployed shortcuts:

```sh
~/aoc-ops/jetson/start.sh
~/aoc-ops/jetson/stop.sh
/usr/bin/python3 -I ~/aoc-ops/jetson/platformctl.py status
```

Run these as the commissioned SSH user. They use system Python and the existing
`sudo -n /usr/local/sbin/aoc-maintain` permission, with no interactive password
prompt. Both V2 services are started and checked; registration, PDU, data connection,
maintenance and recovery pause are reported separately. A disconnected UE produces
a warning, not an automatic reconnect. These scripts never request takeover,
maintenance exit or modem recovery. Existing executor shutdown/recovery policy still
applies; stopping the executor can persist its recovery pause.

Repeated start checks the running services without restarting them. Repeated stop
confirms both services, the device socket and web listener are stopped. Startup
requires prior commissioning; the scripts do not initialize a new installation.
Failures preserve current state and stop subsequent steps. Helper calls time out
after 330 seconds; each health wait is bounded to 60 seconds. An interrupted or timed
out command can leave a systemd job running: query status before retrying.

One user-level lock serializes these scripts across copies. Do not run lifecycle
actions through the UI or another entrypoint concurrently. The lock does not replace
the helper's own access/locking checks. Exit codes are 0 for success, 1 for execution
or verification failure, 2 for invalid arguments and 3 for a busy script. A successful
`status` query returns 0 even when services are stopped. Runtime output is English.

To install from a checkout on the device, first back up any existing destination,
then copy only the three standalone scripts:

```sh
mkdir -p ~/aoc-ops/jetson
install -m 0755 deploy/jetson/start.sh deploy/jetson/stop.sh \
  deploy/jetson/platformctl.py ~/aoc-ops/jetson/
```

Verify transfer hashes before execution. The same files can be copied over SSH;
no checkout is needed on the device. They are excluded from application releases,
do not enable boot startup, and can be reverted by restoring their saved copies
without rolling back the application. Do not put site addresses in these scripts.
See the [2026-09-24 lifecycle acceptance](acceptance/2026-09-24-platform-lifecycle.md)
for the completed device checks.

The underlying installed manager remains available to administrators:

```sh
sudo /opt/agentic-ocudu/jetson/current/venv/bin/python -I \
  /opt/agentic-ocudu/jetson/current/deploy/manage.py status
sudo /opt/agentic-ocudu/jetson/current/venv/bin/python -I \
  /opt/agentic-ocudu/jetson/current/deploy/manage.py start
sudo /opt/agentic-ocudu/jetson/current/venv/bin/python -I \
  /opt/agentic-ocudu/jetson/current/deploy/manage.py stop
```

`stop` must terminate the web process, device executor, bounded helper and
owned child tasks within its timeout. Confirm both systemd units are inactive
before another process opens the modem.

## Device status and setup

The Overview page separates SIM readiness, cell camping, 5GS registration,
PDU activation, pool membership, RNDIS addressing and verified data path.
Device Setup previews every write and records a private baseline before it
changes an allowed data context. Duplicate DNNs, conflicting CIDs or uncertain
device identity stop the workflow.

Maintenance mode waits for the current command, suspends collection and
recovery, and releases the serial port. Leaving maintenance rediscovers the
device and reads current state; it never replays an interrupted command.

## Recovery and connectivity

Recovery first checks current state and repairs only owned routes. A task may
perform one modem reconnect when needed and persists every step, cancellation
and cleanup result. A timeout is followed by readback before any retry.

After a network outage, automatic recovery waits 120 seconds, then permits at
most two attempts with a 300-second cooldown. It runs only after a successful
user setup/recovery has enabled it. Maintenance, uncertain management protection
or exhausted attempts stop writes. A failed diagnostic probe alone never resets
the modem. Successful data evidence must remain healthy for the cooldown before
the automatic attempt budget resets.

The four pages are Overview, Device Setup, History and Settings. Interface RX/TX
activity and bound low-traffic probes remain; active throughput tasks are removed.
See [UE access policy](ue-access-policy.md) for independent status meanings.

## Upgrade and rollback

Stop the platform, verify the new release, install it, start it and validate
health before running device operations. Rollback restores both the previous
release link and compatible database backup. If a workflow changed modem or
network state, use its recorded recovery action as well; changing application
code alone does not restore device state.

Schema 2 configuration migrates once to schema 3 during installation. The installer
backs up configuration and databases before migration. Database schema 2 preserves
old benchmark results but marks unfinished benchmark tasks interrupted and retired;
they cannot be launched. Roll back using the matching pre-upgrade backup.
