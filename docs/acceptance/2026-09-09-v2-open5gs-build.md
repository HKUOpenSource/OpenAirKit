# V2-P1-03 ARM64 版本锁定与无射频验证

- 日期：2026-09-09
- 状态：V2-P1-03 已通过；第一阶段整体仍进行中
- 代码提交：待提交，工作树基线 `88a4b4d074712662b1cef66fd152ffcf04e59167`
- 环境：Spark，Ubuntu 24.04.4，内核 `6.17.0-1008-nvidia`，Docker 29.1.3，原生 ARM64
- 范围：构建、依赖锁定、空核心网接口和临时 MongoDB；没有 RF/UE 接入验收

## 固定产物

完整输入见 [sources.lock.json](../../stacks/open5gs/sources.lock.json)，构建产物见 [artifacts.lock.json](../../stacks/open5gs/artifacts.lock.json)。构建工具同时核验 `config/upstreams.json` 与 `config/images.lock.json` 中仍适用的固定输入。

| 组件 | 版本或提交 | 核验方式 |
| --- | --- | --- |
| Open5GS | v2.8.0，`157f611a530e292e40ec50f9d23f0ef5d4fcd6a6` | 官方 tag 解引用、源码归档 SHA256、Spark 原生编译、二进制版本回读 |
| freeDiameter | `14725af3ba0edbf9ff61c4e3239ed42464423b2e` | 固定上游 `r1.5.0` 分支当前提交及归档 SHA256 |
| prometheus-client-c | `a58ba25bf87a9b1b7c6be4e6f4c62047d620f402` | 固定上游 `open5gs` 分支当前提交及归档 SHA256 |
| MongoDB | 8.0.30 | ARM64 平台 manifest digest、实际启动、版本回读、临时读写 |
| Ubuntu 构建基底 | 24.04 | ARM64 平台 manifest digest |
| 编译依赖 | GCC 13.3.0、Meson 1.3.2 等 | 完整 `packages.tsv` 归档，摘要写入产物锁 |

Open5GS 主仓库的 wrap 文件包含分支引用；准备工具预置校验后的依赖源码，Meson 使用 `--wrap-mode=nodownload`。Linux SCTP、libtins 使用构建镜像内的发行版包，不触发其 fallback 下载。依赖安装没有写入宿主系统。

首次 APT 解析使用当日仓库，后续完全相同产物的重放以已导出的镜像归档和 image ID 为准；不承诺未来重新解析 APT 后字节一致。Open5GS 本地构建未推送镜像仓库，因此 image ID 与镜像归档 SHA256 分别记录，不冒充 registry manifest digest。

## 实际结果

| 检查项 | 实际结果 | 结论 |
| --- | --- | --- |
| 源码校验与构建 | 三份源码校验和匹配；4661 个构建步骤，2 任务并行完成 | 通过 |
| 上游测试 | `open5gs:unit / core`、`crypt`、`unit` 均为 OK，无跳过/超时 | 通过 |
| ARM64 架构 | Open5GS、MongoDB image inspect 均为 Linux/arm64 | 通过 |
| AMF infoAPI | `/gnb-info`、`/ue-info` 返回 `items: []` 及 `pager.count: 0` | 空列表格式通过 |
| SMF infoAPI | `/pdu-info` 返回 `items: []` 及 `pager.count: 0` | 空列表格式通过 |
| Prometheus | AMF、SMF 的 `/metrics` 均返回非空 HELP/指标文本 | 通过 |
| NF 退出 | NRF、AMF、SMF 收到 SIGTERM 后各返回 0，没有强杀 | 通过 |
| MongoDB | 回读 8.0.30，ping=1，临时集合写入/查询/删除通过 | 通过 |
| MongoDB 退出 | 正常退出 0，tmpfs 数据随容器清理 | 通过 |
| 测试资源清理 | NF/MongoDB 两个专属容器已移除；标签查询无残留 | 通过 |
| 本地回归 | `make check` 共 113 项通过，`git diff --check` 通过 | 通过 |

构建后的 NF/MongoDB 运行检查均使用 `--network none`，仅容器回环地址，无宿主端口发布、USB/TUN 设备、宿主目录挂载或 Linux capabilities。CPU 限额 2 核、内存限额 2 GiB。镜像构建使用 Docker 默认构建网络获取发行版包，未修改宿主 N6/NAT/路由，没有访问生产 SIM 或数据库。

