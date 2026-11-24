# REST and SSE API Reference

[简体中文](api-reference.zh-CN.md)

This reference specifies the supported HTTP and Server-Sent Events (SSE)
endpoints for **Spark Console** and **Jetson Console**. Both services bind
exclusively to loopback (`127.0.0.1`) and enforce a shared session-cookie +
CSRF security model for Web UI clients, automation scripts, and external AI
clients.

## Authentication & Session Model

1. Obtain an HttpOnly session cookie and CSRF token from the login endpoint (`/api/v1/login` on Spark, `/api/v1/auth/login` on Jetson).
2. Attach the session cookie to all authenticated `GET` and SSE requests.
3. Attach both the session cookie and CSRF header to all state-mutating `POST` requests.
4. Watch SSE streams for `auth_expired` events and re-authenticate cleanly upon session expiration.

---

## Spark Console API (`127.0.0.1:8877`)

### Health & Authentication

| Endpoint | Method | Auth | Purpose |
| --- | --- | --- | --- |
| `/api/v1/health` | `GET` | Public | Web & telemetry collector liveness check |
| `/api/v1/login` | `POST` | Public | Exchange console password for HttpOnly session cookie + CSRF token |
| `/api/v1/session` | `GET` | Session | Inspect active authentication state and CSRF token |
| `/api/v1/logout` | `POST` | Session + CSRF | Invalidate active session |

### Observation, Telemetry & Diagnostics

| Endpoint | Method | Auth | Purpose |
| --- | --- | --- | --- |
| `/api/v1/snapshot` | `GET` | Session | Unified snapshot spanning host, B210, OCUDU gNB, N2, Open5GS NFs, bridge counters, and UEs |
| `/api/v1/stream` | `GET` | Session | Persistent SSE telemetry stream |
| `/api/v1/devices` | `GET` | Session | List correlated UE RNTI contexts and active PDU sessions |
| `/api/v1/devices/{identifier}` | `GET` | Session | Per-UE detail view |
| `/api/v1/devices/{identifier}/metrics` | `GET` | Session | Time-series KPIs for one UE |
| `/api/v1/components/{identifier}/metrics` | `GET` | Session | Time-series KPIs for one platform/RAN/core component |
| `/api/v1/history` | `GET` | Session | Historical time-series telemetry query |
| `/api/v1/history/catalog` | `GET` | Session | Indexed metric catalog available for history queries |
| `/api/v1/events` | `GET` | Session | Filterable subsystem event timeline |
| `/api/v1/events/kinds` | `GET` | Session | Supported event categories |
| `/api/v1/diagnostics` | `GET` | Session | Collector health, timestamps, and subsystem diagnostics |

### Bounded Operations & Audit

| Endpoint | Method | Auth | Purpose |
| --- | --- | --- | --- |
| `/api/v1/control` | `GET` | Session | List recent and in-flight stack control tasks |
| `/api/v1/control/{identifier}` | `GET` | Session | Poll execution steps and state of a control task |
| `/api/v1/control` | `POST` | Session + CSRF | Dispatch a bounded allow-listed stack/service operation |
| `/api/v1/control/{identifier}/cancel` | `POST` | Session + CSRF | Request cancellation of an active control task |
| `/api/v1/audit` | `GET` | Session | Read persistent control and authentication audit log |

---

## Jetson Console API (`127.0.0.1:8878`)

### Health & Authentication

| Endpoint | Method | Auth | Purpose |
| --- | --- | --- | --- |
| `/api/v1/health` | `GET` | Public | Web & device executor liveness check |
| `/api/v1/auth/login` | `POST` | Public | Exchange console password for HttpOnly session cookie + CSRF token |
| `/api/v1/auth/session` | `GET` | Session | Inspect active authentication state and CSRF token |
| `/api/v1/auth/logout` | `POST` | Session + CSRF | Invalidate active session |

### Observation, Telemetry & Diagnostics

| Endpoint | Method | Auth | Purpose |
| --- | --- | --- | --- |
| `/api/v1/status` | `GET` | Session | Full UE snapshot (USIM, cell, NR SA registration, IPv4 PDU, interface, bound probes, routing, recovery, telemetry freshness) |
| `/api/v1/config` | `GET` | Session | Redacted active UE configuration (excluding USIM keys) |
| `/api/v1/events/stream` | `GET` | Session | Persistent SSE state and job progress stream |
| `/api/v1/metrics` | `GET` | Session | Passive interface RX/TX counters and probe latencies (`hours` window) |
| `/api/v1/history` | `GET` | Session | Historical Setup and Recover job records |
| `/api/v1/diagnostics` | `GET` | Session | Redacted modem and interface diagnostics |

### Bounded Device Workflows & Maintenance

| Endpoint | Method | Auth | Purpose |
| --- | --- | --- | --- |
| `/api/v1/jobs` | `GET` | Session | List prepared, active, and completed device jobs |
| `/api/v1/jobs/{identifier}` | `GET` | Session | Inspect one job's change plan and step results |
| `/api/v1/jobs` | `POST` | Session + CSRF | Prepare a Setup or Recover plan (previews changes prior to execution) |
| `/api/v1/jobs/{identifier}/run` | `POST` | Session + CSRF | Execute a prepared device job |
| `/api/v1/jobs/{identifier}/cancel` | `POST` | Session + CSRF | Request bounded cancellation of an active job |
| `/api/v1/maintenance` | `POST` | Session + CSRF | Toggle maintenance mode (releases AT serial lock and activates Wi-Fi fallback route) |
