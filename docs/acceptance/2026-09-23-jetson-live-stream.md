# Jetson live update repair — 2026-09-23

[简体中文](2026-09-23-jetson-live-stream.zh-CN.md)

Jetson 0.5.1 removes scheduled SSE disconnects and reduces the time spent waiting
for independent network probes. Device evidence still expires after 20 seconds;
missing live updates still become stale after 10 seconds. The UI distinguishes
expired evidence from lost updates instead of describing both as stream failure.

## Evidence and cause

The deployed 0.5.0 Web and device services had no automatic restarts or logged
exceptions. All 36 read-only samples over 72 seconds reported registration, an
active data session and verified connectivity. Cached evidence reached 19.2 seconds
of age, close to the 20-second freshness boundary. Stream requests returned 200
and recurred every 21–22 seconds. The server deliberately ended streams after
approximately 15 seconds.

A timing replay using actual cached device status and the page's freshness rule
reproduced a stale decision 1.38 seconds after the last simulated event: the held
evidence was 20.09 seconds old while the backend already had 8.34-second-old
evidence and a verified connection. This was a read-only timing replay, not a
capture of the user's authenticated browser. The user's browser/forwarding path
was not independently confirmed.

## Question, call path and impact

Question: why can a healthy device appear to lose its live stream? No CodeGraph
index exists. The inspected path is `Modem.snapshot → Agent.sample → four network
probes → cached status → API events/stream → App stale → Banner`.

- The four fixed, interface-bound read-only probes now run concurrently, with
  existing per-command deadlines and cancellation. The hardware lock still covers
  the sample; modem commands and network mutations remain serialized. Probe
  failures remain independent, and required failed/unknown evidence prevents a
  connected claim. No timestamp is advanced to conceal old measurements.
- SSE remains open while the client is connected. Each status update validates
  authentication before and after the executor call. Logout/expiry terminates the
  stream; executor errors emit `unavailable` and retry on the same connection.
  Cache prevention and a one-second reconnect hint accompany the stream.
- Web graceful shutdown is bounded to five seconds, below systemd's 20-second
  stop limit, so an open stream cannot indefinitely delay deployment.
- The UI uses separate messages for transport silence and device evidence expiry.
  Both suppress a current connected claim; the freshness thresholds are unchanged.

## Validation and delivery

Backend regression covers a stream across multiple former lifetimes, executor
error recovery, disconnect cleanup, logout, session expiry during an executor
call, concurrent probes and required probe failure. Browser regression checks a
single real stream for 35 seconds, stale evidence on a functioning stream, loss of
updates, and session expiry, alongside the existing desktop/mobile checks.

- `make test-jetson-backend VENV=local/bootstrap-check`: 58 tests passed.
- `make e2e-jetson VENV=local/bootstrap-check`: desktop/mobile browser regression
  passed, including the 35-second uninterrupted stream and both stale cases.
- `make build-jetson-release VENV=local/bootstrap-check`: frontend typecheck/build,
  locked ARM64 wheel validation and offline archive verification passed. The
  pre-existing Vite 500 kB bundle advisory remains.
- Documentation, release-boundary and license audits, plus `git diff --check`, pass.
- The device validated archive checksums, all packaged files and native `visudo`
  policy syntax. An isolated unprivileged Python 3.10 environment passed offline
  dependency installation, `pip check` and new backend imports.

The administrator activated the exact 0.5.1 approval, and the application is now
running release `186b6c4659cc5e14`. Installation, rollback to 0.5.0
(`c4e60f990fc61882`) with a successful health response, and reinstallation passed
through the restricted helper. The old device evidence was briefly stale directly
after startup; final 0.5.1 device health is `ok` with fresh connected evidence.
The payload remains under the device SSH account's home at
`aoc-deploy/jetson-live-0.5.1-20260923/`. Approval verification passed before and
after deployment. The account, role and exact sudo action list remain unchanged. See
[maintenance approval boundaries](../../deploy/maintenance/README.md).

| Artifact | Identifier / SHA-256 |
| --- | --- |
| Release | `186b6c4659cc5e14` |
| Manifest | `6757bdcdafcc5fc73b1bbd7d4395d7c05bbc209f8248f53c5bcb96806288be37` |
| Application archive | `5498e55585343ef84fcceea209e0f7f0d2a2699f5283702347033b73407af6af` |
| New approval | `860dab1de5a00c1806aea71a1c7d952c9820a22bc4e2eb308429b1b4b864f307` |
| Previous approval | `f1c013f979ba20b1f4fe5f16dfc32fc2defb9ba2dc2b7d779e7065257185e705` |

The manifest records the current development working tree (`dirty=true`). Both
V2 services are active, disabled at boot, with zero automatic restarts. All 48
manifest files match; served HTML and entry JS/CSS match the installed files, SPA
routes work and unauthenticated status/stream requests return 401. The successful
rollback exercised the helper-managed checkpoint at
`/var/lib/aoc-maintenance/jetson-rollback.json`; protected database/checkpoint
contents were not independently queried.

Post-deployment observation completed over 120.09 seconds. All 57 cached-status
reads reported healthy registration, active data session and verified connection.
Backend evidence age ranged from 4.872 to 15.470 seconds, versus the previous
19.2-second observed maximum. Across 12 distinct hardware samples, sampling
intervals were 10.745–10.774 seconds. Maximum status-read latency was 123.6 ms.
Evaluating the page's age rule between approximately two-second updates gave a
maximum held evidence age of 17.222 seconds and zero stale decisions; the
20-second threshold was unchanged. This is a live read-only timing observation,
not a capture of rendered browser state or authenticated SSE payloads.

From final startup at 21:39:11 through 21:42:26 (UTC+8), service logs contain one
authenticated stream start at 21:39:12, no periodic reconnects and no exceptions.
The two 401 responses were our deliberate unauthenticated status/stream checks.
Both services remained active with zero automatic restarts. This bounded check
does not establish long-term behavior under every network fault.

No Spark deployment, protocol-stack restart or modem recovery was performed.
Automatic recovery remains paused as it was before this update; maintenance mode
is off. Refresh the browser page to load the updated frontend messages.
