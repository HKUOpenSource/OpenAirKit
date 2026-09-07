# Agentic-OCUDU

面向 DGX Spark 的独立 5G SA 实验栈：**OCUDU RAN + 独立 OAI 5GC + 独立监控平台**。首阶段使用现有 USRP B210 / UHD / Split 8，不要求 O-RU。

本仓库不依赖 Biverge 的代码、数据库、Python 环境、定制镜像或运行目录。唯一的兼容边界是宿主机 systemd：两套 RAN 串行占用同一台 B210，切回入口保持原 Biverge 脚本。

**当前阶段：仓库骨架与部署设计已初始化，尚未安装或启动新服务。** `.in` 文件是待实现的部署模板，不能直接安装。ARM64 镜像、OCUDU 构建、UE 接入、systemd 切换均需按验收计划验证。

## 目录结构

```text
Agentic-OCUDU/
├── README.md
├── Makefile                         # 本地只读规划与校验入口
├── config/
│   ├── spark.example.json           # 环境、地址、端口与旧栈保留资源
│   └── upstreams.json               # 上游来源、版本与待验证项
├── modules/
│   ├── ocudu/
│   │   ├── README.md                # ARM 构建、B210、RAN 部署边界
│   │   └── config/README.md         # 无线参数映射与生成要求
│   ├── oai-core/
│   │   ├── README.md                # 独立 5GC、订阅和用户面
│   │   └── compose/README.md        # Compose 服务及隔离约定
│   └── monitoring/
│       ├── README.md                # 采集、API、前端与权限规划
│       └── contracts/
│           └── observation.schema.json
├── deploy/
│   └── systemd/                    # 新栈生命周期与 B210 互斥模板
├── scripts/
│   └── validate.py                 # 无第三方依赖的配置校验及规划输出
├── tests/
│   └── test_validate.py            # 地址/端口冲突等负向测试
└── docs/
    ├── architecture.md             # 模块职责、数据流、部署拓扑
    ├── switching.md                # 原脚本兼容机制及切换验收
    ├── roadmap.md                  # 分阶段实施与完成标准
    └── research/                   # 现场调研与此前迁移评估
```

`local/`、`build/`、`artifacts/` 和 `secrets/` 按需生成并被 Git 忽略，不放占位文件。后续实现分别落入模块自己的 `scripts/`、`config/`，以及监控的 `backend/`、`frontend/`；尚未实现的应用不创建空代码包。

## 本地使用

Python 3.9+，无需安装依赖，无需连接 Spark：

```sh
make plan
make check
```

校验基于仓库中记录的现场保留资源，**不是实时端口、路由或 Docker 冲突探测，也不表示可以部署**。自定义配置可通过 `python3 scripts/validate.py --config /absolute/path/to/config.json` 检查。

## 隔离与切换

| 资源 | Biverge / 原 OAI | 本仓库规划 |
| --- | --- | --- |
| systemd | `oai-*` | `aoc-*` |
| Compose project | `oai-only-cn5g` | `aoc-cn5g` |
| 核心网 bridge | `oai-cn5g` | `aoc-cn5g` |
| 核心网网段 | `192.168.70.128/26` | `172.28.80.0/24` |
| UE 地址池 | 原 `10.0.*` 地址池 | `10.80.0.0/24`，IMS 预留 `10.80.9.0/24` |
| 监控 HTTP | `127.0.0.1:8787` | `127.0.0.1:8877` |
| RAN N3 | `192.168.70.129:2152/UDP` | `172.28.80.1:2152/UDP` |
| B210 | OAI gNB | OCUDU gNB，互斥占用 |

地址和端口是 2026-09-07 现场核对后的候选分配，部署前仍须实时复查。标准 N2/N3/N4 端口不必改号，必须绑定各自地址或网络命名空间；不能在宿主机通配监听后宣称隔离。

待部署和切换验收通过后，新栈入口计划为 `sudo systemctl start aoc-stack.target`；切回仍执行 Spark 上的 `~/.local/bin/oai-spark-services.sh start`。新栈的 systemd 互斥关系将先释放 B210，并停止新栈服务。此能力**尚未安装或进行现场验证**，详细限制见[切换设计](docs/switching.md)。

阅读顺序：[架构](docs/architecture.md) → [切换](docs/switching.md) → [实施计划](docs/roadmap.md)。此前调研提出过“复用旧核心网”的路径；本仓库采用用户后续要求的独立核心网，以本文和当前设计为准。
