# RAN Configuration Generation

Site-specific deployment configuration lives outside Git in protected runtime
storage rather than checked-in radio YAML files. `deploy/spark/stack/runtime.py`
renders the OCUDU gNB configuration from `config/network-contract.json` and the
target deployment inputs:

| Deployment Input | OCUDU gNB Target Field |
| --- | --- |
| Core AMF address | `cu_cp.amf.addrs` |
| Local gNB N2/N3 bind address | `cu_cp.amf.bind_addrs`, `cu_up.ngu.socket[].bind_addr` |
| PLMN / TAC / SST | `cu_cp.amf.supported_tracking_areas` and cell identity fields |
| USRP B210 serial | UHD `device_args` |
| RF & TDD parameters | `ru_sdr` and `cell_cfg` |

Verify `radio.serial`, `dl_arfcn`, gain settings, TDD pattern, cell identity,
and Open5GS subscriber alignment against [Network & RF Profile](../../../docs/reference/network-and-rf-profile.md)
before field operation.

When OCUDU `remote_control` JSON telemetry is enabled via
`scripts/spark/enable_radio_json_metrics.py`, it binds strictly to loopback
`127.0.0.1:8879` behind the root-only `aoc-v2-metrics-guard.service` firewall
and is never exposed externally.
