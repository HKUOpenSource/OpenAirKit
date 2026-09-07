# OAI 核心网部署模块

部署本项目自己的 OAI 5GC。新栈的 AMF、SMF、UPF、NRF、AUSF、UDM、UDR、数据库和 ext-DN 均使用独立配置、网络、容器及数据卷。

首阶段目标是数据 DNN `oai` 的注册、认证、PDU 会话和用户面连通。IMS 地址已预留，但 IMS/VoNR 不属于首阶段已支持能力；后续独立验收 5QI、P-CSCF、SIP 与媒体链路。

`config/upstreams.json` 中的 OAI 2.2.1 是候选基线，不是已经验证的 ARM64 镜像锁文件。部署前逐个检查镜像架构、版本、健康检查及配置格式，并记录 digest；数据库版本单独验证。不能使用 `latest` 作为发布基线，也不依赖现有 AMF/SMF 的 Biverge 补丁镜像。

订阅 IMSI、Ki、OPc、数据库密码由明确的订阅配置流程输入 `/etc/agentic-ocudu/secrets/`，文件权限按消费者收敛，不进入 Git。不自动读取或共用旧 MySQL 数据目录。沿用同一 SIM 时，新数据库必须配置一致的认证材料，并验证切换后的 SQN 重同步；复制一次数据库不等于长期认证状态一致。

后续实现 `compose/compose.yaml`、`config/` 和 `scripts/`。具体编排约定见 [compose/README.md](compose/README.md)。
