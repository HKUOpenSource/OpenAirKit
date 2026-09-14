# V2 P2-05 Open5GS 适配验收记录

日期：2026-09-12
任务：V2-P2-05

## 实现

- 以固定地址并发读取 AMF `/ue-info?page=-1`、`/gnb-info?page=-1`，SMF `/pdu-info?page=-1`，以及 AMF/SMF/UPF `/metrics`；单响应上限 1 MiB、请求超时 2 秒。
- 只保留注册/MM state、CM state、NGAP/gNB 数字标识、DNN `oai`、数据地址、S-NSSAI、PDU state、UE activity、QFI/5QI 和经过固定端点核验的 N3 地址对。
- SUPI 只在采集进程内作为 AMF/SMF 关联键，Web 输出稳定哈希和末四位。SUCI、PEI、GUTI、M-TMSI、TEID、PDR ID 和完整原始响应均不输出。
- 当前数据地址必须属于 `10.0.0.0/24`，否则保留会话但地址为空并标记 pool invalid；非 `oai` 上下文不进入 V2 数据模型。
- Prometheus 仅采集每个 NF 的固定 gauge 白名单；标签值和未列入白名单的 process/内部指标不发布。
- N2 保留独立 SCTP 证据并附 AMF gNB info；N3 同时有脱敏的活动会话端点证据和独立流量计数；N4 由 SMF/UPF 两端 PFCP peer gauge 交叉判断；N6 使用 UPF namespace 中的独立计数。
- 现场确认 V2 UPF tunnel 接口名为 `ogstun`，修正了早期 `tun0` 假设。计数规则只计数，policy accept，不添加 NAT、route 或 drop。

## 实机只读取证

- AMF infoAPI：一个 mm_state=registered、cm_state=connected 的当前 UE，NGAP/gNB 标识和一个 `oai` PDU 引用。
- SMF infoAPI：一个 active `oai` PDU，地址 `10.0.0.31`，S-NSSAI 1/ffffff，QFI 1、5QI 9，N3 端点为 `172.28.81.1:2152` 与 `172.28.81.14:2152`。
- AMF gNB infoAPI：setup_success=true、一个 gNB、一个 CM-connected UE。
- SMF 与 UPF metrics 均报告一个 PFCP peer；UPF 报告一个 session 和一个 `oai` QoS flow。

原始响应只用于本地字段核对，未写入仓库。Open5GS 官方 infoAPI 文档说明这些端点是当前 UE、gNB 和 PDU 会话的 JSON 视图，并与 Prometheus 使用同一 HTTP server：<https://open5gs.org/open5gs/docs/tutorial/07-infoAPI-UE-gNB-session-data/>。

## 自动验证

监测后端 29 项测试通过，覆盖真实结构解析、完整身份/TEID 脱敏、错误地址池、非数据 DNN、metrics 白名单、部分失败、N3/N6 方向和计数重置；前端 production build 与 `git diff --check` 通过。正式采集服务的流量方向与页面实机结果留待 P2-11。
