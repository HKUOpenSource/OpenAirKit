# V2 P2-02 观测契约验收记录

日期：2026-09-12
任务：V2-P2-02
范围：本地契约、状态归一和测试；未安装或操作现网。

## 契约

- Spark 快照升级为 `schema_version=4`，固定为单一 `ocudu` 环境。
- 单项 metric observation 升级为 v2，要求来源、实体、名称、值、单位、证据时间、采样窗口、质量和原因。
- 证据质量固定为 `ok/stale/unavailable/unsupported`；非 `ok` 质量必须有原因。
- 组件及设备业务状态独立于证据质量。`healthy/degraded/failed/inactive/unknown` 不能写入 metric 的质量字段。
- 设备 connection 固定分层为 `registration`、`radio`、`data_pdu`。PDU 报告或地址不会将设备提升为“数据可达”；注册也不会证明 RRC 或用户面；RRC idle 保留为无线状态，不判为掉网。
- 快照过期时，当前状态失效为 unknown/stale，历史注册只保留在 `last_registration`，不继续显示成当前在线。

契约文件：

- `apps/spark-platform/contracts/observation.schema.json`
- `apps/spark-platform/contracts/snapshot.schema.json`

## 验证

- 两份 JSON Schema 均通过 JSON 语法检查。
- 监测后端 21 项测试通过，包含非法质量拒绝、非 `ok` 原因补齐、注册/PDU/地址不能证明数据可达、RRC idle 不等于断网、样本过期和计数重置。
- React + TypeScript production build 通过。

Open5GS 会话来源、OCUDU 扩展字段和用户面真实数据仍由 P2-04/P2-05 接入；本任务只锁定这些数据进入平台后的表达规则。
