# Jetson 故障排查

## Web 服务无法启动（`203/EXEC`、权限拒绝或 `8878` 端口冲突）

- **`127.0.0.1:8878` 端口占用**：执行 `ss -tlnp | grep 8878` 检查是否有旧版控制台服务
  仍在运行。若存在冲突单元，先 stop 并 disable 该冲突单元（可保留其程序目录用于回滚），
  再运行 `aoc-maintain start`。
- **`status=203/EXEC` 或读取 `web.json` 报 `PermissionError`**：在 `umask 077` 环境下
  运行旧版安装器时，可能将 `venv/` 建为 `0700` 或把 `/etc/aoc-v2-jetson/web.json`
  写为 `0600`。`0.6.2+` 的 `deploy/jetson/manage.py` 已对 `venv` 强制使用 `0o022` 掩码，
  并在 `private_write()` 中显式调用 `os.chmod(..., mode)`。若现场出现权限问题，检查并确保
  `venv` 对非特权用户可读可执行（无组/全局写权限），且 `web.json` 为 `0640 root:aoc-v2-jetson-web`。

## 执行器不可用或 USB 发现报错

先运行 `/usr/local/sbin/aoc-maintain status`（或 `manage.py status`），再检查
`journalctl -u aoc-v2-jetson-device.service`。确认发布路径存在、drop-in 目录
`/etc/systemd/system/aoc-v2-jetson-device.service.d` 权限为 `0755`，以及
`device.at_interface_number` 与当前 RM520N USB 拓扑一致：

- RNDIS 模式（`rndis_host` 位于 `00/01`，串口 `02..05`）须配置 `"04"`。
- ECM 模式（`cdc_ether` 位于 `04` 或 `0a`，串口 `00..03`）须配置 `"02"`。

若 `hardware.discover()` 提示 `Configured AT interface differs from USB layout; expected 02`
（或 `04`），应在停止服务后更新 `/etc/aoc-v2-jetson/device.json`；若已启用
`boot_connect.py`，更新配置或升级版本后还须同步刷新 `/etc/aoc-v2-jetson/boot.json`。

## 串口被占用

进入维护模式，停止当前持有者，并确认发现到的 AT 设备已释放（`fuser /dev/ttyUSB*`）。
执行器同时使用进程锁与串口排他打开；未检查进程就删除锁可能产生两个写入者。同时确认
`ModemManager.service` 处于 disabled/masked 状态。

## 注册或 PDU 失败

依次读取 SIM、服务小区、`C5GREG`、上下文定义、激活和地址证据。已注册但地址为
`0.0.0.0` 不代表数据会话有效。只有配置回读符合网络契约后才允许执行一次重连。

## 数据路径或诊断目标失败

确认当前模组接口、IPv4 地址、到配置探测目标的路由和受保护管理路由。探测必须绑定
该接口；未绑定的 ping 可能走 Wi-Fi，不能作为验收依据。分别查看注册、PDU、实验室
策略与管理保护；UPF 或 ext-DN 的 ping 失败不代表注册丢失。ext-DN 通过 TCP 8080
的 `/health` 返回固定小响应，不再提供测速监听。

## 开机协调器中止或拒绝重放

查看 `journalctl -u aoc-v2-jetson-boot.service` 与
`/var/lib/aoc-v2-jetson-boot/public/status.json`。常见原因包括升级应用后未同步更新
`/etc/aoc-v2-jetson/boot.json` 中的 `device_sha256` / `manifest_sha256`、先前启动失败
后出于安全考虑保留了 `maintenance=true` / `uncertain-selection.json` 等待人工核查，
或校园网管理网关触发 ICMP 限速。新版 `boot_connect.py` 在单包 `ping -c 1 -W 2`
未收到回包时会自动改用 `ping -c 3 -i 1 -W 2` 重试，并对已通过的网关连通状态缓存 `15.0 s`
（每次调用仍实时检查 `nmcli` 与 `inspect_management`）；若管理接口已关联但三包均被丢弃，
请检查上联网关的 ICMP 限速策略或 Wi-Fi 关联状态。
