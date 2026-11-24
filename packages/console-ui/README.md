# Shared console UI

[简体中文](README.zh-CN.md)

Both consoles use the official Astryx Core components, Neutral theme and Charts.
Application pages and domain state mappings remain in their respective apps.
`layout.css` contains document sizing, content width, wrapping and spacing only;
it must not override component appearance. Do not add a parallel control library,
copy Astryx component implementations, or draw replacement controls in CSS/SVG.

Each app's `UIProvider` connects the official theme and `LinkProvider` to React
Router, and both frontend lock files pin the same Astryx revision.

`licenses.mjs` is a build-only Vite plugin that emits `THIRD_PARTY_NOTICES.txt`
for dependencies included in the bundle. Existing release staging copies this
asset with `dist/`. Missing license text fails the build. Pinned fallback copies
cover omissions in the published Core and StyleX tarballs:

- [Astryx d72e4d6 license](https://github.com/facebook/astryx/blob/d72e4d6/LICENSE)
- [StyleX 0.19.0 source license](https://github.com/facebook/stylex/blob/5f51b24444abced04b213726977b9d67339bb26d/LICENSE)

When updating dependencies, refresh both locks, any version-specific fallback
license and the browser regression evidence together.
