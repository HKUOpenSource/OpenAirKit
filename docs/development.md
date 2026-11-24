# Developer Guide

[简体中文](development.zh-CN.md)

This guide covers local development environment setup, synthetic console
previews, test suites, browser verification, and repository audit gates for
**OpenAirKit**. For contribution policies and ownership boundaries, see
[Contributing](../CONTRIBUTING.md) and
[Architecture Decisions](adr/README.md).

## 1. Prerequisites and Environment Setup

Requires **Python `3.10–3.12`** and **Node.js `22`** (Jetson targets Python
`3.10`; Spark targets Python `3.12`; CI validates on Python `3.12`).

```sh
make install-dev BOOTSTRAP_PYTHON=python3.12
```

By default, Make targets look for a virtual environment at `.venv/`. To use a
custom path (for example `local/dev-venv`), pass `VENV=local/dev-venv` to both
`make install-dev` and subsequent Make targets:

```sh
make install-dev BOOTSTRAP_PYTHON=python3.12 VENV=local/dev-venv
make check VENV=local/dev-venv
```

`make install-dev` installs tool dependencies (`requirements-tools.txt`) and
both console development requirement sets, runs `npm ci`, and builds both React
frontends.

## 2. Local Preview and Frontend Development

Both web consoles run locally without physical USRP or 5G modem hardware:

- **Jetson Console (synthetic hardware)**: Uses `SimModem` and `SimNetwork`
  adapters inside [`apps/jetson-console/`](../apps/jetson-console) with backend
  loopback on `127.0.0.1:8878`. Vite dev mode (`npm --prefix
  apps/jetson-console/frontend run dev`) proxies `/api` requests to
  `http://127.0.0.1:8878`.
- **Spark Console (synthetic collector preview)**: Start an isolated local
  preview server on `127.0.0.1:8877` with switching disabled via
  [`scripts/monitor_preview.py`](../scripts/monitor_preview.py), or run Vite
  dev mode (`npm --prefix apps/spark-console/frontend run dev`) proxying `/api`
  to `http://127.0.0.1:8877`.
- **Shared UI primitives**: Shared Astryx Core, Charts, and Neutral theme
  configuration lives in
  [`packages/console-ui/README.md`](../packages/console-ui/README.md) with no
  platform business logic.

## 3. Test and Audit Matrix

| Command | Scope | Hardware Needed |
| --- | --- | --- |
| `make test-jetson-backend` | Jetson executor, API security headers/limits, config, network, and release rollback tests | No |
| `make test-spark-backend` | Spark telemetry collector, storage, Open5GS correlation, and control tests | No |
| `make test-stack` | OCUDU/Open5GS config validation, runtime orchestration, SIM provisioning, and release archive tests | No |
| `make test-frontend-behavior` | Node behavioral tests across both frontends (`behavior.mjs`) | No |
| `make typecheck` | Strict `tsc --noEmit` across both React frontends | No |
| `make docs-audit` | Paired EN/ZH docs, relative links, heading anchors, and public hygiene checks | No |
| `make release-audit` | Single-platform release boundary, lockfile, and systemd unit checks | No |
| `make license-audit` | Root `LICENSE`, `CITATION.cff`, `images.lock.json`, and private frontend manifest checks | No |
| `make version-audit` | Root [`VERSION`](../VERSION) sync across backends, npm manifests/locks, badges, `CITATION.cff`, and shared dependency pins | No |
| `make shell-check` | `bash -n` syntax validation across all `deploy/` and `scripts/` shell scripts | No |
| `make check` | Runs all fast checks against an already-prepared environment | No |
| `make ci` | Full CI sequence including frontend `npm ci` + production builds before tests and audits | No |

### Synthetic Browser End-to-End Suites

Install Chromium via Playwright inside each frontend directory and run:

```sh
make e2e-jetson
make e2e-spark
```

Both suites launch isolated loopback servers with synthetic state and never
touch physical hardware.

## 4. Regenerating Architecture Diagrams

SVG architecture and state diagrams in `docs/assets/diagrams/` (Light + Dark,
English + Simplified Chinese) are deterministically generated from
[`docs/assets/diagrams/generate.py`](assets/diagrams/generate.py). See
[Visual Assets Guide](assets/README.md) for diagram, hardware asset, and
screenshot redaction rules.

## 5. Offline Releases and AI-Assisted Navigation

- **Offline ARM64 archives**: Follow [Releasing](releasing.md) to build and
  verify single-platform `.tar.gz` bundles via `make build-jetson-release` and
  `make build-spark-release`.
- **CodeGraph navigation**: When a `.codegraph/` index is present locally,
  follow the [CodeGraph Workflow](coding-agent-codegraph.md) before editing
  shared contracts.
