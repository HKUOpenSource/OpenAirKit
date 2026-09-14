# V2 P2-03 主机与组件采集验收记录

日期：2026-09-12
任务：V2-P2-03

## 实现

- Spark CPU 分开输出在线容量（cores）、实际使用核数和宿主占比；采样预热不伪造为零。
- gNB 输出 systemd Active/SubState、Result、ExecMainStatus、PID、重启数、InvocationID、进程 affinity 容量、CPU 核数/占比、RSS 和运行时间。
- 只对固定的 12 个 `aoc-v2-open5gs-*` 容器采集运行/健康/退出码/重启及 Docker CPU、内存；容器 CPU 核数、受限容量、容量占比和宿主占比分开。
- 主机内存、磁盘、温度和默认路由接口流量保持独立语义。
- B210 只读 USB `2500:0020` 属性、USB 速率和占用 PID；未调用 `uhd_find_devices`、`uhd_usrp_probe` 或打开设备。

## 实机只读取证

Spark SSH 只读盘点显示：

- `aoc-v2-radio.service` 为 active/running，Result=success，ExecMainStatus=0，NRestarts=0，PID 3693457，InvocationID 已取得。
- 12 个 `aoc-v2-open5gs-*` 容器均为 Up/healthy。
- 在线 CPU 为 20，MemTotal 127601452 kB，MemAvailable 100571800 kB。
- USB sysfs 中存在一个 Ettus vendor `2500` 设备。

这些值只证明 P2-03 数据源在当前主机可读；正式采集服务和页面实机显示由 P2-10/P2-11 验收。

## 自动验证

监测后端 23 项测试通过，包括 CPU 容量/核数/占比和容器 quota/cpuset 容量语义；前端 production build 与 `git diff --check` 通过。
