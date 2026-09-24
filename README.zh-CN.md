# Agentic-OCUDU

Agentic-OCUDU 是一个独立的实验室 5G 系统，由 OCUDU 无线接入网、Open5GS
核心网和两个可独立发布的运维应用组成。

| 应用 | 职责 | 监听地址 | 版本 |
| --- | --- | --- | --- |
| Jetson Console | 模组发现、数据会话验证与有界恢复 | `127.0.0.1:8878` | 0.5.1 |
| Spark Platform | 主机、无线与核心网监测及受限栈操作 | `127.0.0.1:8877` | 0.2.0 |

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
`VENV=local/dev-venv` 使用新目录。`make check` 包含应用和根目录协议栈测试。
Spark 浏览器验证需先构建前端，执行
`npm --prefix apps/spark-platform/frontend exec -- playwright install chromium`，再执行
`make e2e-spark`；测试会自行启动和停止使用模拟数据的回环服务。

两个应用分别维护后端、前端、依赖锁、发布包和回滚路径。安装器默认不启用
开机自启，也不会操作另一个应用。

## 仓库结构

- `apps/jetson-console/`：Jetson API、设备执行器和 Web 应用。
- `apps/spark-platform/`：Spark 采集器、API 和 Web 应用。
- `stacks/ocudu/`：无线栈构建与运行输入。
- `stacks/open5gs/`：核心网、订阅和用户面输入。
- `deploy/`：各平台发布、安装和回滚工具。
- `config/`：共享且版本化的网络与依赖契约。
- `docs/`：当前架构、安装、运维和验收依据。

退役实现和迁移记录保存在当前源码树之外，不参与构建或发布。

请从[文档导航](docs/README.zh-CN.md)、[架构](docs/architecture.zh-CN.md)、
[贡献指南](CONTRIBUTING.zh-CN.md)、[安全策略](SECURITY.md)和
[发布指南](docs/releasing.zh-CN.md)开始。
