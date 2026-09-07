# RAN 配置生成约定

输入以 `config/spark.example.json` 的环境结构为准，实际站点配置放在未跟踪的 `local/`，输出写入发布目录及 `/etc/agentic-ocudu/ocudu/`。当前不提供可直接发射的 gNB YAML。

| 输入 | OCUDU 26.04 目标配置 |
| --- | --- |
| `network.addresses.amf` | `cu_cp.amf.addrs` |
| `network.addresses.gnb` | `cu_cp.amf.bind_addrs` 和 `cu_up.ngu.socket[].bind_addr` |
| PLMN / TAC / SST | AMF supported tracking areas 与 cell 配置一致 |
| B210 序列号 | UHD device args，明确选择设备 |
| 射频参数 | `ru_sdr`、`cell_cfg`，必须现场确认 |

必须补齐 `radio.serial`、`dl_arfcn`、增益、TDD、cell identity 和订阅匹配。OAI 的 SSB ARFCN `643392` 不能直接当作 OCUDU 的 `dl_arfcn`；OAI attenuation 也不能直接当作 UHD gain。

JSON 指标需要评估 OCUDU `remote_control` WebSocket。该端口同时包含控制命令，默认不开启；启用时仅绑定 `127.0.0.1:8001`，不得通过网页代理或 Tailscale 直接暴露。
