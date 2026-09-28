# Spark system setup

## Prerequisites

Use an ARM64 host with Python 3.12, systemd, Docker Compose and a supported
B210 connected over USB 3. Confirm that ports `127.0.0.1:8877` and
`127.0.0.1:8001` are available. The monitor, radio and core have separate
release and lifecycle boundaries.

Verify Open5GS image digests from `stacks/open5gs/artifacts.lock.json` and source
revisions from `stacks/open5gs/sources.lock.json`, the OCUDU revision from
`config/upstreams.json`, and site settings derived from
`config/network-contract.json`. Production subscriber material must be loaded
from the protected deployment state, never from the repository.

## Install the monitoring platform

Build with `make build-spark-release`, transfer the resulting ARM64 release,
then run its platform installer in preflight and install modes. The target is
`/opt/agentic-ocudu/monitor`; the three platform services remain disabled at
boot. Installing the monitor does not start or restart the protocol stack.

From the unpacked Spark release, use the actual installer actions:

```sh
python3 -I -B install.py verify --path .
python3 -I -B install.py check-host --path .
sudo python3 -I -B install.py install --path .
```

After preparing the protocol stack, approve the matching
[maintenance bundle](../deploy/maintenance/README.md) and install the
[Spark lifecycle scripts](spark-operations.md). Full-stack startup and status
check N2 independently from service process state.

## Prepare the protocol stack

Follow the [independent stack package guide](../deploy/spark/stack/README.md):
build the pinned radio artifacts, render/provision a private authenticated N6
bundle, then stage and verify with `deploy/spark/stack/package.py`. Its fresh-install
path supplies the V2 controller and core/radio units without starting services;
existing installations are never overwritten. Local package tests do not certify
target installation or RF operation. `scripts/spark` supplies the subsequent
guarded telemetry setup.
Validate B210 ownership, the core network, N2 and the loopback JSON metrics
endpoint before accepting UE traffic. Bind the metrics endpoint to loopback and
restrict it to the collector account.

## Verify

Open `127.0.0.1:8877` through an SSH tunnel. Verify all core containers, gNB
generation, N2, current UE context, active PDU and independent N3/N6 evidence.
Use a Jetson-side bound probe for end-to-end data-path acceptance.
