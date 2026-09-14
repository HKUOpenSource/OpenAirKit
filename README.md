# Agentic-OCUDU

Agentic-OCUDU is a self-contained laboratory 5G system built with an OCUDU
radio access network, an Open5GS core network, and two independently released
operations applications.

| Application | Responsibility | Listener | Version |
| --- | --- | --- | --- |
| Jetson Console | Modem discovery, verified data sessions, recovery and throughput tests | `127.0.0.1:8878` | 0.3.0 |
| Spark Platform | Host, radio and core observation with bounded stack operations | `127.0.0.1:8877` | 0.1.0 |

The current product scope is one 5G SA data network. A connected UE requires
fresh registration, an active PDU session in the configured pool, a current
RAN context and a verified user-plane path. IMS, SIP and voice services are
outside the current scope.

## Develop

```sh
make install-dev
make check
```

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
