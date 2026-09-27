# Spark 系统安装

## 前提

目标机应为 ARM64、Python 3.12，并提供 systemd、Docker Compose 和通过 USB 3
连接的受支持 B210。确认 `127.0.0.1:8877` 与 `127.0.0.1:8001` 空闲。监测
平台、无线栈和核心网具有不同的发布与生命周期边界。

安装前核验 `config/images.lock.json` 的镜像摘要、`config/upstreams.json` 的
源码版本，以及从 `config/network-contract.json` 派生的站点配置。生产订阅资料
只能从受保护的部署状态加载，不能进入仓库。

## 安装监测平台

使用 `make build-spark-release` 构建并传输 ARM64 发布包，再运行发布包内的
platform installer 完成 preflight 和 install。安装位置为
`/opt/agentic-ocudu/monitor`，三个平台服务默认不开机自启。安装监测平台不会
启动或重启协议栈。

在解压后的 Spark 发布目录使用实际安装器动作：

```sh
python3 -I -B install.py verify --path .
python3 -I -B install.py check-host --path .
sudo python3 -I -B install.py install --path .
```

协议栈准备完成后，批准匹配的[维护包](../deploy/maintenance/README.md)，并安装
[Spark 生命周期脚本](spark-operations.zh-CN.md)。完整启动和状态检查将 N2 建链
与服务进程状态分开验证。

## 准备协议栈

使用 `deploy/spark/stack` 和 `scripts/spark` 下的工具。接收 UE 流量前验证 B210
所有权、核心网、N2 和回环 JSON 指标端点。指标端点只绑定回环地址并限制为采集器
账户访问。

## 验证

通过 SSH 隧道访问 `127.0.0.1:8877`。验证所有核心网容器、gNB 进程代次、N2、
当前 UE 上下文、活动 PDU 以及独立的 N3/N6 证据。端到端数据路径必须由 Jetson
侧绑定接口的探测完成验收。
