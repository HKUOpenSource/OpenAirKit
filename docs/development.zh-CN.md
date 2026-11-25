# 开发者指南

[English](development.md)

本指南说明 **OpenAirKit** 的本地开发环境搭建、模拟预览调试、测试套件、浏览器端到端检查以及仓库自动化审计门禁。贡献规范与目录归属边界请参阅[贡献指南](../CONTRIBUTING.zh-CN.md)与[架构决策记录](adr/README.zh-CN.md)。

## 1. 环境准备

本地开发与验证需准备 **Python `3.10–3.12`** 与 **Node.js `22`**（Jetson 实机目标为 Python `3.10`，Spark 实机目标为 Python `3.12`，自动 CI 运行于 Python `3.12`）。

```sh
make install-dev BOOTSTRAP_PYTHON=python3.12
```

Makefile 默认使用 `.venv/` 作为虚拟环境路径。如需使用自定义目录（例如 `local/dev-venv`），可在所有 `make` 命令中传入 `VENV=local/dev-venv`：

```sh
make install-dev BOOTSTRAP_PYTHON=python3.12 VENV=local/dev-venv
make check VENV=local/dev-venv
```

`make install-dev` 会安装共享工具依赖（`requirements-tools.txt`）及两端后端开发依赖，并执行双端前端 `npm ci` 与生产构建。

## 2. 本地模拟运行与前后端联调

两套 Web 控制台均可在无 USRP / 5G 模组硬件的本机环境下启动调试：

- **Jetson Console（模拟设备模式）**：使用 [`apps/jetson-console/`](../apps/jetson-console) 内的 `SimModem` 与 `SimNetwork` 在回环地址 `127.0.0.1:8878` 运行。执行 `npm --prefix apps/jetson-console/frontend run dev` 启动 Vite 开发服务器，会自动将 `/api` 代理到 `http://127.0.0.1:8878`。
- **Spark Console（本地只读预览）**：可通过 [`scripts/monitor_preview.py`](../scripts/monitor_preview.py) 在 `127.0.0.1:8877` 启动禁用切换控制的本地预览服务；前端执行 `npm --prefix apps/spark-console/frontend run dev` 时，`/api` 会自动代理到 `http://127.0.0.1:8877`。
- **共享 UI 原语包**：Astryx Core、Charts 与 Neutral 主题封装位于 [`packages/console-ui/README.zh-CN.md`](../packages/console-ui/README.zh-CN.md)，不包含任何平台业务逻辑。

## 3. 测试与仓库审计矩阵

| Make 目标 | 检查范围 | 是否需要真实硬件 |
| --- | --- | --- |
| `make test-jetson-backend` | Jetson 执行器、API 安全头/请求大小限制、配置迁移、路由与回滚单测 | 否 |
| `make test-spark-backend` | Spark 采集器、SQLite 历史存储、Open5GS 关联与受限控制单测 | 否 |
| `make test-stack` | OCUDU/Open5GS 配置校验、运行时编排、SIM 开户与发布包校验测试 | 否 |
| `make test-frontend-behavior` | 双端前端行为契约测试（`behavior.mjs`） | 否 |
| `make typecheck` | 双端 TypeScript 严格类型检查（`tsc --noEmit`） | 否 |
| `make docs-audit` | 中英文配对文档完整性、相对链接、标题锚点与公开发布卫生检查 | 否 |
| `make release-audit` | 单平台发布边界、依赖锁文件与 systemd 单元合规检查 | 否 |
| `make license-audit` | 根目录 `LICENSE`、`images.lock.json` 与前端私有包属性校验 | 否 |
| `make version-audit` | 根目录 [`VERSION`](../VERSION) 与后端、npm、README 徽章及共享依赖版本一致性校验 | 否 |
| `make shell-check` | 对 `deploy/` 与 `scripts/` 下全部 Shell 脚本执行 `bash -n` 语法检查 | 否 |
| `make check` | 在已就绪的环境中一次性运行上述全量快速检查 | 否 |
| `make ci` | 完整 CI 入口（先执行前端 `npm ci` + 生产构建，再执行全量测试与审计） | 否 |

### 浏览器端到端（E2E）检查

在对应前端目录安装 Playwright Chromium 后运行：

```sh
make e2e-jetson
make e2e-spark
```

上述套件均针对隔离的回环模拟服务端执行，不会操作任何物理设备。

## 4. 重新生成架构图资产

`docs/assets/diagrams/` 中的全部架构图与状态机图（含明暗双主题、中英文双语）均由 [`docs/assets/diagrams/generate.py`](assets/diagrams/generate.py) 确定性生成。图表与硬件视觉资产规范请参阅[视觉素材规范](assets/README.md)。

## 5. 离线打包与代码检索辅助

- **构建离线 ARM64 发布包**：请参阅[发布工程指南](releasing.zh-CN.md)，使用 `make build-jetson-release` 与 `make build-spark-release`。
- **CodeGraph 索引检索**：若本地根目录存在 `.codegraph/` 索引，可按 [CodeGraph 工作流](coding-agent-codegraph.zh-CN.md) 在修改跨模块接口前先检索调用链。
