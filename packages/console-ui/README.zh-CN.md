# 控制台共享 UI

[English](README.md)

两个控制台均使用 Astryx 官方 Core 组件、Neutral 主题和 Charts。
页面与领域状态映射仍放在各自应用中。`layout.css` 只负责文档尺寸、内容宽度、
换行与间距，不覆盖组件外观。不引入另一套控件库、不复制 Astryx 组件实现，
也不使用自绘 CSS/SVG 替代控件。

各应用通过 `UIProvider` 将官方主题与 `LinkProvider` 接入 React Router。
两个前端锁文件固定同一 Astryx 修订版本。组件映射、兼容性与验证记录见
[迁移记录](../../docs/acceptance/2026-09-23-astryx-ui.zh-CN.md)。

`licenses.mjs` 是仅用于构建的 Vite 插件，为打包依赖生成
`THIRD_PARTY_NOTICES.txt`。现有发布打包流程会随 `dist/` 复制此文件。
缺少许可证正文时构建失败。以下固定版本的上游许可证副本用于补足 Core 和
StyleX 已发布 npm 包的遗漏：

- [Astryx d72e4d6 许可证](https://github.com/facebook/astryx/blob/d72e4d6/LICENSE)
- [StyleX 0.19.0 源码许可证](https://github.com/facebook/stylex/blob/5f51b24444abced04b213726977b9d67339bb26d/LICENSE)

升级依赖时，应同步更新两端锁文件、对应版本的许可证副本与浏览器回归记录。
