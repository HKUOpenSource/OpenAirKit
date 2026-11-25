# Changelog

## 1.0.0 (2026-11-24)

- Unified Spark Console and Jetson Console under platform version `1.0.0` (`VERSION`) with automated version and shared-dependency parity enforcement (`scripts/audit/version_audit.py` wired into `make check` and `make ci`).
- Renamed the Spark Console application directory from `apps/spark-platform` to `apps/spark-console` across workflows, build scripts, audits, and documentation.
- Hardened the Jetson Console HTTP API with `TrustedHostMiddleware`, `Content-Length` enforcement (`<= 8192` bytes), `X-Frame-Options: DENY`, and `access_log=False`, fixed the Jetson Vite dev proxy port to `8878`, aligned Spark frontend timestamps to browser local timezone, and removed unreachable legacy radio config parsing.
- Added Apache License 2.0 (`LICENSE`), Architecture Decision Records (`docs/adr/`), paired Developer Guides (`docs/development.md`), expanded `SECURITY.md`, and structured GitHub issue templates.
- Updated repository documentation, hardware illustrations, and release verification:
  - Added paired English and Simplified Chinese onboarding guides: [Hardware & Topology](docs/hardware-and-topology.md), [End-to-End Quickstart](docs/quickstart.md), [DIY AI Customization](docs/ai-customization.md), and [Visual Assets & Brand Guide](docs/assets/README.md).
  - Documented the **Waveshare SIM8262E-M2 5G for Jetson Orin** M.2 carrier board mounting the **Quectel RM520N-GL** module, Open5GS container build inputs, interactive Web Console password setup, and `tailscale0` management routing checks.
  - Replaced ASCII architecture diagrams with layered Mermaid topology, swimlane deployment, and routing/recovery state diagrams; retired site-migration coexistence helpers to `archive/` and consolidated release boundary rules into [Releasing](docs/releasing.md).
- Hardened Spark runtime defaults (`GLIBC_TUNABLES=glibc.pthread.rseq=1` on Open5GS MongoDB Compose, `rx_gain=54`, `cell_cfg.pusch.max_ue_mcs=24`, `aoc-v2-cpu-latency` helpers/drop-ins) and moved OCUDU loopback JSON metrics and `aoc-v2-metrics-guard` from `127.0.0.1:8001` to `127.0.0.1:8879` so `127.0.0.1:8000–8002` stay free for co-located inference services.
- Added Quectel RM520N-GL ECM (`cdc_ether` on `bInterfaceNumber=0a` -> AT `02`) support in `aoc_jetson.hardware.discover()`, hardened `umask 077` permissions during `venv` and `web.json` creation, and verified Spark `0.2.1` + Jetson `0.6.2` multi-UE hardware alignment (including opt-in `boot_connect.py` cold-boot self-recovery).
- Completed development bootstrap, unified stack/release unit suites in `make ci`, Linux ARM64 offline release archives with target-specific wheel validation, and automated repository boundary audits (`docs-audit`, `release-audit`, `license-audit`, `shell-check`).

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
