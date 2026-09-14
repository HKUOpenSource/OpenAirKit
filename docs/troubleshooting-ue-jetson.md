# Jetson troubleshooting

## Executor unavailable

Check both units with the installed manager, then inspect the device-service
journal. Confirm the release path exists, the Python module imports from the
installed backend and the Unix socket owner/mode match the web service. Do not
work around the socket with a general privileged shell.

## Serial device occupied

Enter maintenance, stop the current owner and verify the process has released
the discovered AT device. The executor uses a process lock and exclusive serial
open; deleting the lock without checking the process can create two writers.

## Registration or PDU failure

Read SIM state, serving cell, `C5GREG`, context definitions, activation and
address evidence in that order. A registered modem with `0.0.0.0` does not have
a valid data session. Reconnect once only after configuration readback matches
the network contract.

## Data path failure

Confirm the current modem interface, its IPv4 address, route to the configured
probe target and the protected management route. Run the probe bound to that
interface. A successful unbound ping may have used Wi-Fi and is insufficient.

## Speed-test failure

Keep uplink and downlink errors separate. Wait for the previous iperf3 control
session to close, verify the target service and confirm no child process remains
after cancellation. Retain partial results and the task identifier.
