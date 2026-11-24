# REST and SSE API Reference

[简体中文](api-reference.zh-CN.md)

This reference lists the verified HTTP and Server-Sent Events (SSE) endpoints
for **Spark Platform** and **Jetson Console**. Both services bind to loopback
only (`127.0.0.1`) and share the same session cookie + CSRF model for custom
integrations and DIY AI clients.

## Authentication & Session Model

1. Obtain a session cookie and CSRF token from the login endpoint (`/api/v1/login` on Spark, `/api/v1/auth/login` on Jetson).
2. Include the session cookie on all authenticated `GET` and SSE requests.
3. Include both the session cookie and CSRF header on all mutating `POST` requests.
4. Monitor SSE streams for `auth_expired` events and re-authenticate cleanly when sessions expire.

---

## Spark Platform API (`127.0.0.1:8877`)

### Health & Authentication

| Endpoint | Method | Auth | Purpose |
| --- | --- | --- | --- |
| `/api/v1/health` | `GET` | Public | Web & collector liveness check |
| `/api/v1/login` | `POST` | Public | Exchange password for HttpOnly session cookie + CSRF token |
| `/api/v1/session` | `GET` | Session | Inspect current authentication state and CSRF token |
| `/api/v1/logout` | `POST` | Session + CSRF | Invalidate current session |

### Observation, Telemetry & Diagnostics

| Endpoint | Method | Auth | Purpose |
| --- | --- | --- | --- |
| `/api/v1/snapshot` | `GET` | Session | Latest unified snapshot across host, B210, OCUDU gNB, N2, Open5GS NFs, bridge counters, and UEs |
| `/api/v1/stream` | `GET` | Session | Persistent SSE live update stream |
| `/api/v1/devices` | `GET` | Session | List correlated UE contexts and active PDU sessions |
| `/api/v1/devices/{identifier}` | `GET` | Session | Per-UE detail view |
| `/api/v1/devices/{identifier}/metrics` | `GET` | Session | Time-series KPIs for one UE |
| `/api/v1/components/{identifier}/metrics` | `GET` | Session | Time-series KPIs for one platform/RAN/core component |
| `/api/v1/history` | `GET` | Session | Historical time-series telemetry query |
| `/api/v1/history/catalog` | `GET` | Session | Indexed metric names available for history queries |
| `/api/v1/events` | `GET` | Session | Filterable subsystem events timeline |
| `/api/v1/events/kinds` | `GET` | Session | Supported event categories |
| `/api/v1/diagnostics` | `GET` | Session | Collector health, timestamps, and subsystem diagnostics |

### Bounded Operations & Audit

| Endpoint | Method | Auth | Purpose |
| --- | --- | --- | --- |
| `/api/v1/control` | `GET` | Session | List recent and active stack control tasks |
| `/api/v1/control/{identifier}` | `GET` | Session | Poll status/steps of a specific control task |
| `/api/v1/control` | `POST` | Session + CSRF | Start a bounded allow-listed stack/service operation |
| `/api/v1/control/{identifier}/cancel` | `POST` | Session + CSRF | Request cancellation of an active control task |
| `/api/v1/audit` | `GET` | Session | Read persistent control and login audit trail |

---

## Jetson Console API (`127.0.0.1:8878`)

### Health & Authentication

| Endpoint | Method | Auth | Purpose |
| --- | --- | --- | --- |
| `/api/v1/health` | `GET` | Public | Web & device executor liveness check |
| `/api/v1/auth/login` | `POST` | Public | Exchange console password for HttpOnly session cookie + CSRF token |
| `/api/v1/auth/session` | `GET` | Session | Inspect current authentication state and CSRF token |
| `/api/v1/auth/logout` | `POST` | Session + CSRF | Invalidate current session |

### Observation, Telemetry & Diagnostics

| Endpoint | Method | Auth | Purpose |
| --- | --- | --- | --- |
| `/api/v1/status` | `GET` | Session | Full UE snapshot (SIM, cell, NR SA registration, IPv4 PDU, interface, bound probes, routing, recovery, evidence quality) |
| `/api/v1/config` | `GET` | Session | Sanitized active UE configuration (without SIM secrets) |
| `/api/v1/events/stream` | `GET` | Session | Persistent SSE state and job update stream |
| `/api/v1/metrics` | `GET` | Session | Passive interface RX/TX counters and probe latencies (`hours` window) |
| `/api/v1/history` | `GET` | Session | Past Setup and Recover job records |
| `/api/v1/diagnostics` | `GET` | Session | Redacted modem and interface diagnostics |

### Bounded Device Workflows & Maintenance

| Endpoint | Method | Auth | Purpose |
| --- | --- | --- | --- |
| `/api/v1/jobs` | `GET` | Session | List prepared, running, and completed device jobs |
| `/api/v1/jobs/{identifier}` | `GET` | Session | Inspect one job's plan and step outcomes |
| `/api/v1/jobs` | `POST` | Session + CSRF | Prepare a Setup or Recover plan (previews changes before execution) |
| `/api/v1/jobs/{identifier}/run` | `POST` | Session + CSRF | Execute a prepared job |
| `/api/v1/jobs/{identifier}/cancel` | `POST` | Session + CSRF | Request bounded cancellation of an active job |
| `/api/v1/maintenance` | `POST` | Session + CSRF | Toggle maintenance mode (releases AT serial lock and switches to Wi-Fi fallback) |
