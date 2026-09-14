# 架构

## 产品边界

Agentic-OCUDU 提供一套 5G SA 数据网络：OCUDU 提供 RAN，Open5GS 提供 5G
核心网；Spark Platform 负责基站侧监测与受限操作；Jetson Console 负责 UE
模组监测与受限操作。IMS、SIP 和语音服务不属于当前产品范围。

```text
Jetson Console -> RM520N 模组 -> B210 / OCUDU gNB -> Open5GS -> 外部数据网
                                      |
                               Spark Platform
```

## 组件归属

| 组件 | 拥有 | 不得拥有 |
| --- | --- | --- |
| Jetson Console | 模组锁、受限 AT 流程、自有路由、UE 状态、`127.0.0.1:8878` | RAN/核心网生命周期或任意 shell |
| Spark Platform | 主机/RAN/核心网证据、历史、事件、受限栈任务、`127.0.0.1:8877` | 模组控制或仅 UE 可见的信息 |
| OCUDU 栈 | B210、小区配置、NGAP 与无线指标 | Web 会话或平台数据 |
| Open5GS 栈 | 注册、PDU、策略、N3/N4/N6 与订阅状态 | 无线硬件或 UI 状态 |

每个应用分别拥有配置、SQLite 数据库、运行用户、systemd 单元、发布版本和回滚
记录。Web 进程不具有通用 root 权限；特权动作只能通过接受固定操作白名单的 helper。

## 网络契约

共享契约保存在 `config/network-contract.json`。当前部署使用 PLMN `460/03`、
DNN `oai`、一个 IPv4 数据 PDU 和配置的 `10.0.0.0/24` UE 地址池。站点地址和
凭据不进入仓库。

## 状态语义

证据质量与业务健康相互独立。`ok`、`stale`、`unavailable`、`unsupported`
说明数值是否可信；运行、健康、连接描述业务状态。只有新鲜的注册、PDU、地址池、
RAN 上下文和用户面证据一致时，UE 才显示为已连接。历史日志、已有 IP 或一次 ping
都不能单独证明当前连接。

采集器保存来源时间和进程代次。服务重启、日志轮转或计数器归零会开启新的观测
区间，避免旧设备在线、虚假零流量和速率尖峰。
