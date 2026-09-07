# OCUDU 部署模块

负责 OCUDU 源码获取、ARM64 构建、产物记录、配置生成及 gNB 健康检查。运行形态从单进程 CU-CP + CU-UP + DU 开始，B210 通过 USB3 / UHD 接入；无需 O-RU。F1 分离和 7.2x O-RU 是后续独立选项。

上游版本来自 `config/upstreams.json`；源码下载到被忽略的 `build/sources/ocudu/`，构建与安装产物进入本项目目录。不能引用 Biverge checkout、复用其虚拟环境或覆盖 `/usr/local` 中共享 UHD。

## 后续实现位置

- `scripts/build.sh`：校验固定提交、检测依赖、独立构建，输出构建清单；尚未实现。
- `config/`：生成 gNB YAML 的参数映射规则；射频参数未确认时拒绝生成可启动配置。
- `scripts/check-health.sh`：检查本栈 N2 对端、进程稳定性及设备占用；尚未实现。

systemd 编排统一归属 `deploy/systemd/`，本模块不自行启动旧/新核心网。gNB 绑定新 bridge 地址 `172.28.80.1`，AMF 使用 `.12`，UPF 使用 `.14`。

## 验收

先完成无射频构建和配置解析，再在切换窗口确认 B210 序列号、USB3、线程调度和稳定运行。不得在原 OAI 使用 B210 时执行会打开设备的探测或测试。CPU 亲和性基于实测分配，不直接照搬旧栈 CPU 0-18 配置。

参考：[OCUDU 安装](https://docs.ocudu.org/user_manual/installation/)、[CU/DU 与 B210 示例](https://docs.ocudu.org/tutorials/cu_du_split/)。
