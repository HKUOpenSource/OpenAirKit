# Agentic-OCUDU

Agentic-OCUDU is a self-contained laboratory 5G system built with an OCUDU
radio access network, an Open5GS core network, and two independently released
operations applications.

| Application | Responsibility | Listener | Version |
| --- | --- | --- | --- |
| Jetson Console | Modem discovery, verified data sessions and bounded recovery | `127.0.0.1:8878` | 0.5.1 |
| Spark Platform | Host, radio and core observation with bounded stack operations | `127.0.0.1:8877` | 0.2.0 |

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
includes application and root stack tests. For Spark browser checks, build the
frontend, run `npm --prefix apps/spark-platform/frontend exec -- playwright install chromium`,
then `make e2e-spark`; it starts and stops its own synthetic loopback service.

The two applications have separate backends, frontends, dependency locks,
release packages and rollback paths. Installers leave services disabled at
boot and never operate the other application.

## Repository map

- `apps/jetson-console/`: Jetson API, device executor and web application.
- `apps/spark-platform/`: Spark collector, API and web application.
- `stacks/ocudu/`: radio build and runtime inputs.
- `stacks/open5gs/`: core network, subscriber and user-plane inputs.
- `deploy/`: platform-specific release, installation and rollback tools.
- `config/`: shared, versioned network and dependency contracts.
- `docs/`: current architecture, setup, operations and acceptance evidence.

Retired implementations and migration records are kept outside the current
source tree and are never included in builds or releases.

Start with the [documentation map](docs/README.md),
[architecture](docs/architecture.md), [contribution guide](CONTRIBUTING.md),
[security policy](SECURITY.md) and [release guide](docs/releasing.md).
