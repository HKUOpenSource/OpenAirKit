# Agentic-OCUDU

Agentic-OCUDU is a self-contained laboratory 5G system built with an OCUDU
radio access network, an Open5GS core network, and two independently released
operations applications.

| Application | Target Host & Runtime | Listener | Version |
| --- | --- | --- | --- |
| Jetson Console | Jetson ARM64, Ubuntu 22.04, Python 3.10, RM520N (RNDIS / ECM) | `127.0.0.1:8878` | 0.6.2 |
| Spark Platform | DGX Spark ARM64, Ubuntu 24.04, Python 3.12, B210 USB 3 | `127.0.0.1:8877` (`8879` gNB JSON metrics, root-only) | 0.2.1 |

Each application handles separate responsibilities:
- **Jetson Console**: Modem discovery, bounded AT/registration/PDU checks, owned failover routing, and bounded recovery.
- **Spark Platform**: Host, radio (`127.0.0.1:8879` loopback JSON metrics + `nftables` guard), and Open5GS core observation with bounded stack operations.

The current product scope is one 5G SA data network. A connected UE requires
fresh registration, an active PDU session in the configured pool, a current
RAN context and a verified user-plane path. IMS, SIP and voice services are
outside the current scope.

## Develop

Use Python 3.10–3.12 and Node.js 22. The device targets are Python 3.10 for
Jetson and Python 3.12 for Spark; CI tests both. Bootstrap creates `.venv`,
installs both backend development dependencies, runs `npm ci` and builds both UIs.

```sh
make install-dev BOOTSTRAP_PYTHON=python3.12
make check
```

An existing environment is never replaced. If `.venv` uses an older Python,
select a fresh path with `VENV=local/dev-venv` on both commands. `make check`
includes frontend behavior tests, TypeScript checks, application and root stack
tests, and repository audits (`docs-audit`, `release-audit`, `license-audit`,
`shell-check`). For Spark browser checks, build the frontend, run
`npm --prefix apps/spark-platform/frontend exec -- playwright install chromium`,
then `make e2e-spark`; it starts and stops its own synthetic loopback service.
When `.codegraph/` is present at the repository root, follow the
[CodeGraph workflow](docs/coding-agent-codegraph.md) before searching or reading source.

The two applications have separate backends, frontends, dependency locks,
release packages and rollback paths. Installers leave services disabled at
boot and never operate the other application.

## Repository map

- `apps/jetson-console/`: Jetson API, device executor and React web application.
- `apps/spark-platform/`: Spark collector, API and React web application.
- `packages/console-ui/`: Shared Astryx Core, Charts and Neutral theme components (`@aoc/console-ui`).
- `stacks/ocudu/`: radio build and runtime inputs.
- `stacks/open5gs/`: core network, subscriber and user-plane inputs.
- `deploy/`: platform installers, stack lifecycle, restricted maintenance (`aoc-maintain`) and optional Jetson boot coordinator (`boot_connect.py`).
- `scripts/`: release builders, Spark metrics guard transaction (`enable_radio_json_metrics.py`) and CI audits.
- `config/`: shared, versioned network and dependency contracts.
- `docs/`: current architecture, setup, operations and acceptance evidence.

Retired implementations and migration records are kept outside the current
source tree and are never included in builds or releases.

Start with the [documentation map](docs/README.md),
[architecture](docs/architecture.md), [contribution guide](CONTRIBUTING.md),
[security policy](SECURITY.md) and [release guide](docs/releasing.md).
