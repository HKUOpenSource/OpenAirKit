# Changelog

All notable changes to OpenAirKit are recorded here. This project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.1.0] - 2026-11-27

### Added

- Added platform-separated host `sysctl` throughput profiles: `deploy/spark/stack/sysctl/99-aoc-v2-throughput.conf` (`bbr` + `fq` + `16 MiB` socket buffers for Spark Linux `7.0+`) and `deploy/jetson/sysctl/99-aoc-v2-jetson-throughput.conf` (`16 MiB` socket buffers, `tcp_window_scaling=1`, and `tcp_mtu_probing=1` for Jetson L4T `5.15`).
- Added bidirectional `nftables` TCP MSS clamping (`1400`) in `table ip aoc_v2` (`forward` mangle chain) inside `stacks/open5gs/compose/runtime.py` and automatic cellular interface MTU alignment (`align_cellular_mtu()`, capping `<= 1440`) inside `apps/jetson-console/backend/aoc_jetson/network.py`.
- Documented Quectel RM520N-GL `AT+QCFG="usbspeed","311"` USB 3.0 recovery and host `sysctl` throughput profiles in [Hardware & Modem Notes](docs/reference/hardware-notes.md) ([简体中文](docs/reference/hardware-notes.zh-CN.md)), formalized **Semantic Versioning 2.0.0** and release conventions in [Releasing](docs/releasing.md), and archived hardware-verified `40 MHz` benchmarks (`112–119 Mbps` DL / `50.7 Mbps` UL N6 `iperf3`; `107.6 / 32.17 Mbps` browser Speedtest) in [40 MHz Throughput Acceptance](docs/acceptance/2026-11-27-40mhz-throughput-tuning.md).

### Changed

- Upgraded the 5G SA n78 (`1T1R`) RF baseline from `20 MHz` (`7 DL / 2 UL`, `23.04` MSps, `sc12`, `64/64` UHD frames, `pusch.max_ue_mcs=24`) to **`40 MHz`** (`106` PRBs, `6 DL / 3 UL` TDD, `srate=46.08` MSps, `otw_format=sc16`, `256/256` UHD frames, `pdsch`/`pusch` `qam256`, `pusch.max_ue_mcs=27`) across `deploy/spark/stack/runtime.py`, `config/network-contract.json`, `config/network-profile.example.json`, `config/jetson.example.json`, `stacks/open5gs/config.py`, and `scripts/aoclib/radio.py`.
- Aligned Open5GS SMF and UPF `ogstun` PDU MTU from `1400` to `1440` (`stacks/open5gs/compose/render.py`, `stacks/open5gs/compose/runtime.py`), synchronized `RUNTIME_SHA` in `deploy/maintenance/repair-connectivity-manifest.py`, and raised default subscriber Session AMBR from `100/200 Mbps` to `500/1000 Mbps` (`stacks/open5gs/subscriber.py`, `scripts/aoclib/core.py`, `scripts/aoclib/subscriber.py`).
- Synchronized unified platform version `1.1.0` across `VERSION`, both console backends and frontends, `packages/console-ui`, badges, and release documentation.

### Fixed

- Eliminated public-egress PMTUD black-hole stalls (`Socket Error` during browser Speedtest) caused by newly enumerated USB cellular interfaces defaulting to `MTU 1500` against the `1440`-byte 5G PDU path.
- Eliminated downlink CUBIC bufferbloat (`3.13 MB` cwnd inflation and `934` burst retransmits) on the 5G SA path by switching Spark to `bbr` + `fq` and expanding host socket buffers to `16 MiB`.

### Compatibility

- Console REST/SSE APIs, authentication, `device.json` / SQLite schemas, systemd units, `aoc-v2ctl` / `aoc-maintain` CLIs, single `IPv4` `oai` PDU semantics, and existing USIM/SQN state remain backward-compatible; `stacks/open5gs/config.py::load()` now validates the `40 MHz / 6D1S3U` network profile baseline.

## [1.0.0] - 2026-11-24

### Added

- Unified Spark Console and Jetson Console under platform version `1.0.0` (`VERSION`) with automated version and shared-dependency parity enforcement (`scripts/audit/version_audit.py` wired into `make check` and `make ci`).
- Added Apache License 2.0 (`LICENSE`), Architecture Decision Records (`docs/adr/`), paired Developer Guides (`docs/development.md`), expanded `SECURITY.md`, and structured GitHub issue templates.
- Added paired English and Simplified Chinese onboarding guides: [Hardware & Topology](docs/hardware-and-topology.md), [End-to-End Quickstart](docs/quickstart.md), [DIY AI Customization](docs/ai-customization.md), and [Visual Assets & Brand Guide](docs/assets/README.md).
- Added Quectel RM520N-GL ECM (`cdc_ether` on `bInterfaceNumber=0a` -> AT `02`) support in `aoc_jetson.hardware.discover()`.
- Completed development bootstrap, unified stack/release unit suites in `make ci`, Linux ARM64 offline release archives with target-specific wheel validation, and automated repository boundary audits (`docs-audit`, `release-audit`, `license-audit`, `shell-check`).

