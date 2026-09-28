# Cellular default-route failback — 2026-09-28

## Question and cause

Does restored cellular connectivity automatically replace a Wi-Fi default?
Before this repair it did not. `Agent.auto_reconcile` returned once registration
and the data PDU were active; `network.helper(promote)` only installed bound probe
host routes. Wi-Fi was required to remain the preferred default. A successful
public diagnostic route therefore did not prove that ordinary IPv4 traffic used
cellular. NetworkManager could independently install a cellular default after USB
re-enumeration, explaining the observed difference between devices and times.

Read-only inspection of both Jetsons found policy routing disabled in their
kernels. This repair uses main-table routes and does not claim independent Wi-Fi
transport for the Tailscale management connection.

## Call path and impact

`Agent.serve -> sample -> reconcile_routes -> Network.action -> network.helper ->
managed_routes / managed_defaults -> exact iproute2 operations`.
No `.codegraph` index exists in this checkout; source inspection supplied the
call-path evidence.

- Two complete fresh healthy probe sets, including Internet, prefer cellular.
  Two failed sets return to Wi-Fi. Missing registration/PDU/interface or evidence
  older than 20 seconds triggers fallback on the next reconciliation. Normal
  samples are 10 seconds apart. Reusing a cached or partly refreshed sample does
  not count twice. Registration, session, radio and interface changes invalidate
  the confirmation streak.
- Routing remains enabled when automatic modem resets are paused. It issues no
  modem writes. Ready/paused tasks fall back after their evidence expires.
- Main-table default routes use protocol 186, metric 5 for fallback and metric 10
  for cellular. Original system defaults and NetworkManager profiles are retained.
  Foreign high-priority defaults and ambiguous ownership fail closed.
- `egress-state.json` records exact default-route ownership separately from
  `network-state.json` for diagnostic host routes. Timed-out additions retain
  uncertain ownership. Cleanup never removes a changed or foreign route.
- Dedicated probe routes remain cellular-bound during Wi-Fi fallback. USB
  re-enumeration replaces only exact owned host/default routes. Full manager stop
  cleans both journals, including when the modem is absent.
- Systemd selects fallback before executor start and after executor stop. Entering
  maintenance selects fallback before releasing serial ownership. Ordinary IPv4
  egress is read from a destination outside the diagnostic host routes.

Wi-Fi must remain addressed with a unique gateway, and the configured Spark route
must use Tailscale. Existing default metrics must exceed 10. Route changes may
briefly reconnect Tailscale; `management_protected` reports fallback availability,
not independent or uninterrupted management transport. IPv6 failover is out of scope.

## Validation and deployment boundary

- Jetson backend: 99 tests passed, including 57 agent/network regressions.
- Repository lifecycle/release tests: 172 passed.
- Frontend behavior: 7 passed; Jetson type check and production build passed.
- Documentation and release boundary audits passed.
- Real Linux route integration passed in a disposable `--network none` container,
  with `NET_ADMIN` only for that private namespace, no host mounts, and five
  explicitly packaged test/source files. Eleven cases include three failover/
  failback cycles, bound probes during fallback, preservation of foreign routes,
  rejection of changed ownership, USB re-enumeration and offline cleanup.
  Modem discovery was substituted; this is not a physical cellular outage test.

Deployed Jetson version: **0.6.2**, release `9657a217e057b275`.
Manifest SHA-256: `ed11769f5320d2f5a2dc4f12365809bf3b1b1ba77b0f66c891f11b6a8a5f36f2`.
Maintenance approval SHA-256:
`173c66872aaf4767b58f4fc6eff77ec1b5db204a900d774927d883f908e60050`.

Both targets passed non-root archive verification, native sudo policy syntax
checks, upgrade prerequisites, offline dependency validation and all 57 synthetic
agent/network tests under Python 3.10. Jetson browser regression passed at desktop
and mobile sizes with no reported failures.

## Hardware deployment and failback

After the administrator activated the exact approval above on both devices, its
hash was verified before installing Jetson A and then Jetson B. Both now run 0.6.2;
all 51 packaged file hashes match. Installation saved the prior-version rollback
checkpoint. Web and device services are active with no automatic restarts, and
boot startup remains disabled. Spark production services were not modified.

On each device, startup automatically selected the owned cellular default. The
approved maintenance action then selected Wi-Fi (metric 5), while the public
probe host route continued to select the modem. Resuming observation left Wi-Fi
selected until fresh probe confirmation; the background reconciler then removed
the owned Wi-Fi default and selected cellular (metric 10). Existing system
Wi-Fi and modem defaults at metrics 30000 and 100 remained intact throughout.

| Check | Jetson A | Jetson B |
| --- | --- | --- |
| Maintenance selects Wi-Fi | Passed | Passed |
| Cellular-bound probe route during fallback | Passed | Passed |
| First observed cellular default after resume | 28.35 s | 24.09 s |
| Three consecutive cellular confirmations | Passed | Passed |
| Modem auto-recovery paused during failback | True | True |
| Unbound public ICMP outside diagnostic host routes | 3/3 replies | 3/3 replies |

Timings include polling and sampling delays, not a promised switching deadline.
This physical-device check exercised a controlled maintenance/resume cycle without
resetting the modems or interrupting the RAN/core. A radio/USB outage was not
injected on production hardware. Failure/stale-evidence decisions and USB
replacement remain covered by the source and isolated Linux tests above.

Final joint observation passed all seven samples over 76.46 seconds. Both
Jetsons retained the owned cellular default and fresh registration/PDU/data evidence;
maximum observed evidence age was 15.61 seconds. Spark reported two registered UEs,
two active PDUs with distinct addresses and verified N3, one N2 setup with two UEs,
and all 12 core containers healthy. Both Jetson health endpoints returned all-ok.
