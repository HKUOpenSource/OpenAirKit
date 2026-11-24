# 第三方声明

运行时依赖来自各平台锁文件及发布所用的离线 wheelhouse。每次发布记录确切的
依赖集合，并在 `THIRD_PARTY_LICENSES/` 和 `THIRD_PARTY_DEPENDENCIES.json`
中附带生成的依赖材料。

上游源码修订与容器镜像摘要固定在 `config/upstreams.json` 和
`config/images.lock.json` 中。升级依赖时，应同步更新锁文件、声明、测试及
发布审计证据。

两个 Web 控制台使用同一固定版本 `0.6.2-canary.d72e4d6` 的 Astryx Core、
Neutral 和 Charts（MIT），StyleX 0.19.0（MIT），以及 Lucide React 1.18.0
（ISC，包含其附带的其他图标声明）。传递依赖的确切版本记录在各前端的
`package-lock.json` 中。

前端构建从打包依赖的许可证文件生成 `dist/THIRD_PARTY_NOTICES.txt`，并随静态
前端复制到发布产物。许可证正文缺失会使构建失败。用于补足 npm 包遗漏的固定
版本上游许可证副本见[共享 UI 包](packages/console-ui/README.zh-CN.md)。

## 上游协议栈与硬件工具链协议边界

本仓库自有代码与发布工具遵循 **Apache License 2.0**（[LICENSE](LICENSE)）。
在目标主机上独立拉取、编译或运行的外部上游组件——包括 **OCUDU**（`config/upstreams.json`）、
**Open5GS**（`config/images.lock.json`）、**Ettus UHD** 与 **pySim**——并未在
本仓库或控制台离线发布包中再分发，仍各自受其原始上游开源协议约束。
