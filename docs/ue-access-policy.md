# UE access and lab policy

This project supports OCUDU + Open5GS. A UE does not need the Spark management
address, gNB implementation or fixed PCI to perform standard network access.
The lab must align its SIM subscription, PLMN, DNN, slice and supported PDU type.
This application currently validates IPv4 only; slice and QoS configuration are
expectations, not proof that the modem negotiated them.

Jetson schema 3 separates `network` (access and PDU expectations), `selection`
(observed NR SA/band/optional PCI/optional **SSB** ARFCN), `diagnostics` (bound
probe addresses and required probes), `management` (Wi-Fi/Tailscale protection)
and `recovery` (bounded timing and attempt policy). Fields are validated
individually. Changing a configured expectation does not reconfigure Open5GS or
silently program the modem. Setup checks and preserves existing radio settings.

`selection.mode` is `observe_only`. It reports policy match and does not issue
frequency or cell-lock commands. Such writes need verified modem capability and
complete before/after readback and are intentionally unsupported. A carrier-center
ARFCN in `radio_reference` is not a serving SSB ARFCN. Migrating schema 2 preserves
the old band/PCI observation policy and radio reference. An operator may set PCI
and SSB ARFCN to null after reviewing the lab policy. Neither observation nor
frequency restriction eliminates physical RF interference.

The Overview reports registration, active PDU, verified data path, lab match and
management protection independently. Data verification requires current SIM,
NR SA on the access PLMN, registration, an active IPv4 PDU in the expected pool,
RNDIS addressing and the configured multiple bound probes. A registration,
serving-cell, PDU or interface change invalidates earlier probes. Expired evidence
cannot remain connected. A diagnostic failure does not clear the registration
indicator, and a management failure blocks writes without changing registration.

After successful setup/recovery enables automation, registration/PDU loss starts
a natural recovery wait (120 seconds by default), followed by at most two
recovery jobs, at least 300 seconds apart. Each job allows at most one reconnect;
reset cooldown survives process restart. Cancellation and maintenance pause
automation. Diagnostic-only failures never cause resets. The budget resets only
after data remains healthy for the cooldown period.

The ext-DN service returns a fixed small HTTP response at `/health` on port 8080,
inside the core network. It publishes no host port and runs no throughput server.
Historical benchmark evidence remains historical; it is no longer a release gate.
