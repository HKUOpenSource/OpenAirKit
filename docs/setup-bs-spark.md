# Spark system setup

## Prerequisites

Use an ARM64 host with Python 3.12, systemd, Docker Compose and a supported
B210 connected over USB 3. Confirm that ports `127.0.0.1:8877` and
`127.0.0.1:8001` are available. The monitor, radio and core have separate
release and lifecycle boundaries.

Verify image digests from `config/images.lock.json`, source revisions from
`config/upstreams.json` and site settings derived from
`config/network-contract.json`. Production subscriber material must be loaded
from the protected deployment state, never from the repository.

## Install the monitoring platform

Build with `make build-spark-release`, transfer the resulting ARM64 release,
then run its platform installer in preflight and install modes. The target is
`/opt/agentic-ocudu/monitor`; the three platform services remain disabled at
boot. Installing the monitor does not start or restart the protocol stack.

## Prepare the protocol stack

Use the stack-specific tools under `deploy/spark/stack` and `scripts/spark`.
Validate B210 ownership, the core network, N2 and the loopback JSON metrics
endpoint before accepting UE traffic. Bind the metrics endpoint to loopback and
restrict it to the collector account.

## Verify

Open `127.0.0.1:8877` through an SSH tunnel. Verify all core containers, gNB
generation, N2, current UE context, active PDU and independent N3/N6 evidence.
Use a Jetson-side bound probe for end-to-end data-path acceptance.
