# 审阅问题修复 — 2026-09-28

[English](2026-09-28-review-fixes.md)

后续进展：[实机部署与回滚验收](2026-09-28-review-deployment.zh-CN.md)。

源码基线为 `5f2d06f9baa586fb1bff73ac9c7c0822d2d62b87`，加上本文记录的
未提交修复。应用版本仍为 Jetson 0.6.0、Spark 0.2.0。本文是本地开发记录，
不是已部署发布的验收记录。

本轮问题是能否在不操作设备的前提下修复
[二次审阅](2026-09-28-next-round-review.zh-CN.md)确认的问题。仓库没有
CodeGraph 索引，采用源码检查、调用链追踪与回归测试。本修复阶段没有连接、
部署、启停或验证任何设备，也不关闭路线图验收项。

| 问题／调用链 | 修复与影响 | 回归依据 |
| --- | --- | --- |
| Jetson `cancel_job` → 取消事件 → 空闲 `sample(probes=True)` | 没有工作线程执行最终清理时主动清除取消事件；取消 ready/paused 任务后恢复正常空闲探测，保持自动恢复暂停。 | ready 与正常进入 paused 的任务，取消后连续探测。 |
| Spark `ControlHandler` → `execute` / `request_cancel` → `persist` | 使用同一可重入锁串行化状态更新和原子文件替换；首次进度写入纳入异常处理，首次持久化成功后才保留任务。 | 进度与取消并发交错、首次进度写失败、首次任务写失败，以及后续任务可正常接受。 |
| 诊断导出 → `redacted_diagnostics` | 归一化标识符键名，同时脱敏以这些名称命名的结构化 observation 值；原始实时快照保持不变。 | 已认证导出中的根级／嵌套 observation、`InvocationID`；保留普通指标。 |
| 调度器载荷 → `parse_ocudu` → 吞吐聚合 | 保留零传输块时明确上报的零速率；字段缺失或矛盾的正速率仍不可用，无传输块的 MCS/BLER 仍不可用。 | 活跃、空闲、混合、多活跃 UE 与字段缺失场景。 |
| 源码 CLI → 栈运行时 → systemd 回调；打包 stage → verify → install | 在 `deploy/spark/stack` 恢复受维护的生命周期源码、当前单元与离线私有打包；移除缺失的 `scripts.v2` 导入，归档退役部署输入。 | CLI 帮助、精确清单、ARM64 ELF／构建来源、篡改与链接拒绝、模拟安装与回滚、资源归属及启停失败保留证据。 |
| Spark 浏览器导航一致性 | 将过时的五项预期更新为已实现的八项导航。 | 完整本地 Spark 浏览器套件。 |

ready/paused 任务预留期间暂停采样在二次审阅中已撤销缺陷定性，保持原行为。

栈工具当前只支持首次安装，拒绝覆盖已有发布、单元与 CLI。安装不会启动或
设置服务开机自启，也不预置订户数据。包保留输入核心网配置及凭据，属于私有部署
候选，不是公开应用归档。启动同时要求当前进程的 SCTP 关联和 infoAPI 的 NG Setup
成功证据。初始无线配置关闭遥测，需另行执行带访问保护的指标配置。
参见[栈部署指南](../../deploy/spark/stack/README.zh-CN.md)。

## 本地验证

环境：macOS、Python 3.11.15（`local/bootstrap-check`）、Node 24.14.0。

- `make ci VENV=local/bootstrap-check`：两端生产构建／类型检查、7 项前端行为
  测试、80 项 Jetson 测试及 70 项 Spark 测试（69 通过、1 项 Linux 对端凭据测试
  跳过）通过。共享测试首次运行受沙箱限制，无法绑定回环 HTTP 端口。
- 放行本地监听后重跑 `make test-stack docs-audit release-audit license-audit
  shell-check VENV=local/bootstrap-check`，172 项共享测试与全部审计通过。
  Python 测试合计 321 项通过、1 项跳过。
- `make e2e-spark VENV=local/bootstrap-check` 与
  `make e2e-jetson VENV=local/bootstrap-check` 在本地合成服务上通过，
  Jetson 输出的失败列表为空。
- 生产构建仍有已有的包体积提示，没有构建错误。

安装测试将路径重定向至临时目录，并替换 Docker/systemd／平台调用；ELF 输入是
合成文件。测试只证明源码行为，不证明目标平台可执行性或无线就绪。没有安装真实
发布，也未执行设备回滚；模拟安装失败只清理新建文件。真实 ARM64 制品、
Python 3.10/3.12 与 Node 22、Linux 服务验证、已有安装迁移、指标配置、
N2/RF/UE 连通性及设备回滚留待后续授权阶段。
