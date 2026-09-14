# Spark troubleshooting

## Monitor unavailable

Check the three platform units and `127.0.0.1:8877`. A listener conflict stops
installation before the current release link changes. If SSE is disconnected
while health remains available, inspect collector freshness and authentication
expiry before restarting services.

## Radio start failure

Run `aoc-v2ctl status`, inspect the lifecycle record and radio journal, and
verify that no process owns the B210. Distinguish a failed unit from an active
process with no N2. Do not repeatedly restart a radio that failed its stability
window; preserve its log and invocation identifier.

## Core function unhealthy

Inspect only the named container and its dependencies. Record exit code, OOM
state and health reason. N2, N3, N4 and N6 are separate evidence domains; one
healthy interface cannot clear another failure.

## Device shown stale or disconnected

Compare current gNB process generation, RAN-context timestamp, core session and
PDU endpoint. A session reported before a gNB restart remains historical until
new correlation evidence arrives. A previous IP or throughput result cannot
mark it current.

## RF errors or low throughput

Compare underflow, overflow and late counts within the same gNB invocation.
Record RSRP, RSRQ, SINR, antenna configuration and a three-sample bound UE
benchmark. Change one radio, scheduler or runtime variable, keep a rollback,
and repeat under equivalent physical conditions.
