# Visual Assets, Photography and Rebranding Guide

This directory maintains standardized paths for **brand assets**, **hardware
visuals**, **redacted console screenshots**, and optional **vector diagrams**.
Pending field photographs and redacted console screenshots are tracked in the
asset inventory table below until capture and redaction are complete.

## Directory Layout

```text
docs/assets/
├── README.md
├── brand/
│   ├── logo-light.png        # Horizontal OpenAirKit logo for light GitHub theme (active)
│   ├── logo-dark.png         # Horizontal OpenAirKit logo for dark GitHub theme (active)
│   └── hero-banner.png       # Optional 16:9 project header visual
├── hardware/
│   ├── dgx-spark.webp              # DGX Spark base-station & core host (active)
│   ├── usrp-b210.webp              # Ettus USRP B210 SDR board (active)
│   ├── jetson-orin-nano.webp       # NVIDIA Jetson Orin Nano UE host (active)
│   ├── waveshare-m2-5g-carrier.webp # Waveshare M.2 5G expansion board for Jetson Orin (active)
│   ├── quectel-rm520n-gl.webp      # Quectel RM520N-GL 5G NR module (active)
│   ├── programmable-5g-usim.webp   # Programmable 5G USIM test cards (active)
│   ├── pcsc-smartcard-reader.webp  # USB CCID/PC/SC smartcard reader (active)
│   ├── kit-overview.webp           # Benchtop Hardware Topology Overview (16:9, 1024x576, active)
│   ├── spark-b210-wiring.jpg       # DGX Spark + USRP B210 USB 3.0 & RF wiring close-up
│   └── jetson-waveshare-rm520n.jpg # Jetson Orin + Waveshare carrier + RM520N-GL + SIM
├── screenshots/
│   ├── spark-console-overview.png  # Redacted Spark Console (8877) Overview/Devices
│   └── jetson-console-overview.png # Redacted Jetson Console (8878) Overview/Setup
└── diagrams/
    ├── generate.py                                    # Deterministic Light/Dark SVG generator (pure stdlib)
    ├── system-architecture-{en,zh}-{light,dark}.svg
    ├── three-plane-architecture-{en,zh}-{light,dark}.svg
    ├── deployment-flow-{en,zh}-{light,dark}.svg
    ├── hardware-topology-{en,zh}-{light,dark}.svg
    ├── ai-closed-loop-{en,zh}-{light,dark}.svg
    └── jetson-state-machine-{en,zh}-{light,dark}.svg
```

## Project Name & Hero Logo (`docs/assets/brand/`)

Both root READMEs render theme-aware transparent PNG logos from
`docs/assets/brand/` inside a centered `<picture>` container (optional `.svg`
vector replacements can be placed at the same paths without modifying Markdown
references):

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

Keep **display branding** (`OpenAirKit`) decoupled from **runtime system
identifiers** so visual updates never break deployed hosts or systemd units:

| Layer | Examples | Rebranding Impact |
| --- | --- | --- |
| **Display Brand Name & Visuals** | Hero title, SVG/PNG logo, badges, overview descriptions | Update `README.md`, `README.zh-CN.md`, `docs/README*.md`, `docs/architecture*.md`, `docs/hardware-and-topology*.md`, `docs/quickstart*.md`, `docs/ai-customization*.md`, `docs/assets/brand/` |
| **Component Role Names** | `Spark Console`, `Jetson Console`, `5G SA Stack` | Keep consistent across all guides to minimize cross-file drift |
| **Immutable Runtime Identifiers** | `aoc-v2ctl`, `aoc-maintain`, `/opt/agentic-ocudu/`, `aoc-v2-*.service`, `aoc_jetson`, `aoc_spark` | Do **not** rename in docs without a coordinated code and package release |

## Registered Visual Assets & Pending Captures

| Asset / Slot File | Document Location | Composition & Guidelines |
| --- | --- | --- |
| `docs/assets/brand/logo-{light,dark}.png` | Top of `README.md` / `README.zh-CN.md` (active) | Transparent PNG (`887x180`), legible in both light & dark GitHub themes |
| `docs/assets/hardware/*.webp` (`7` files) | `README*`, `hardware-and-topology*`, `sim-provisioning*`, `setup-bs-spark*`, `setup-ue-jetson*` (active) | Standardized WebP hardware visuals (`dgx-spark`, `usrp-b210`, `jetson-orin-nano`, `waveshare-m2-5g-carrier`, `quectel-rm520n-gl`, `programmable-5g-usim`, `pcsc-smartcard-reader`) rendered in proportional bounding boxes |
| `docs/assets/hardware/kit-overview.webp` | `README*` & `hardware-and-topology*` (active) | `16:9` Benchtop Hardware Topology Overview (`1024x576`) showing Jetson Orin + Waveshare M.2 carrier + RM520N-GL, DGX Spark + USRP B210, and live Spark Console |
| `docs/assets/diagrams/*-{en,zh}-{light,dark}.svg` (`24` files + `generate.py`) | `README*`, `architecture*`, `quickstart*`, `hardware-and-topology*`, `ai-customization*`, `jetson-operations*` (active) | Theme-aware Light/Dark vector diagrams generated deterministically by `docs/assets/diagrams/generate.py` for System Architecture, Three-Plane Architecture, Deployment Flow, Hardware Topology, AI Closed-Loop, and Jetson Routing & Recovery State Machine |
| `docs/assets/hardware/spark-b210-wiring.jpg` | `hardware-and-topology*` | Close-up showing direct USB 3.0 connection and Band `n78` antennas / SMA attenuators |
| `docs/assets/hardware/jetson-waveshare-rm520n.jpg` | `hardware-and-topology*` | Close-up showing RM520N-GL seated in Waveshare M.2 carrier, Nano-SIM orientation, and 4x SMA RF pigtails |
| `docs/assets/screenshots/spark-console-overview.png` | `spark-operations*` | Light/neutral UI capture showing Overview / Devices state with live `8879` telemetry (`<= 1440px` wide) |
| `docs/assets/screenshots/jetson-console-overview.png` | `jetson-operations*` | Light/neutral UI capture showing Overview / Device Setup verified state (`<= 1440px` wide) |

## Mandatory Privacy & Redaction Checklist

Before committing any photograph or screenshot under `docs/assets/`, confirm that
none of the sensitive identifiers below remain legible (crop, blur, or redact):

- IMSI, ICCID, Ki, OPc, PIN/PUK, or console passwords;
- Tailnet (`100.x.x.x`) or private institutional IPv4/IPv6 addresses;
- Internal hostnames, SSH usernames (`/home/<user>`), Wi-Fi SSIDs, or browser bookmarks/tabs;
- Device serial barcodes or MAC address labels on DGX Spark, USRP B210, Jetson Orin, or RM520N-GL.
