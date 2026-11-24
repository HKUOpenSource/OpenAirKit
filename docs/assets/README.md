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
│   ├── logo-light.svg        # Horizontal logo for light GitHub theme
│   ├── logo-dark.svg         # Horizontal logo for dark GitHub theme
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

## Replacing the Project Name & Hero Logo

When the final public project name and logos are ready, drop `logo-light.svg`
and `logo-dark.svg` into `docs/assets/brand/` and replace the hero `ASSET_SLOT`
comment in [README.md](../../README.md) and [README.zh-CN.md](../../README.zh-CN.md)
with a centered `<picture>` block:

```html
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/brand/logo-dark.svg" />
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/brand/logo-light.svg" />
    <img alt="Project Logo" src="docs/assets/brand/logo-light.svg" width="420" />
  </picture>
</p>
```

### Brand Decoupling Matrix

Keep **display branding** separate from **runtime system identifiers** so
rebranding does not break deployed hosts or systemd units:

| Layer | Examples | Rebranding Impact |
| --- | --- | --- |
| **Display Brand Name & Visuals** | Hero title, SVG logo, badges, overview descriptions | Update `README.md`, `README.zh-CN.md`, `docs/README*.md`, `docs/architecture*.md`, `docs/hardware-and-topology*.md`, `docs/quickstart*.md`, `docs/ai-customization*.md`, `docs/assets/brand/` |
| **Component Role Names** | `Spark Platform`, `Jetson Console`, `5G SA Stack` | Keep stable across prose (`L1`/`L2`/`L3` guides) to minimize cross-file coupling |
| **Stable System Identifiers** | `aoc-v2ctl`, `aoc-maintain`, `/opt/agentic-ocudu/`, `aoc-v2-*.service`, `aoc_jetson`, `aoc_spark` | Do **not** rename silently in docs without a coordinated code + package release |

## Registered `ASSET_SLOT` Placements

| Slot File | Document Location | Composition & Guidelines |
| --- | --- | --- |
| `docs/assets/brand/logo-{light,dark}.svg` | Top of `README.md` / `README.zh-CN.md` | Vector SVG, transparent background, legible in both light & dark themes |
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
