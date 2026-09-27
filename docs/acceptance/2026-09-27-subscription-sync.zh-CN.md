# 订阅同步与双设备接入验收 — 2026-09-27

[English](2026-09-27-subscription-sync.md)

源码基线：`39dde4d0216dee973ed6cbf40ecb500e83c1ac74`，包含
[执行准备记录](2026-09-27-subscription-sync-preparation.zh-CN.md)中的未提交维护工具
及 BSON 修复。已安装应用仍为 Spark 0.2.0 / Jetson 0.5.1。Spark 为 ARM64
Python 3.12.3，两台 Jetson 系统 Python 均为 3.10.12；临时串口探针使用已安装
OAI Python 环境和本仓库的硬件发现、模组查询解析器。

## 导入证据

操作员在 Spark 终端以 sudo 执行暂存工具，并提供成功结果：源订阅 4 条，目标
原有 1 条，计划/实际新增 3 条，最终 4 条；`existing_unchanged`、
`source_static_unchanged`、`cleanup`、`passed` 均为 true。代理没有读取仅 root
可读的备份文件，也不将此次结果表述为已独立演练备份恢复。

- 私有备份目录：`/var/lib/aoc-maintenance/subscription-sync-1790492951589900727`。
- 停机数据卷归档 SHA-256：
  `a8f5fb41769e4d7ad59d5c281d6d6189665cfec77b2c382a56f5039bb63b1283`。
- 部署包清单 SHA-256：
  `3e40ff4c69c064d36cc6f055e4423249f399b4e8af5269f3de17ee3b8a8a82ec`。

随后独立 SSH 检查确认 OAI 仍运行、OCUDU 核心网/无线停止、无本项目容器、
MongoDB 持久卷保留。OCUDU 实测运行期间，通过认证只读 MongoDB 查询独立确认
四条记录均为单 `oai` IPv4 会话、配置 5QI 9，SQN 均为 BSON int64。没有输出原始
身份、凭据或 SQN 值。后续网络鉴权会正常推进 SQN；“保持不变”指的是导入阶段，
不涵盖随后的网络活动。

## 设备与核心网验收

用户已另行部署 OAI 启停脚本。检查已安装 Jetson 脚本确认：停止操作先退出控制
进程，再调用固定管理 helper 保护 Wi-Fi、禁用模组自动默认路由。两台停止均通过，
无其他控制进程运行。对当前 Tailscale SSH 对端的实际端点进行包含传输 mark 的
路由查询，两台均走 Wi-Fi；Wi-Fi 也是各自唯一默认路由。

临时只读探针在打开模组前检查控制进程已停止，随后独占串口，查询当前 SIM
指纹、服务小区、注册、数据上下文和地址。没有调用模组写操作、修改 SIM/设置或
触发恢复/重置。两台 SIM 指纹均与源订阅清单对应；切换前同一探针已确认两台
在 OAI 下注册及绑定数据路径正常。

切换顺序：停止两台 OAI Jetson 控制进程 → 使用已安装脚本停止 Spark OAI →
执行 `~/aoc-ops/spark/start.sh` 启动 OCUDU。12 个 Open5GS/数据网容器健康，
gNB NG Setup 成功。早期样本正确显示未注册、无 PDU；随后两台模组自然重新接入，
没有显式重置或重连。

| OCUDU 运行期间的新鲜证据 | matt Jetson | zihao Jetson |
| --- | --- | --- |
| SIM 与导入清单匹配 | 是，原目标库订阅 | 是，本次新增订阅 |
| RAT / PLMN / 频段 / PCI | NR5G-SA / 46003 / n78 / 666 | NR5G-SA / 46003 / n78 / 666 |
| 模组当前注册 | 已注册 | 已注册 |
| 数据 PDU / 地址池 | 活动 / 有效 | 活动 / 有效 |
| AMF 移动性 / 连接状态 | registered / connected | registered / connected |
| SMF 会话 / QFI / 5QI | 活动 `oai` / 1 / 9 | 活动 `oai` / 1 / 9 |
| UE 与核心网地址对应 | 一致 | 一致；与 matt 不冲突 |
| 绑定接口的网关 / UPF / 公网探测 | 全部通过 | 全部通过 |

两台 UE 采样间隔不足一秒，约十一秒后的核心网采样同时显示两个已连接 UE 和
两个活动数据会话。每个端点发送两个小 ICMP 请求，先检查路由，再绑定发现的模组
接口。请求/响应证明双向可达，不代表吞吐或核心网主动发起下行连接能力。本次
临时 UE 探针没有验证 OCUDU 专属 ext-DN HTTP 端点。

当前 AMF 日志有两条注册完成记录、一条同步失败匹配，没有 MAC 失败匹配。
有界日志没有显式 AUTS 标记，因此本轮不独立认定 AUTS 交换已验收。
最终注册、当前 PDU 和用户面结果均通过。

## 恢复基线与范围

OCUDU 停止已通过：五个项目服务 inactive、PID 为零，无项目核心网容器，无 Web
监听，数据库卷保留。随后使用已安装脚本启动 Spark OAI，再启动两台 Jetson OAI
控制进程；三个生命周期命令均通过。最终检查确认：

- OAI 核心网、gNB、采集器和 Web 服务 active、自动重启次数为零；九个 OAI
  核心网/数据网容器全部健康。
- 两台 Jetson 的已安装 `verify-jetson.sh` 均退出零并输出验收成功标记，覆盖
  绑定接口探测、路由和服务边界；两台公开健康接口均为 `ok`、版本 0.3.0。
- 当前 OAI SMF 显示两条已对应到设备的 `oai` 会话，均为 activated。
- OCUDU 核心网/无线保持 inactive，无本项目容器，MongoDB 卷保留。最终运行
  平台为 OAI，四条订阅可供下次 OCUDU 启动使用；临时探针没有占用串口。

第二台 Jetson 通过临时只读工具验收，没有安装或初始化其 OCUDU Console。
另外两条订阅只通过数据库/结构检查，未做实机接入。本次单轮双设备切换不关闭
任何 Gate、完整故障矩阵、五次循环或数据库恢复验收。数据库备份继续私密保留在 Spark。

本次后续仅修改验收文档，`make docs-audit VENV=local/bootstrap-check` 通过
88 份当前文档，`git diff --check` 通过。此前代码和测试修改仍未提交；本次没有
重复运行未变化的后端测试或前端构建。
