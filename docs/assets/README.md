# Visual Assets, Photography and Rebranding Guide

This directory reserves standardized slots for **brand assets**, **hardware
photographs**, **redacted console screenshots**, and optional **vector
diagrams**. Placeholders inside active markdown docs currently use HTML
comments (`<!-- ASSET_SLOT: ... -->`) so automated link audits stay clean until
binary assets are captured.

## Reserved Directory Structure

```text
docs/assets/
├── README.md
├── brand/
│   ├── logo-light.png        # Horizontal OpenAirKit logo for light GitHub theme (active)
│   ├── logo-dark.png         # Horizontal OpenAirKit logo for dark GitHub theme (active)
│   └── hero-banner.png       # Optional 16:9 project header visual
├── hardware/
│   ├── kit-overview.jpg      # Full hardware stack overview (16:9, <=1200px wide)
│   ├── spark-b210-wiring.jpg # DGX Spark + USRP B210 USB 3.0 & RF wiring close-up
│   └── jetson-waveshare-rm520n.jpg # Jetson Orin + Waveshare carrier + RM520N-GL + SIM
├── screenshots/
│   ├── spark-console-overview.png  # Redacted Spark Platform (8877) Overview/Devices
│   └── jetson-console-overview.png # Redacted Jetson Console (8878) Overview/Setup
└── diagrams/                 # Optional exported .svg / .excalidraw / .drawio sources
```

## Project Name & Hero Logo (`docs/assets/brand/`)

Both root READMEs render the light/dark transparent PNG logos from
`docs/assets/brand/` via a centered `<picture>` block (optional `.svg` vector
upgrades can drop into the same paths):

```html
<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/brand/logo-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="docs/assets/brand/logo-light.png">
  <img src="docs/assets/brand/logo-light.png" alt="OpenAirKit" width="540">
</picture>

</div>
```

### Brand Decoupling Matrix

Keep **display branding** (`OpenAirKit`) separate from **runtime system
identifiers** so visual updates do not break deployed hosts or systemd units:

| Layer | Examples | Rebranding Impact |
| --- | --- | --- |
| **Display Brand Name & Visuals** | Hero title, SVG logo, badges, overview descriptions | Update `README.md`, `README.zh-CN.md`, `docs/README*.md`, `docs/architecture*.md`, `docs/hardware-and-topology*.md`, `docs/quickstart*.md`, `docs/ai-customization*.md`, `docs/assets/brand/` |
| **Component Role Names** | `Spark Platform`, `Jetson Console`, `5G SA Stack` | Keep stable across prose (`L1`/`L2`/`L3` guides) to minimize cross-file coupling |
| **Stable System Identifiers** | `aoc-v2ctl`, `aoc-maintain`, `/opt/agentic-ocudu/`, `aoc-v2-*.service`, `aoc_jetson`, `aoc_spark` | Do **not** rename silently in docs without a coordinated code + package release |

## Registered `ASSET_SLOT` Placements

| Slot File | Document Location | Composition & Guidelines |
| --- | --- | --- |
| `docs/assets/brand/logo-{light,dark}.png` | Top of `README.md` / `README.zh-CN.md` (active) | Transparent PNG (`887x180`), legible in both light & dark GitHub themes |
| `docs/assets/hardware/kit-overview.jpg` | `README` & `hardware-and-topology` | `16:9` flat-lay or benchtop shot showing DGX Spark, B210, Jetson Orin, Waveshare M.2 carrier + RM520N-GL, antennas and SIM reader (`<= 1200px` wide, `< 400 KB`) |
| `docs/assets/hardware/spark-b210-wiring.jpg` | `hardware-and-topology` | Close-up showing direct USB 3.0 connection and `n78` antennas / SMA attenuators |
| `docs/assets/hardware/jetson-waveshare-rm520n.jpg` | `hardware-and-topology` | Close-up showing RM520N-GL seated in Waveshare M.2 carrier, Nano-SIM orientation, and 4x SMA RF pigtails |
| `docs/assets/screenshots/spark-console-overview.png` | `spark-operations` | Light/neutral UI capture showing Overview / Devices state with live `8879` telemetry (`<= 1440px` wide) |
| `docs/assets/screenshots/jetson-console-overview.png` | `jetson-operations` | Light/neutral UI capture showing Overview / Device Setup verified state (`<= 1440px` wide) |

## Mandatory Privacy & Redaction Checklist

Before committing any photo or screenshot under `docs/assets/`, confirm that
none of the following appear visibly (crop, blur, or redact cleanly):

- IMSI, ICCID, Ki, OPc, PIN/PUK, or console passwords;
- Tailnet (`100.x.x.x`) or private institutional IPv4/IPv6 addresses;
- Real lab hostnames, SSH usernames (`/home/<user>`), Wi-Fi SSIDs, or browser bookmarks/tabs;
- Device serial barcodes/MAC stickers on DGX Spark, USRP B210, Jetson Orin, or RM520N-GL.
