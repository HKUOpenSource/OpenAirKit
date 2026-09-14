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

## Recovery and speed tests

Recovery first checks current state and repairs only owned routes. A task may
perform one modem reconnect when needed and persists every step, cancellation
and cleanup result. A timeout is followed by readback before any retry.

Speed tests bind to the discovered modem interface and verify the effective
route. Uplink and downlink results belong to one task, retain partial failures
and are never combined across runs. Wi-Fi remains the protected management
path when route ownership cannot be proven.

## Upgrade and rollback

Stop the platform, verify the new release, install it, start it and validate
health before running device operations. Rollback restores both the previous
release link and compatible database backup. If a workflow changed modem or
network state, use its recorded recovery action as well; changing application
code alone does not restore device state.
