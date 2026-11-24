# REST 与 SSE 接口参考

[English](api-reference.md)

本文档汇总 **Spark Console** 与 **Jetson Console** 开放的 HTTP 及 Server-Sent Events
（SSE）接口规范。两端接口均严格绑定本地回环地址（`127.0.0.1`），并采用统一的
Session Cookie + CSRF 鉴权模型，供运维面板、自动化脚本及外部 AI 客户端集成调用。

## 鉴权与会话模型

1. 调用登录接口（Spark 为 `/api/v1/login`，Jetson 为 `/api/v1/auth/login`）获取 HttpOnly 会话 Cookie 与 CSRF Token。
2. 所有已鉴权 `GET` 查询与 SSE 订阅连接均须携带会话 Cookie。
3. 所有状态变更类 `POST` 请求须同时携带会话 Cookie 与 CSRF 请求头。
4. 客户端应订阅 SSE 流中的 `auth_expired` 事件，并在会话失效时自动重新鉴权。

---

## Spark Console 接口（`127.0.0.1:8877`）

### 健康检查与鉴权

| 接口端点 | 方法 | 鉴权 | 用途说明 |
| --- | --- | --- | --- |
| `/api/v1/health` | `GET` | 公开 | Web 与遥测采集器存活检查 |
| `/api/v1/login` | `POST` | 公开 | 使用控制台密码换取会话 Cookie 与 CSRF Token |
| `/api/v1/session` | `GET` | Session | 查询当前登录状态与 CSRF Token |
| `/api/v1/logout` | `POST` | Session + CSRF | 注销当前会话 |

### 实时状态、历史指标与诊断

| 接口端点 | 方法 | 鉴权 | 用途说明 |
| --- | --- | --- | --- |
| `/api/v1/snapshot` | `GET` | Session | 获取主机、B210、OCUDU gNB、N2、Open5GS 网元、网桥与 UE 统一快照 |
| `/api/v1/stream` | `GET` | Session | 持久 SSE 实时推送流 |
| `/api/v1/devices` | `GET` | Session | 列出已关联 UE RNTI 上下文与活动 PDU 会话 |
| `/api/v1/devices/{identifier}` | `GET` | Session | 单台 UE 详情视图 |
| `/api/v1/devices/{identifier}/metrics` | `GET` | Session | 单台 UE 的时序 KPI |
| `/api/v1/components/{identifier}/metrics` | `GET` | Session | 单组件的时序 KPI |
| `/api/v1/history` | `GET` | Session | 历史时序指标查询 |
| `/api/v1/history/catalog` | `GET` | Session | 可查询的历史指标目录 |
| `/api/v1/events` | `GET` | Session | 可筛选子系统事件流 |
| `/api/v1/events/kinds` | `GET` | Session | 支持的事件类别列表 |
| `/api/v1/diagnostics` | `GET` | Session | 采集时间戳与各子系统诊断详情 |

### 受限运维操作与审计

| 接口端点 | 方法 | 鉴权 | 用途说明 |
| --- | --- | --- | --- |
| `/api/v1/control` | `GET` | Session | 列出近期与执行中的控制任务 |
| `/api/v1/control/{identifier}` | `GET` | Session | 查询单个控制任务的执行步骤与状态 |
| `/api/v1/control` | `POST` | Session + CSRF | 发起白名单内的协议栈/平台运维动作 |
| `/api/v1/control/{identifier}/cancel` | `POST` | Session + CSRF | 请求取消进行中的控制任务 |
| `/api/v1/audit` | `GET` | Session | 查询持久化控制与登录审计日志 |

---

## Jetson Console 接口（`127.0.0.1:8878`）

### 健康检查与鉴权

| 接口端点 | 方法 | 鉴权 | 用途说明 |
| --- | --- | --- | --- |
| `/api/v1/health` | `GET` | 公开 | Web 与设备执行器存活检查 |
| `/api/v1/auth/login` | `POST` | 公开 | 使用控制台密码换取会话 Cookie 与 CSRF Token |
| `/api/v1/auth/session` | `GET` | Session | 查询当前登录状态与 CSRF Token |
| `/api/v1/auth/logout` | `POST` | Session + CSRF | 注销当前会话 |

### 实时状态、历史指标与诊断

| 接口端点 | 方法 | 鉴权 | 用途说明 |
| --- | --- | --- | --- |
| `/api/v1/status` | `GET` | Session | 完整 UE 快照（USIM、小区、NR SA 注册、IPv4 PDU、网卡、绑定探测、路由、恢复与数据时效状态） |
| `/api/v1/config` | `GET` | Session | 脱敏后的现役 UE 配置（不含 SIM 密钥） |
| `/api/v1/events/stream` | `GET` | Session | 持久 SSE 状态与任务进度流 |
| `/api/v1/metrics` | `GET` | Session | 被动网卡收发速率与探测时延（支持 `hours` 窗口参数） |
| `/api/v1/history` | `GET` | Session | Setup 与 Recover 历史任务记录 |
| `/api/v1/diagnostics` | `GET` | Session | 脱敏模组与接口诊断信息 |

### 受限设备任务与维护模式

| 接口端点 | 方法 | 鉴权 | 用途说明 |
| --- | --- | --- | --- |
| `/api/v1/jobs` | `GET` | Session | 列出已准备、执行中及已完成的设备任务 |
| `/api/v1/jobs/{identifier}` | `GET` | Session | 查看单个任务的配置预览与分步结果 |
| `/api/v1/jobs` | `POST` | Session + CSRF | 生成 Setup 或 Recover 变更计划 |
| `/api/v1/jobs/{identifier}/run` | `POST` | Session + CSRF | 执行已准备好的设备任务 |
| `/api/v1/jobs/{identifier}/cancel` | `POST` | Session + CSRF | 请求有界取消活动任务 |
| `/api/v1/maintenance` | `POST` | Session + CSRF | 切换维护模式（释放 AT 串口锁并切回 Wi-Fi 备用默认路由） |
