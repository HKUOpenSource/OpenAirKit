# Agentic-OCUDU

Agentic-OCUDU 是一个独立的实验室 5G 系统，由 OCUDU 无线接入网、Open5GS
核心网和两个可独立发布的运维应用组成。

| 应用 | 目标主机与运行时 | 监听地址 | 版本 |
| --- | --- | --- | --- |
| Jetson Console | Jetson ARM64、Ubuntu 22.04、Python 3.10、RM520N（RNDIS / ECM） | `127.0.0.1:8878` | 0.6.2 |
| Spark Platform | DGX Spark ARM64、Ubuntu 24.04、Python 3.12、B210 USB 3 | `127.0.0.1:8877`（`8879` 为 gNB JSON 指标，仅限 root） | 0.2.1 |

两个应用各自承担独立职责：
- **Jetson Console**：模组发现、有界 AT/注册/PDU 检验、自有故障切换路由及有界恢复。
- **Spark Platform**：主机、无线（`127.0.0.1:8879` 回环 JSON 指标 + `nftables` 防护）与 Open5GS 核心网监测及受限协议栈操作。

当前产品范围是一套 5G SA 数据网络。只有注册、配置地址池中的活动 PDU、
当前 RAN 上下文和真实用户面路径均具有新鲜证据时，设备才会显示为已连接。
IMS、SIP 和语音服务不在当前范围内。

## 开发

使用 Python 3.10–3.12 和 Node.js 22。Jetson 目标版本为 Python 3.10，Spark 为
Python 3.12，CI 覆盖两者。初始化会创建 `.venv`，安装两个后端的开发依赖，并为
两个前端执行 `npm ci` 和构建。

```sh
make install-dev BOOTSTRAP_PYTHON=python3.12
make check
```

不会覆盖已有环境。若 `.venv` 使用旧 Python，在两条命令中都指定
`VENV=local/dev-venv` 使用新目录。`make check` 包含前端行为测试、TypeScript 检查、
应用与根目录协议栈测试以及仓库边界审计（`docs-audit`、`release-audit`、
`license-audit`、`shell-check`）。Spark 浏览器验证需先构建前端，执行
`npm --prefix apps/spark-platform/frontend exec -- playwright install chromium`，再执行
`make e2e-spark`；测试会自行启动和停止使用模拟数据的回环服务。若仓库根目录存在
`.codegraph/`，搜索或阅读源码前请先遵循 [CodeGraph 工作流](docs/coding-agent-codegraph.zh-CN.md)。

两个应用分别维护后端、前端、依赖锁、发布包和回滚路径。安装器默认不启用
开机自启，也不会操作另一个应用。

## 仓库结构

- `apps/jetson-console/`：Jetson API、设备执行器和 React Web 应用。
- `apps/spark-platform/`：Spark 采集器、API 和 React Web 应用。
- `packages/console-ui/`：共享的 Astryx Core、Charts 与 Neutral 主题组件包（`@aoc/console-ui`）。
- `stacks/ocudu/`：无线栈构建与运行输入。
- `stacks/open5gs/`：核心网、订阅和用户面输入。
- `deploy/`：安装器、协议栈生命周期、受限维护 helper（`aoc-maintain`）及可选 Jetson 开机协调器（`boot_connect.py`）。
- `scripts/`：发布包构建脚本、Spark 指标守护事务（`enable_radio_json_metrics.py`）与 CI 审计脚本。
- `config/`：共享且版本化的网络与依赖契约。
- `docs/`：当前架构、安装、运维和验收依据。

退役实现和迁移记录保存在当前源码树之外，不参与构建或发布。

请从[文档导航](docs/README.zh-CN.md)、[架构](docs/architecture.zh-CN.md)、
[贡献指南](CONTRIBUTING.zh-CN.md)、[安全策略](SECURITY.md)和
[发布指南](docs/releasing.zh-CN.md)开始。
