# Jetson Console operations

## Service lifecycle

Use the installed manager for all lifecycle actions:

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
