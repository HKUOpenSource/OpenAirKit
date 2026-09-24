# 设备本地一键启停脚本 — 2026-09-24

[English](2026-09-24-platform-lifecycle.md)

源码基线：`dba599c830f2abe6a09309ca85a52afd281519cf`，包含尚未提交的生命周期实现与
文档改动。应用仍为 Spark 0.2.0、Jetson 0.5.1。独立脚本已部署到各设备的
`~/aoc-ops/<platform>/`，分别在原生 ARM64 Python 3.12.3／3.10.12 上执行验收。

## 问题、调用链与影响

问题：如何在保留既有特权边界的情况下，本地一条命令启停平台，并包含 Spark 的无线与
核心网？仓库无 `.codegraph/` 索引，直接检查现有部署与维护实现。调用链为
`start.sh / stop.sh → platformctl.py → sudo -n aoc-maintain → approved manager / systemd`。
观测使用固定服务名、回环健康接口、本机 Docker 项目过滤及既有受限 UE-status 动作。

Spark 按核心网 → gNB → 监测启动，按 gNB → 核心网 → 监测停止。Jetson 仅操作两个 V2
服务。失败保留现场，重复调用不重启健康服务。脚本不请求模组恢复、任意命令、Docker
写操作、新维护权限或开机自启。Jetson 运维脚本从应用发布 staging 中排除；Spark
operations 原本就不属于其应用打包的显式输入。

安装方法、超时、退出码及并发边界见 [Spark 运维](../spark-operations.zh-CN.md)和
[Jetson 运维](../jetson-operations.zh-CN.md)。

## 验证

- 新增 32 项隔离生命周期测试，覆盖顺序、重复调用、部分运行／不健康状态、失败保留、
  残留进程／容器／socket／监听、权限、超时、操作锁、脚本路径、固定动作和 Docker 范围。
- 最终 socket 可见性修正之前，`make ci VENV=local/bootstrap-check` 通过：两个生产
  前端构建、242 项测试通过、1 项既有 macOS peer-credential 检查跳过，仓库审计通过。
- 修正后执行最终 `make check VENV=local/bootstrap-check`：Jetson 58 项通过，Spark
  52 项通过并跳过 1 项，根级栈／发布／生命周期 134 项通过。合计 244 项通过、1 项跳过；
  TypeScript、文档、发布边界、许可证、Shell 检查通过，`git diff --check` 通过。
- 本地使用 Python 3.11.15、Node 24.14.0，不替代 Python 3.10／3.12 与 Node 22 发布矩阵。
  独立脚本本身已在两端目标解释器实测。已有前端分块大小警告保留，本轮不修改前端。

首次 Jetson 状态检查发现受保护的 `0750` 运行目录使普通用户的 `Path.exists()` 抛出
PermissionError，实际服务正常。修正后在需要时读取内核 socket 列表，无法读取的证据
明确标记为不可访问，不把权限错误当作不存在。增加两项回归，没有修改权限或用户组。

## 实机验收

两端初始均不存在目标脚本目录。传输后核对 SHA-256；Jetson 修正 socket 检查前备份了
中间版本。未实测脚本回滚；首次安装可通过移除新增脚本撤回，后续可恢复已审阅的脚本
备份，这些操作只影响运维工具，不回滚应用发布。

以下命令均从 `/tmp` 执行，验证与工作目录无关；八次启动／停止调用均返回零：

1. Jetson 连续两次 `stop.sh`：两个 V2 服务 inactive，PID 为零，设备 socket 消失，
   8878 无监听；第二次没有再次发起停止动作。
2. Spark 连续两次 `stop.sh`：gNB、核心网和三个监测单元 inactive，PID 为零，项目
   核心网容器不再存在，8877 无监听。容器移除是既有 core-stop 行为，新脚本没有直接
   发出移除容器或卷的命令；第二次没有再次发起停止动作。
3. Spark 连续两次 `start.sh`：预期的 12 个核心网容器健康，gNB 通过既有启动检查后
   active，三个监测服务 active，health／collector 为 `ok`。第二次保留无线／监测 PID，
   没有再次发起启动动作。
4. Jetson 连续两次 `start.sh`：两个 V2 服务 active，网页可访问；重复启动保留 PID，
   没有再次发起启动动作。首次缓存证据过期时正确显示警告；最终执行器证据新鲜，报告
   注册成功、数据会话激活、实验室策略匹配、RNDIS 绑定连接已验证。维护模式仍关闭，
   自动恢复仍暂停，与基线一致。

全程没有显式调用模组重连／恢复。这是一次完整停止／启动循环，不是路线图中的五次
循环或完整故障矩阵。未执行实机故障注入、登录浏览器检查或独立关联 RAN／UE 的端到端
验收。既有管理链路保护缺口未修复，`management_protected=true` 不代表该问题已解决。

最终对比确认：

- Spark release 为 `5bc68497243efdf5`，Jetson 为 `186b6c4659cc5e14`；发布链接与
  manifest 哈希未变，Spark 28 项、Jetson 48 项清单文件全部匹配。
- 已安装维护工具哈希、所检查服务的开机策略未变；应用服务仍 disabled，无线／核心网
  仍 static，自动重启次数为零。
- Spark 的 47 个其他容器身份、状态、启动时间和重启次数全部保持一致。原始容器清单
  和运行日志未加入版本控制。

## 已交付脚本 SHA-256

| 文件 | SHA-256 |
| --- | --- |
| 两端 `start.sh` | `2ef85b63c47b0c7d05b35775ae56c2be159ba8d95e72ea3f14329e2b0abe6c77` |
| 两端 `stop.sh` | `2fda486b618c627756119499d2f9ecefbf0a6ec0ac6b4780c3cbfd10fcdda583` |
| Spark `platformctl.py` | `dca4cd6167ecd157758c069c86932ebcf92d75ed3a3a0008fc8453cddd1e5f9f` |
| Jetson `platformctl.py` | `c0a9b6634a1e8271bb86d3591e304df7c57e9558437bc81a6dd8ef276d5d1bdc` |

路线图仍是唯一完成清单，本轮没有改变任何 Gate 状态。
