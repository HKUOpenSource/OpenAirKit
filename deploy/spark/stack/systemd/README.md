# Stack service definitions

[简体中文](README.zh-CN.md)

The stack package installs `aoc-v2-core.service` and `aoc-v2-radio.service`.
Core is a oneshot service with retained active state; radio requires and binds to
core, runs the gNB as its main process and checks current N2 setup after launch.
Neither unit has an Install section or enables boot startup. Monitor services are
packaged independently. See the [stack package guide](../README.md).

Installation verifies staged unit syntax with staged executable paths, then writes
the fixed installed paths. Local tests replace systemd/Docker commands with inert
functions; target systemd and RF behavior remain unverified by these tests.
