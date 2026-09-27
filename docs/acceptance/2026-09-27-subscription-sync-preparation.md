# Subscription transfer preparation — 2026-09-27

[简体中文](2026-09-27-subscription-sync-preparation.zh-CN.md)

Source base: `39dde4d0216dee973ed6cbf40ecb500e83c1ac74`, with this uncommitted
tooling change. Application versions remain Jetson 0.5.1 / Spark 0.2.0.
This record preserves the preparation-stage evidence. Production import and
two-device results are recorded separately in the
[execution record](2026-09-27-subscription-sync.md). No roadmap gate is closed.

## Question, call path and impact

Question: can all four configured OAI subscriptions be added to the independent
Open5GS database without changing existing subscriptions or copying live SQN?
No CodeGraph index exists in this repository. The optional maintenance path is
`sync-subscriptions.py → read-only MySQL query → subscriber.document → target
comparison → subscriber.insert_script → canonical EJSON readback`.

The operator explicitly requested all configured subscriptions, preserving target
records and using OCUDU's existing single-data policy. Static IMSI/K/OPc/AMF are
converted in Spark memory. Source SQN, IMS profiles, fixed addresses and runtime
registration/session contexts are not imported. Every conflicting existing static
credential blocks the batch before subscriber writes. Existing records, including
their SQN and policy, must remain byte-equivalent at the EJSON object level.

`deploy/maintenance/sync-subscriptions.py --check-source` is read-only and checks
source ownership, static material and access/data-profile presence. `--apply`
requires root, acquires the existing maintenance lock, validates the current
protected bundle, exact MongoDB image and existing volume, and refuses running
target services/containers or overlapping networks. It does not use the historical
empty-database provisioning entrypoint, which must not be used with this volume.

Before starting only MongoDB, it saves a private offline archive of the stopped
database volume, validates the gzip stream and archive inventory, and records
SHA-256. This is a full volume backup; restoration has not been exercised in this
round. Before insertion it also saves canonical subscription EJSON and a private
batch identity list. It refuses an unexpectedly empty target or a missing unique
IMSI index. Each insertion is acknowledged, and final checks compare every old
record and every new document. No update/upsert or automatic rollback runs.

The tool stops and removes only the MongoDB container it started, removes its
empty owned network, and retains the database volume. Errors preserve the private
backup/batch/result for inspection and must not be blindly retried. If a result is
uncertain, compare the recorded new identities with actual target contents before
deleting anything. A full volume restore requires the database to be stopped and
an explicit recovery decision; it must not overwrite subsequently advanced SQN.

Private outputs live below `/var/lib/aoc-maintenance/subscription-sync-<time>/`
with directory mode 0700 and file mode 0600. Database diagnostics and SIM material
are not printed or copied to the development host. The source database is queried
using read-only transactions only. No persistent cross-stack runtime dependency
or new sudo rule is introduced.

## BSON defect found and fixed

The first isolated real-MongoDB test found that the existing importer parsed EJSON
with default relaxed conversion: initial SQN zero was stored as BSON int32 despite
the document containing `$numberLong`. The importer now uses
`EJSON.parse(..., {relaxed: false})` and requires `_bsontype === 'Long'` at readback.
This changes newly inserted subscriptions only; it does not rewrite existing SQN.

## Validation and current boundary

- Twelve new unit tests cover preservation of existing SQN/policy, static conflicts,
  duplicate identities, unsupported profiles, typed readback, private backups,
  active-core refusal and withheld command diagnostics. Five existing subscriber
  tests also pass, including the strengthened BSON parsing/readback assertions.
- `make ci VENV=local/bootstrap-check` passed before the final BSON correction:
  256 passing tests, one existing macOS skip, both production frontend builds and
  repository audits. After that correction, all 146 root stack tests passed again.
  Local Python is 3.11.15, Node 24.14.0; this is not the native release matrix.
- On Spark Python 3.12.3 and the pinned MongoDB image, the corrected isolated
  `network=none` test passed: one existing synthetic record with int64 SQN 42,
  three new records, exact readback, original record unchanged, new SQN int64 zero,
  empty repeat plan and duplicate-insert refusal. It used tmpfs and synthetic
  credentials, never mounted the production volume, and removed its container.
- The staged tool's live `--check-source` reports four valid subscriptions and
  zero mutations. Source identifiers and secrets are withheld.

The reviewed two-file tool is staged on Spark at
`~/aoc-ops/subscription-sync-20260927/`. From an authenticated Spark terminal:

```sh
sudo /usr/bin/python3 -I "$HOME/aoc-ops/subscription-sync-20260927/sync-subscriptions.py" \
  --apply --expected-source-count 4
```

This command performs the authorized backup/import/database-only cleanup. It does
not switch radio platforms or start either Jetson. The current SSH accounts have
fixed lifecycle sudo grants but no noninteractive arbitrary sudo or database-import
grant, so the agent cannot execute it unattended. Do not transmit a sudo password
in chat. A successful result still requires separate device identity mapping,
platform switching and per-device/combined registration, PDU and user-plane checks.
The second Jetson's OCUDU controller is not installed; its control/management path
must be prepared separately before disruptive acceptance.