### Changed

- Renamed the Spark Console application directory from `apps/spark-platform` to `apps/spark-console` across workflows, build scripts, audits, and documentation.
- Documented the **Waveshare SIM8262E-M2 5G for Jetson Orin** M.2 carrier board mounting the **Quectel RM520N-GL** module, Open5GS container build inputs, interactive Web Console password setup, and `tailscale0` management routing checks.
- Replaced ASCII architecture diagrams with layered Mermaid topology, swimlane deployment, and routing/recovery state diagrams; retired site-migration coexistence helpers to `archive/` and consolidated release boundary rules into [Releasing](docs/releasing.md).
- Hardened Spark runtime defaults (`GLIBC_TUNABLES=glibc.pthread.rseq=1` on Open5GS MongoDB Compose, `rx_gain=54`, `cell_cfg.pusch.max_ue_mcs=24`, `aoc-v2-cpu-latency` helpers/drop-ins) and moved OCUDU loopback JSON metrics and `aoc-v2-metrics-guard` from `127.0.0.1:8001` to `127.0.0.1:8879` so `127.0.0.1:8000–8002` stay free for co-located inference services.
- Verified Spark `0.2.1` + Jetson `0.6.2` multi-UE hardware alignment (including opt-in `boot_connect.py` cold-boot self-recovery).

### Fixed

- Hardened the Jetson Console HTTP API with `TrustedHostMiddleware`, `Content-Length` enforcement (`<= 8192` bytes), `X-Frame-Options: DENY`, and `access_log=False`, fixed the Jetson Vite dev proxy port to `8878`, aligned Spark frontend timestamps to browser local timezone, and removed unreachable legacy radio config parsing.
- Hardened `umask 077` permissions during `venv` and `web.json` creation.

## Jetson 0.6.2

- Automatically prefer verified cellular IPv4 after two fresh successful probe samples, and fall back to Wi-Fi on failures or expired evidence independently of modem recovery permission.
- Journal and restore only owned default routes, rebuild owned probe routes after USB enumeration changes, and report ordinary IPv4 egress separately from probe routing.
- Preserve administrator routes and NetworkManager profiles; Wi-Fi fallback does not guarantee independent tunnel transport.

## Jetson Console 0.6.1 / Spark Platform 0.2.1

- Fixed task cancellation cleanup, concurrent task persistence, structured diagnostics redaction, and idle-UE throughput aggregation.
- Verified ARM64 patch upgrades, previous-version rollback/reinstallation, and live multi-UE data connectivity while preserving independent stack boundaries.
- Updated Spark stack lifecycle packaging, private candidate verification, and browser navigation checks for the eight-page Spark Console.

## Jetson Console 0.6.0

- Corrected local-state filters, persistent operation feedback, and retained-history access in both Astryx consoles.
- Restored saved Jetson systemd unit files on rollback and reloaded systemd before starting the rolled-back web service.
- Indexed retained Spark metric names (schema 6), kept authenticated SSE live streams persistent across updates, and required N2 NG Setup in full-stack startup.
- Added bounded `CFUN=1` power restoration after uncertain `CFUN=0` outcomes and kernel-cgroup listener verification on port `8877`.

## Jetson Console 0.5.1

- Kept authenticated status streams open with per-update session checks and bounded graceful shutdown.
- Parallelized independent read-only network probes to lower status latency without relaxing freshness limits.

## Jetson Console 0.5.0 / Spark Platform 0.2.0

- Standardized both consoles on Astryx Core, Neutral theme, and Charts (`packages/console-ui/`) with responsive navigation and evidence-aware charts.
- Preserved third-party frontend license notices (`THIRD_PARTY_NOTICES.txt`) in built release artifacts.

## Jetson 0.4.0

- Separated network access expectations, `observe_only` lab selection, and diagnostic probes into schema 3 configuration with schema-2 migration backups.
- Retired active throughput benchmarks and added bounded natural-wait + cooldown automatic modem recovery.
- Added role-specific passwordless maintenance (`aoc-maintain`) with SHA-256 payload verification and atomic restoration on activation failure.

## Jetson Console 0.3.0

- Added independent Jetson Console (`127.0.0.1:8878`) with bounded modem/routing helpers, evidence-verified data status, and task persistence.

## Spark Platform 0.1.0

- Added independent Spark Platform (`127.0.0.1:8877`) with OCUDU and Open5GS collectors, evidence-quality semantics, history, events, and bounded operations.

[Unreleased]: https://github.com/HKUOpenSource/OpenAirKit/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/HKUOpenSource/OpenAirKit/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/HKUOpenSource/OpenAirKit/releases/tag/v1.0.0
