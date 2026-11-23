# Spark and UE runtime alignment — 2026-11-23

[简体中文](2026-11-23-spark-ue-alignment.zh-CN.md)

## Scope and source

- Source baseline: `5ff2b244df05f60dea0c570b27a92dcd956f4fff` plus runtime
  alignment commit `a5965c7` on branch `fix/align-spark-ue-runtime`.
- Spark target: DGX Spark (ARM64, Ubuntu 24.04.5 LTS, kernel `7.0.0-1019-nvidia`,
  Python 3.12.3, Docker 29.6.2, USRP B210 over USB 3 SuperSpeed), running
  Open5GS 2.8.0 + MongoDB 8.0.30 alongside co-located inference services on
  `127.0.0.1:8000–8002`.
- UE target: Jetson Orin Nano (ARM64, Ubuntu 22.04.5 LTS, JetPack 6.2 / L4T,
  Python 3.10.12, Quectel RM520N-GL in `cdc_ether` ECM mode on USB interface `0a`
  with serial interfaces `00..03`).
- This record omits Tailnet addresses, SIM identifiers, credentials, B210
  serials and raw logs.

## Staged release artifacts

| Artifact | Release / ID | Archive / Manifest SHA-256 |
| --- | --- | --- |
| Spark Platform `0.2.1` | `599a67f4c4bfd503` | Archive `a0d309e53140c79251a2a24305be9f86aadfbc28bd1f7b86ce8b84a533dedb97` |
| Spark maintenance approval | `spark` | `fa3af457ea98078dd08173abad4f6d26ea395763111b60884f19150bdb73e415` |
| Jetson Console `0.6.2` | `18b45ddf1164a8ba` | Manifest `52a7702a7c33edeafcd55da32c2f13477ee2b5f943edc4aedbc112c6b87caef1`; archive `a5dd24472ba49016a01540d05010a90e6bb6158cac865f5efc84a5768dd34d5f` |
| Jetson maintenance approval | `jetson` | `a39a014fa4d8a6bee4f9a41f62ec243018813bd67406845d7eeab2e10a9bf764` |

Both packages were built as development alignment candidates prior to finalizing
git commits on the branch (`dirty=true` in staged release manifests).

## Implemented runtime alignment

1. **Open5GS MongoDB kernel compatibility (`stacks/open5gs/compose/render.py`)**:
   upstreamed `GLIBC_TUNABLES=glibc.pthread.rseq=1` on `mongo` for Linux 7.0+
   kernels alongside existing core tests.
2. **Spark stack RF tuning and CPU latency assets (`deploy/spark/stack/`)**:
   persisted `rx_gain=54` and `cell_cfg.pusch.max_ue_mcs=24` into `runtime.py`,
   added `libexec/aoc-v2-cpu-latency`, `systemd/aoc-v2-cpu-latency.service`,
   `cpu-latency.conf` and `realtime.conf.example`.
3. **Spark metrics port migration (`8001 -> 8879`)**: updated
   `apps/spark-platform/backend/aoc_spark/telemetry.py` and
   `scripts/spark/enable_radio_json_metrics.py` (`LEGACY_ENABLED` migration and
   `remove_guard()` stopping `aoc-v2-metrics-guard.service` before deleting the
   `nftables` table).
4. **Jetson ECM (`0a` + `00..03`) discovery & installer umask fixes**:
   added `("0a", ("00", "01", "02", "03")): "02"` to
   `apps/jetson-console/backend/aoc_jetson/hardware.py`, enforced `os.umask(0o022)`
   around `venv` creation/`pip install` and explicit `os.chmod(temporary, mode)`
   in `deploy/jetson/manage.py::private_write()`.

## Observed hardware deployment and verification

- **Spark host**:
  - Installed `/usr/local/sbin/aoc-maintain` and upgraded Spark Monitor to
    `599a67f4c4bfd503` without disturbing `aoc-v2-core.service`.
  - An initial attempt to replace live `/opt/agentic-ocudu/v2/runtime.py` with
    the repository's schema-3 file stopped at `AOC V2 ERROR: Unlisted release files`
    (live host retains schema-2 `units/` and backup directories) and
    automatically rolled back cleanly with zero core disruption.
  - Patched live `runtime.py` (`6aa11528...` -> `f1d7c2a2...`), removed ephemeral
    `/run/systemd/system/aoc-v2-radio.service.d/90-rx-gain-test.conf`, switched
    `aoc-v2-metrics-guard` to `127.0.0.1:8879`, passed `gnb --dryrun`, restarted
    `aoc-v2-radio.service` and `aoc-observe.service`, and kept `aoc-v2-core.service`
    and `8000–8002` listeners untouched.
  - Final read-only checks confirmed all 7 Spark units `active` (`NRestarts=0`),
    `127.0.0.1:8877/api/v1/health` returning `{"status":"ok","collector":"ok"}`,
    `127.0.0.1:8879` `LISTEN` + `ESTAB` WebSocket telemetry connection, AMF N2
    `setup_success: true`, and live UE traffic (`CQI 15`, `DL MCS 26–27`,
    `UL MCS 24`, `0% BLER`).
