# 独立监控平台

规划采用 Python 采集器/API、SQLite 历史存储和独立 Web 前端；具体框架在实现阶段确定。当前仅提供数据契约，没有可运行的 API 或页面。

## 数据来源与职责

| 层 | 来源 | 观测内容 |
| --- | --- | --- |
| Host | systemd、接口/进程信息 | 新栈生命周期、CPU、内存、B210 占用状态 |
| RAN | OCUDU JSON 指标及受控日志 | 小区、RNTI、吞吐、BLER、CQI、RRC/AMF 状态 |
| Core | 新栈 NF 状态、标准接口及必要的适配器 | 注册、会话、UPF 流量及来源可信度 |
| User plane | 新 ext-DN 内的受控探测 | 指定 UE 数据路径连通性与时延 |

后续 `backend/` 内设置 `collectors/ocudu`、`collectors/oai_core`、`collectors/host`、`domain`、`api`、`storage`，`frontend/` 通过本项目 API 展示。模块之间通过标准化 observation 交互，契约位于 `contracts/`。

初始 API 规划：`/api/v1/health`、`/api/v1/snapshot`、`/api/v1/history`。前端与 API 同源由 `127.0.0.1:8877` 提供；首阶段通过 SSH tunnel 访问，后续单独规划认证和发布。不覆盖现有 Tailscale Serve 的 443 根路径。

## 正确性与权限

原 Biverge 定制 SMF `/management/v1/pdu-sessions` 不是上游保证存在的接口，本模块不能以它为必需依赖。无法获取时输出 `unsupported`，采集失败为 `unavailable`，超时样本为 `stale`，均不能伪造为零或“无 UE”。UE 身份关联必须记录证据，RNTI/内部索引不能直接等同 SUPI 或 NGAP UE ID。

吞吐归一到 bit/s，累计计数与采样窗口计数分开。健康分解为进程、N2、注册、PDU、用户面，不把 gNB 进程存在等同 UE 已连通。N2 检查须匹配本栈 AMF 和 gNB 地址，不能仅查宿主机是否存在任意 38412 SCTP 连接。

采集器与 Web 分进程；Web 使用独立低权限用户，不能访问 Docker socket、SIM 密钥或直接调用 systemctl。需要权限的采集通过窄接口提供。OCUDU WebSocket 带控制能力，仅本地采集器可接入，不直接代理给浏览器。
