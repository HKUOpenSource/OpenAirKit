# 发布工程指南

[English](releasing.md)

**Jetson Console** 与 **Spark Console** 共用仓库统一版本号（`1.0.0`，定义于根目录
`VERSION` 文件），同时保持各自独立的源码边界与离线发布产物，每次发布流程仅针对
单一平台执行。

## 发布边界约束

所有离线发布包在交付前均须通过以下仓库审计门禁：

- **单平台严格隔离**：发布包内仅允许包含本平台的应用代码、部署工具、锁定依赖、
  wheelhouse、版本元数据、完整性清单（Manifest）及第三方许可声明。
- **违规内容拦截**：审计脚本将直接拒绝包含对端平台文件、`archive/` 目录、构建缓存、
  符号链接、未锁定依赖或生产用户凭据的归档包。
- **安全安装契约**：安装程序默认保持 systemd 服务不开机自启，且不得修改对端平台的
  协议栈配置或数据库。

## 构建前检查清单

1. 同步更新根目录 `VERSION`、两端后端 `__version__`、前端包描述文件、`README*.md` 版本徽章、
   `docs/releasing*.md` 与 `CHANGELOG.md`（由 `make version-audit` 自动校验一致性）。
2. 核对 Python 依赖锁文件、npm lockfile、上游源码提交哈希及容器镜像摘要。
3. 执行 `make ci`，完整覆盖后端单元测试、前端生产构建与仓库合规审计。
4. 对候选发布版本手动触发 `Extended checks` 工作流（覆盖 Jetson Python 3.10、
   Spark Python 3.12 及双端浏览器端到端套件）。任何失败项均须在打标签发布前修复。

## 构建离线 ARM64 发布包

构建前请先完成开发环境初始化。构建可在 macOS 或 Linux 主机上执行（需具备 Python
`3.10–3.12` 与 Node.js `22`），且每次须指定全新的输出目录。构建脚本将自动编译目标前端，
并按目标主机运行时拉取精确锁定的 Linux ARM64 依赖包：Jetson 目标为 `CPython 3.10 /
Ubuntu 22.04`，Spark 目标为 `CPython 3.12 / Ubuntu 24.04`。依赖标记按目标环境解析，
因此即使在更高版本 Python 主机上打包 Jetson，也会准确包含 `exceptiongroup`。

```sh
make build-jetson-release RELEASE_OUT=/tmp/agentic-ocudu-jetson
make build-spark-release RELEASE_OUT=/tmp/agentic-ocudu-spark
```

生成的标准归档文件分别为
`agentic-ocudu-jetson-<version>-linux-arm64.tar.gz` 与
`agentic-ocudu-spark-<version>-linux-arm64.tar.gz`。

输出目录下包含 `stage/`、归档包及其 `.tar.gz.sha256` 校验文件（Jetson 同时在
`stage/` 外保留下载的 `wheels/`）。发布清单（Manifest）记录源码提交哈希、工作区洁净度、
目标架构及 Python 版本——凡工作区含未提交改动的产物仅视作开发候选包，不可作为正式干净
发布。打包阶段会在归档前校验 wheel 平台标签、Python 版本约束、锁文件成员完整性与
传递依赖，校验器亦会拦截篡改、冗余文件及非安全路径。所有发布产物均须保存于 Git 之外。

Shell 构建入口同样支持 `--output <新目录>` 参数，可通过 `PYTHON` 环境变量指定开发解释器；
底层暂存脚本仅用于内部构建流水线，不直接产出压缩包。

## 部署与验收

将离线包与 `.sha256` 传输至目标主机，校验摘要无误后解压到全新暂存目录，并在正式安装前
运行包内 `verify` 与 `preflight`/`check-host`。安装过程须保持开机自启禁用策略，且不得
改动对端应用与协议栈。服务启动后依次核验 `/api/v1/health`、登录鉴权、SSE 实时流及
平台核心业务链路。

Jetson 包内运行 `python3 deploy/manage.py verify` 与
`python3 deploy/manage.py preflight`；Spark 包内运行
`python3 install.py verify --path .` 与
`python3 install.py check-host --path .`。主机侧校验务必使用对应平台要求的 Python
版本执行。包内预检用于辅助排错，不可替代独立的硬件实机安装/回滚验收门禁。

## 回滚验证与证据归档

升级前须登记现役版本号、SQLite 数据库 Schema 版本及备份路径。发布验证周期内须实际演练
一次完整回滚：切回上一稳定版本并验证服务健康，随后再重新安装候选版本。最终归档一份经过
脱敏处理的验收记录，须涵盖验证日期、源码提交号、版本号、Manifest 校验和、目标架构、
执行命令、实测结果、回滚版本标识及未覆盖项。