- **UE host (Jetson)**:
  - Disabled and stopped the conflicting legacy console unit (leaving its
    directory untouched for rollback), aligned `at_interface_number` to `"02"`,
    updated the maintenance approval, installed `18b45ddf1164a8ba`, and
    remediated the `umask 077` `venv`/`web.json`/`boot-ready.conf` directory
    permissions discovered during live startup.
  - Installed `/opt/agentic-ocudu/jetson/boot_connect.py`, passed read-only ECM
    AT/SIM/configuration/USB-speed queries, generated post-install
    `/etc/aoc-v2-jetson/boot.json`, installed `boot-ready.conf` +
    `aoc-v2-jetson-boot.service`, and enabled `web`, `device` and `boot` units.
  - Live `boot_connect.py ready`, `site_guard.py` (`ttyUSB2`), and
    `network_entry.py` passed; final checks confirmed both `aoc-v2-jetson-web`
    and `aoc-v2-jetson-device` `active (running)` (`NRestarts=0`),
    `127.0.0.1:8878/api/v1/health` returning `{"status":"ok","web":"ok","device":"ok"}`,
    and `aoc-maintain ue-status` reporting `quality="ok"`, `connected=true`,
    `registered=true`, `data_session_active=true`, `lab_policy_match=true`, and
    `management_protected=true` (`maintenance=false`, `recovery_paused=true`).

## Cold-reboot verification & gateway ICMP fix

- An initial unattended Jetson cold reboot exercised
  `aoc-v2-jetson-boot.service` (`boot_connect.py ready` then `connect`) with
  a cold-renamed USB ECM interface (`cdc_ether`, `480 Mbps`) and AT serial port.
  `readiness` (`28.5 s`), `identity_and_registration` (`32.6 s`,
  `configuration_differences: []`, `NR5G` registration in `~4.6 s`), and
  `standard_setup` job dispatch (`37.2 s`) succeeded, bringing up
  `aoc-v2-jetson-web`, `aoc-v2-jetson-device` (`NRestarts=0`), healthy
  `/api/v1/health`, default IPv4 cellular routing (metric `10` over Wi-Fi metric
  `30000`), and live Spark gNB scheduling (`CQI 15`, `DL MCS 27`, `UL MCS 24`,
  `PUSCH SINR ~30 dB`, `0%` BLER).
- Finding during `standard_setup`: `boot_connect.py` aborted with
  `ValueError: Management gateway unreachable` on a single dropped
  `ping -c 1 -W 2` reply while `NetworkManager` showed the management Wi-Fi and
  management tunnel continuously online. Direct gateway probing confirmed
  `66.7%` ICMP packet loss caused by campus Wi-Fi gateway ICMP rate-limiting.
- Fix implemented in `7e4b726`: `deploy/jetson/boot_connect.py` now retries a
  failed single-packet gateway probe with `ping -c 3 -i 1 -W 2`, caches
  positive gateway reachability for `15.0 s` (`GATEWAY_CACHE_SECONDS`) while
  retaining per-call `inspect_management` and `nmcli` checks, and clears the
  cache before `wait_ready`, pre-maintenance `connect`, and `Serial.select_once`.
  Unit coverage was added in `tests/test_jetson_boot.py` (`ManagementTests`).
- Follow-up unattended cold reboot after installing `boot_connect.py` from
  `7e4b726`: `aoc-v2-jetson-boot.service` completed end-to-end (`active (exited)`,
  `Result=success`, `NRestarts=0`), `/var/lib/aoc-v2-jetson-boot/public/status.json`
  reached `status="completed"`, `stage="complete"`, `job_state="complete"`,
  `maintenance_retained=false`, `cellular_default=true`,
  `management_verified=true`, `automatic_recovery_active=true`,
  `fresh_probe_sets=13`, `healthy_seconds=122.2`, `usb_speed_mbps="480"`,
  `configuration_differences=[]`, and `observed_network_mode=[["mode_pref","NR5G"]]`
  (timeline: `readiness` `28.3 s`, `identity_and_registration` `32.4 s`,
  `standard_setup` `37.0 s`, `bound_data_acceptance` `61.7 s`, `complete`
  `220.6 s`).
- Steady-state post-reboot checks passed on both hosts: Jetson `web` and
  `device` services remained `active (running)` (`NRestarts=0`),
  `127.0.0.1:8878/api/v1/health` returned `{"status":"ok","web":"ok","device":"ok"}`,
  and default IPv4 routing preferred the cold-renamed ECM cellular interface; on
  Spark, `127.0.0.1:8877/api/v1/health` returned `{"status":"ok","collector":"ok"}`,
  `aoc-v2-radio.service`, `aoc-v2-core.service`, and `aoc-v2-cpu-latency.service`
  remained `active`, and live OCUDU gNB logs showed active UE scheduling
  (`CQI 15`, `DL MCS 26–27`, `UL MCS 24`, `PUSCH SINR 29.0–30.6 dB`, `0%` BLER).

## Regression verification and deferred checks

- Verified on branch commit `a5965c7`: `test-frontend-behavior` (7/7),
  `test-jetson-backend` (109/109), `test-spark-backend` (72 ran, 1 Linux
  peer-cred skipped), `test-stack` (192/192), `typecheck`, `docs-audit`,
  `release-audit`, `license-audit`, and `shell-check` (loopback HTTP test in
  `test-stack` executed outside the network sandbox). Updated `boot_connect.py`
  (`7e4b726`) and `docs/` were subsequently re-verified with `test-jetson-boot`
  (22/22), `test-stack` (195/195), and all repository audit targets.
- Remaining roadmap gates: the unattended Jetson cold-reboot check is now
  complete; roadmap items `V2-P3-15`, `V2-P3-17`, `V2-P3-GATE`, and `V2-R06`
  remain open for their broader fault-matrix, multi-cycle start/stop, and
  post-migration ARM64 rollback acceptance criteria.
