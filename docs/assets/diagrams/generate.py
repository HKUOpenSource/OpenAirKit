#!/usr/bin/env python3
"""Generate deterministic light/dark SVG architecture and deployment diagrams.

All output SVGs use transparent outer backgrounds and left-rail band containers
so inter-layer connectors never cross container title labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

OUT_DIR = Path(__file__).resolve().parent

FONT_FAMILY = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', "
    "'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"
)


@dataclass(frozen=True)
class Theme:
    name: str
    band_bg: str
    band_border: str
    rail_bg: str
    rail_text: str
    rail_subtext: str
    styles: dict[str, tuple[str, str, str, str | None]]  # fill, stroke, text, dasharray
    solid_line: str
    dashed_line: str
    rf_line: str
    pill_bg: str
    pill_border: str
    pill_text: str


THEMES: dict[str, Theme] = {
    "light": Theme(
        name="light",
        band_bg="#f8fafc",
        band_border="#cbd5e1",
        rail_bg="#f1f5f9",
        rail_text="#1e293b",
        rail_subtext="#475569",
        styles={
            "hw": ("#f1f5f9", "#475569", "#0f172a", None),
            "stack": ("#ecfdf5", "#047857", "#064e3b", None),
            "mgmt": ("#eff6ff", "#1d4ed8", "#1e3a8a", None),
            "ai": ("#fefce8", "#a16207", "#713f12", "6 4"),
        },
        solid_line="#475569",
        dashed_line="#64748b",
        rf_line="#0f766e",
        pill_bg="#ffffff",
        pill_border="#cbd5e1",
        pill_text="#334155",
    ),
    "dark": Theme(
        name="dark",
        band_bg="#161b22",
        band_border="#30363d",
        rail_bg="#1c2128",
        rail_text="#e6edf3",
        rail_subtext="#8b949e",
        styles={
            "hw": ("#1e293b", "#94a3b8", "#f1f5f9", None),
            "stack": ("#052e2b", "#34d399", "#d1fae5", None),
            "mgmt": ("#172554", "#60a5fa", "#dbeafe", None),
            "ai": ("#422006", "#facc15", "#fef9c3", "6 4"),
        },
        solid_line="#94a3b8",
        dashed_line="#8b949e",
        rf_line="#2dd4bf",
        pill_bg="#0d1117",
        pill_border="#30363d",
        pill_text="#e6edf3",
    ),
}


def estimate_text_width(text: str) -> float:
    """Estimate rendered pixel width at 11.5-12px sans-serif for pill sizing."""
    total = 0.0
    for ch in text:
        code = ord(ch)
        if code > 0x2E7F:  # CJK and full-width punctuation
            total += 12.6
        elif ch in "MW@#%&":
            total += 9.5
        elif ch in "ilI1.,:;|/ ":
            total += 4.5
        else:
            total += 7.2
    return total


class SvgBuilder:
    def __init__(self, width: int, height: int, theme: Theme, role_desc: str) -> None:
        self.width = width
        self.height = height
        self.theme = theme
        self.role_desc = role_desc
        self.defs: list[str] = []
        self.layers: list[str] = []
        self.nodes: list[str] = []
        self.edges: list[str] = []
        self.pills: list[str] = []
        self._clip_idx = 0
        self._add_markers()

    def _add_markers(self) -> None:
        t = self.theme
        self.defs.extend(
            [
                (
                    f'<marker id="arrow-solid" markerUnits="userSpaceOnUse" '
                    f'markerWidth="10" markerHeight="10" refX="7" refY="5" orient="auto">'
                    f'<path d="M 1 1.5 L 9 5 L 1 8.5 Z" fill="{t.solid_line}" />'
                    f"</marker>"
                ),
                (
                    f'<marker id="arrow-dashed" markerUnits="userSpaceOnUse" '
                    f'markerWidth="10" markerHeight="10" refX="7" refY="5" orient="auto">'
                    f'<path d="M 1 1.5 L 9 5 L 1 8.5 Z" fill="{t.dashed_line}" />'
                    f"</marker>"
                ),
                (
                    f'<marker id="arrow-rf-end" markerUnits="userSpaceOnUse" '
                    f'markerWidth="10" markerHeight="10" refX="7" refY="5" orient="auto">'
                    f'<path d="M 1 1.5 L 9 5 L 1 8.5 Z" fill="{t.rf_line}" />'
                    f"</marker>"
                ),
                (
                    f'<marker id="arrow-rf-start" markerUnits="userSpaceOnUse" '
                    f'markerWidth="10" markerHeight="10" refX="3" refY="5" orient="auto">'
                    f'<path d="M 9 1.5 L 1 5 L 9 8.5 Z" fill="{t.rf_line}" />'
                    f"</marker>"
                ),
            ]
        )

    def add_band(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        rail_w: int,
        title_lines: list[str],
        subtitle: str | None = None,
    ) -> None:
        t = self.theme
        self._clip_idx += 1
        clip_id = f"band-clip-{self._clip_idx}"
        self.defs.append(
            f'<clipPath id="{clip_id}">'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" ry="10" />'
            f"</clipPath>"
        )
        # Band background + clipped rail + border + divider
        parts = [
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" ry="10" '
            f'fill="{t.band_bg}" stroke="{t.band_border}" stroke-width="1.2" />',
            f'<rect x="{x}" y="{y}" width="{rail_w}" height="{h}" '
            f'fill="{t.rail_bg}" clip-path="url(#{clip_id})" />',
            f'<line x1="{x + rail_w}" y1="{y}" x2="{x + rail_w}" y2="{y + h}" '
            f'stroke="{t.band_border}" stroke-width="1" />',
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" ry="10" '
            f'fill="none" stroke="{t.band_border}" stroke-width="1.2" />',
        ]
        # Rail typography centered vertically & horizontally inside rail
        rail_cx = x + rail_w / 2
        line_step = 17
        sub_gap = 16 if subtitle else 0
        total_lines = len(title_lines) + (1 if subtitle else 0)
        block_h = (len(title_lines) - 1) * line_step + sub_gap
        center_y = y + h / 2
        start_y = center_y - block_h / 2 + 4

        for i, line in enumerate(title_lines):
            ly = start_y + i * line_step
            parts.append(
                f'<text x="{rail_cx:.1f}" y="{ly:.1f}" text-anchor="middle" '
                f'font-family="{FONT_FAMILY}" font-size="13" font-weight="600" '
                f'fill="{t.rail_text}">{escape(line)}</text>'
            )
        if subtitle:
            sy = start_y + (total_lines - 1) * line_step
            parts.append(
                f'<text x="{rail_cx:.1f}" y="{sy:.1f}" text-anchor="middle" '
                f'font-family="{FONT_FAMILY}" font-size="11" font-weight="400" '
                f'fill="{t.rail_subtext}">{escape(subtitle)}</text>'
            )
        self.layers.append("\n  ".join(parts))

    def add_node(self, x: int, y: int, w: int, h: int, style_key: str, lines: list[str]) -> None:
        fill, stroke, text_color, dasharray = self.theme.styles[style_key]
        dash_attr = f' stroke-dasharray="{dasharray}"' if dasharray else ""
        parts = [
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" ry="8" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.6"{dash_attr} />'
        ]
        cx = x + w / 2
        line_step = 17
        first_y = y + h / 2 - ((len(lines) - 1) * line_step) / 2 + 4.5
        for i, line in enumerate(lines):
            ly = first_y + i * line_step
            parts.append(
                f'<text x="{cx:.1f}" y="{ly:.1f}" text-anchor="middle" '
                f'font-family="{FONT_FAMILY}" font-size="13" font-weight="600" '
                f'fill="{text_color}">{escape(line)}</text>'
            )
        self.nodes.append("\n  ".join(parts))

    def add_line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        kind: str = "solid",
        arrow_end: bool = False,
        arrow_start: bool = False,
    ) -> None:
        t = self.theme
        if kind == "rf":
            color = t.rf_line
            width = 2.6
            dash = ""
            m_end = ' marker-end="url(#arrow-rf-end)"' if arrow_end else ""
            m_start = ' marker-start="url(#arrow-rf-start)"' if arrow_start else ""
        elif kind == "dashed":
            color = t.dashed_line
            width = 1.6
            dash = ' stroke-dasharray="5 4"'
            m_end = ' marker-end="url(#arrow-dashed)"' if arrow_end else ""
            m_start = ""
        else:
            color = t.solid_line
            width = 1.6
            dash = ""
            m_end = ' marker-end="url(#arrow-solid)"' if arrow_end else ""
            m_start = ""

        # Shorten ends by 2px when arrowheads are attached so stroke never blunts sharp tips
        dx = x2 - x1
        dy = y2 - y1
        length = (dx * dx + dy * dy) ** 0.5
        sx, sy, ex, ey = x1, y1, x2, y2
        if length > 0:
            ux, uy = dx / length, dy / length
            if arrow_start:
                sx += ux * 2.0
                sy += uy * 2.0
            if arrow_end:
                ex -= ux * 2.0
                ey -= uy * 2.0

        self.edges.append(
            f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" '
            f'stroke="{color}" stroke-width="{width}" stroke-linecap="butt"'
            f'{dash}{m_start}{m_end} />'
        )

    def add_path(self, d: str, kind: str = "solid", arrow_end: bool = True) -> None:
        t = self.theme
        if kind == "dashed":
            color = t.dashed_line
            dash = ' stroke-dasharray="5 4"'
            m_end = ' marker-end="url(#arrow-dashed)"' if arrow_end else ""
        else:
            color = t.solid_line
            dash = ""
            m_end = ' marker-end="url(#arrow-solid)"' if arrow_end else ""

        self.edges.append(
            f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.6" '
            f'stroke-linejoin="round"{dash}{m_end} />'
        )

    def add_pill(self, cx: float, cy: float, text: str) -> None:
        t = self.theme
        w = round(max(46.0, estimate_text_width(text) + 20.0), 1)
        h = 22.0
        x = round(cx - w / 2, 1)
        y = round(cy - h / 2, 1)
        self.pills.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="11" ry="11" '
            f'fill="{t.pill_bg}" stroke="{t.pill_border}" stroke-width="1" />\n  '
            f'<text x="{cx:.1f}" y="{cy + 4:.1f}" text-anchor="middle" '
            f'font-family="{FONT_FAMILY}" font-size="11.5" font-weight="500" '
            f'fill="{t.pill_text}">{escape(text)}</text>'
        )

    def render(self) -> str:
        sections = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}" '
            f'width="{self.width}" height="{self.height}" role="img" '
            f'aria-label="{escape(self.role_desc)}">',
            "  <defs>\n    " + "\n    ".join(self.defs) + "\n  </defs>",
            "  <!-- Layers -->\n  " + "\n  ".join(self.layers),
            "  <!-- Edges -->\n  " + "\n  ".join(self.edges),
            "  <!-- Nodes -->\n  " + "\n  ".join(self.nodes),
            "  <!-- Edge Labels -->\n  " + "\n  ".join(self.pills),
            "</svg>",
        ]
        return "\n".join(sections) + "\n"


def build_system_architecture(lang: str, theme: Theme) -> str:
    zh = lang == "zh"
    svg = SvgBuilder(
        880,
        560,
        theme,
        "OpenAirKit System Architecture" if not zh else "OpenAirKit 系统架构",
    )

    svg.add_band(
        16,
        16,
        848,
        88,
        206,
        ["ARM64 硬件栈"] if zh else ["ARM64 Hardware Stack"],
    )
    svg.add_band(
        16,
        160,
        848,
        88,
        206,
        ["5G SA 协议栈平面"] if zh else ["5G SA Protocol Plane"],
    )
    svg.add_band(
        16,
        304,
        848,
        88,
        206,
        ["本地优先管理平面"] if zh else ["Local-First", "Management Plane"],
    )
    svg.add_band(
        16,
        448,
        848,
        96,
        206,
        ["可编程 AI 扩展层"] if zh else ["Programmable AI", "Extension Layer"],
        "自定义算法与推理流水线" if zh else "(User-Defined Pipelines)",
    )

    # Nodes
    svg.add_node(244, 34, 180, 52, "hw", ["Jetson Orin +", "RM520N-GL"])
    svg.add_node(532, 34, 310, 52, "hw", ["DGX Spark + USRP B210"])

    svg.add_node(456, 178, 146, 52, "stack", ["OCUDU gNB"])
    svg.add_node(696, 178, 146, 52, "stack", ["Open5GS 5GC"])

    svg.add_node(244, 322, 180, 52, "mgmt", ["Jetson Console"])
    svg.add_node(456, 322, 386, 52, "mgmt", ["Spark Console"])

    svg.add_node(
        244,
        470,
        180,
        52,
        "ai",
        ["Jetson 端侧", "AI 运行环境"] if zh else ["Jetson Edge", "AI Runtime"],
    )
    svg.add_node(
        456,
        470,
        386,
        52,
        "ai",
        ["DGX Spark 网侧 AI 运行环境"] if zh else ["DGX Spark RAN-Side AI Runtime"],
    )

    # Intra-layer links
    svg.add_line(424, 60, 532, 60, kind="rf", arrow_start=True, arrow_end=True)
    svg.add_pill(478, 60, "5G NR SA")

    svg.add_line(602, 204, 696, 204, kind="solid", arrow_end=True)
    svg.add_pill(649, 204, "N2 / N3")

    # Vertical inter-layer links (straight, zero crossings)
    svg.add_line(334, 86, 334, 322, kind="solid")
    svg.add_line(566, 86, 566, 178, kind="solid")

    svg.add_line(529, 230, 529, 322, kind="dashed", arrow_end=True)
    svg.add_pill(529, 276, "无线指标" if zh else "Metrics")

    svg.add_line(769, 230, 769, 322, kind="dashed", arrow_end=True)
    svg.add_pill(769, 276, "网元与会话状态" if zh else "NF & Session State")

    svg.add_line(334, 374, 334, 470, kind="dashed")
    svg.add_pill(334, 422, "REST / SSE")

    svg.add_line(649, 374, 649, 470, kind="dashed")
    svg.add_pill(649, 422, "REST / SSE")

    return svg.render()


def build_three_plane_architecture(lang: str, theme: Theme) -> str:
    zh = lang == "zh"
    svg = SvgBuilder(
        920,
        432,
        theme,
        "Three-Plane Architecture" if not zh else "三平面架构",
    )

    svg.add_band(
        16,
        16,
        888,
        96,
        208,
        ["1. 5G SA 无线与", "核心网平面"] if zh else ["1. 5G SA Radio &", "Core Plane"],
    )
    svg.add_band(
        16,
        168,
        888,
        96,
        208,
        ["2. 本地管理与", "自愈平面"] if zh else ["2. Local Management", "& Self-Recovery Plane"],
    )
    svg.add_band(
        16,
        320,
        888,
        96,
        208,
        ["3. 可编程 AI 扩展层"] if zh else ["3. Programmable AI", "Extension Layer"],
        "自定义算法与推理流水线" if zh else "(User-Defined Pipelines)",
    )

    # Nodes
    svg.add_node(238, 38, 178, 52, "stack", ["Quectel RM520N-GL", "+ USIM"])
    svg.add_node(512, 38, 146, 52, "stack", ["OCUDU gNB", "+ USRP B210"])
    svg.add_node(754, 38, 136, 52, "stack", ["Open5GS 5GC"])

    svg.add_node(238, 190, 178, 52, "mgmt", ["Jetson Console"])
    svg.add_node(512, 190, 378, 52, "mgmt", ["Spark Console"])

    svg.add_node(
        238,
        342,
        178,
        52,
        "ai",
        ["Jetson 端侧", "AI 运行环境"] if zh else ["Jetson Edge", "AI Runtime"],
    )
    svg.add_node(
        512,
        342,
        378,
        52,
        "ai",
        ["DGX Spark 网侧 AI 运行环境"] if zh else ["DGX Spark RAN-Side AI Runtime"],
    )

    # Intra-layer links
    svg.add_line(416, 64, 512, 64, kind="rf", arrow_start=True, arrow_end=True)
    svg.add_pill(464, 64, "5G NR SA")

    svg.add_line(658, 64, 754, 64, kind="solid", arrow_end=True)
    svg.add_pill(706, 64, "N2 / N3")

    # Vertical inter-layer links
    svg.add_line(327, 90, 327, 190, kind="solid")

    svg.add_line(585, 90, 585, 190, kind="dashed", arrow_end=True)
    svg.add_pill(585, 140, "JSON 实时指标" if zh else "JSON Telemetry")

    svg.add_line(822, 90, 822, 190, kind="dashed", arrow_end=True)
    svg.add_pill(822, 140, "Docker 与 infoAPI" if zh else "Docker & infoAPI")

    svg.add_line(327, 242, 327, 342, kind="dashed")
    svg.add_pill(327, 292, "REST / SSE 与受控任务" if zh else "REST / SSE & Jobs")

    svg.add_line(701, 242, 701, 342, kind="dashed")
    svg.add_pill(701, 292, "REST / SSE 与受控操作" if zh else "REST / SSE & Control")

    return svg.render()


def build_deployment_flow(lang: str, theme: Theme) -> str:
    zh = lang == "zh"
    svg = SvgBuilder(
        920,
        540,
        theme,
        "Deployment Flow Across Hosts" if not zh else "跨主机全链路部署流程",
    )

    svg.add_band(16, 16, 888, 86, 174, ["1. 工作站"] if zh else ["1. Workstation"])
    svg.add_band(16, 156, 888, 86, 174, ["2. DGX Spark"])
    svg.add_band(16, 296, 888, 86, 174, ["3. 工作站"] if zh else ["3. Workstation"])
    svg.add_band(16, 436, 888, 86, 174, ["4. Jetson Orin"])

    # Nodes
    svg.add_node(
        340,
        33,
        240,
        52,
        "hw",
        ["构建 ARM64", "离线发布包"] if zh else ["Build ARM64", "Release Archives"],
    )
    svg.add_node(
        340,
        173,
        240,
        52,
        "stack",
        ["部署 5G 协议栈与", "Spark Console"] if zh else ["Deploy 5G Stack &", "Spark Console"],
    )
    svg.add_node(
        650,
        173,
        240,
        52,
        "stack",
        ["Open5GS 添加", "独立订阅"] if zh else ["Add Open5GS", "Subscriber"],
    )
    svg.add_node(
        650,
        313,
        240,
        52,
        "hw",
        ["烧录并校验", "5G USIM"] if zh else ["Program & Verify", "5G USIM"],
    )
    svg.add_node(
        340,
        453,
        240,
        52,
        "mgmt",
        ["安装并初始化", "Jetson Console"] if zh else ["Install & Commission", "Jetson Console"],
    )
    svg.add_node(
        650,
        453,
        240,
        52,
        "mgmt",
        ["执行 Device Setup", "并端到端验收"] if zh else ["Run Device Setup", "& Verify E2E"],
    )

    # Intra-stage links
    svg.add_line(580, 199, 650, 199, kind="solid", arrow_end=True)
    svg.add_line(580, 479, 650, 479, kind="solid", arrow_end=True)

    # Inter-stage links
    svg.add_line(460, 85, 460, 173, kind="solid", arrow_end=True)
    svg.add_line(770, 225, 770, 313, kind="solid", arrow_end=True)

    svg.add_path(
        "M 650 339 L 472 339 Q 460 339 460 351 L 460 451",
        kind="solid",
        arrow_end=True,
    )

    svg.add_path(
        "M 340 59 L 269 59 Q 257 59 257 71 L 257 467 Q 257 479 269 479 L 338 479",
        kind="dashed",
        arrow_end=True,
    )
    svg.add_pill(257, 269, "Jetson 发布包" if zh else "Jetson archive")

    return svg.render()


def main() -> None:
    builders = {
        "system-architecture": build_system_architecture,
        "three-plane-architecture": build_three_plane_architecture,
        "deployment-flow": build_deployment_flow,
    }
    generated = 0
    for stem, builder in builders.items():
        for lang in ("en", "zh"):
            for theme_name, theme in THEMES.items():
                out_path = OUT_DIR / f"{stem}-{lang}-{theme_name}.svg"
                out_path.write_text(builder(lang, theme), encoding="utf-8")
                generated += 1
    print(f"Generated {generated} SVG diagrams in {OUT_DIR}")


if __name__ == "__main__":
    main()