SMF 未配置 Diameter 的警告符合本次 5GC 空服务检查范围。并行初始化期间出现过 NRF 尚未监听的连接警告；本次仅验证接口存在和空结果格式，没有将其描述为全 NF 注册/就绪验收。后续正式 Compose 需实现就绪排序与相互注册验证。

## 现场盘点与原栈保持

- Spark：20 核，Cortex-X925/A725，约 3 TiB 可用磁盘；MongoDB 在该 CPU/内核组合上真实启动通过。
- B210 的 sysfs/USB 拓扑报告 5000M 链路；本次没有执行 UHD 探测或取得 B210 控制权。
- 现有 OCUDU 提交为 `050a2bb72e1d794cd60570d809987c1fcda3e54b`，二进制 SHA256 为 `879f17f0eed439b962f22608380f5f0782260031c9e212f9a1732bfd303d15ef`，与旧构建记录一致。
- OCUDU 重新执行 timer/network 2 项以及安全算法 59 项，共 61 项 CTest 通过；这不替代虚拟 UE、无线接入或性能基线。
- 旧项目停止后仍保留 `aoc-cn5g-net` / `aoc-cn5g`，路由 `172.28.80.0/24` 仍存在，虽为 linkdown 也不能重复分配。本次保留现场，后续部署单独处理所有权与清理。
- 核验前后 OAI gNB MainPID 均为 `2829454`、NRestarts 均为 `1`、状态 active；原核心网 10 个容器仍 healthy。本次没有操作 Jetson 或重启原 OAI。

## 失败与修复记录

1. 首次源码打包带入 macOS AppleDouble 元数据，Meson 把 `._*.wrap` 当作依赖文件，解析失败。修复为 Python tar 打包并排除元数据，Docker 同时设置 `.dockerignore`；已增加回归测试。
2. 首次 AMF 空配置遗漏固定版本要求的 `time.t3512.value`，启动退出 255。补齐 540 秒定时器，重新验证正常退出；失败记录仍留在 `open5gs-v2-evidence-01`。
3. 自检程序最初假定 Meson JSON 使用短测试名，导致已通过测试被拒绝。改为验证固定 Meson 的完整组名，仍要求恰好三组且全部 OK；增加缺失、重复和失败测试记录的拒绝测试。第二次记录保留在 `open5gs-v2-evidence-02`。
4. 最终完整通过记录为 `open5gs-v2-evidence-03`。失败均未触发旧栈重启或隐藏重试，没有把前后不同任务拼成成功。

## 归档与下一步

Spark 自有工作目录 `/home/defaultuser/agentic-ocudu-work/` 保存：

- `aoc-open5gs-v2-verified-arm64.tar`：Open5GS 验证镜像和 MongoDB 镜像，SHA256 `331a3651593294c6a1798bae5444dec182a740c5d7ca04a9451e305f7bf17d91`。
- `aoc-open5gs-build-final.tar.gz`：不含 macOS 元数据的源码构建上下文，SHA256 `04bc393d006c74c1fbaccc89dda0985d670123b5427e95b542b0ca042f8955aa`。
- `open5gs-v2-evidence-03/`：测试结果、精确包版本、空接口响应和错误日志。`result.json` SHA256 `f3521fbc65b0806e1fe93d9ffac0cf7ec1f9c4e5b9ec9ede7083107bcd89730a`。

V2-P1-04 仍未完成：需要从验证镜像形成仅数据业务的生产运行包、实际 NF 依赖/就绪检查和持久化。V2-P1-05/06/09 仍需独立订阅、UPF/N6 转发和无线验证；真实 infoAPI 字段关联和 QoS 证据留待这些步骤验收。本次没有通过第一阶段 Gate，也没有恢复为已废弃的 OAI/IMS 方案。

参考：[Open5GS v2.8.0 官方发布](https://github.com/open5gs/open5gs/releases/tag/v2.8.0)、[固定版本 AMF 接口注册](https://github.com/open5gs/open5gs/blob/157f611a530e292e40ec50f9d23f0ef5d4fcd6a6/src/amf/init.c)、[固定版本 SMF 接口注册](https://github.com/open5gs/open5gs/blob/157f611a530e292e40ec50f9d23f0ef5d4fcd6a6/src/smf/init.c)、[MongoDB 平台要求](https://www.mongodb.com/docs/manual/administration/production-notes/)。
