"""Audit the current Agentic-OCUDU documentation boundary."""

from pathlib import Path
from urllib.parse import unquote
import re


ROOT = Path(__file__).resolve().parents[2]
DOC_ROOT = ROOT / "docs"
ROOT_DOCUMENTS = (
    "README.md",
    "README.zh-CN.md",
    "CONTRIBUTING.md",
    "CONTRIBUTING.zh-CN.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "THIRD_PARTY_NOTICES.md",
    "AGENTS.md",
)
PAIRED_DOCUMENTS = (
    "README",
    "architecture",
    "hardware-and-topology",
    "quickstart",
    "sim-provisioning",
    "ai-customization",
    "coding-agent-codegraph",
    "setup-ue-jetson",
    "setup-bs-spark",
    "jetson-operations",
    "spark-operations",
    "troubleshooting-ue-jetson",
    "troubleshooting-bs-spark",
    "releasing",
    "roadmap",
    "reference/network-and-rf-profile",
    "reference/ports-and-runtime",
    "reference/api-reference",
    "reference/hardware-notes",
    "reference/glossary",
)
STALE_PATH = re.compile(r"(?:^|[\s`(/])(?:modules/|deploy-v2(?:/|\b)|aoc_monitor\b|aoc_jetson_v2\b)")
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
# Current documentation must stand on its own and may not name the retired
# reference project. Keeping this token assembled avoids making the audit
# source itself look like project documentation to repository-wide scans.
FORBIDDEN_REFERENCE = "biver" + "ge"
PUBLIC_HYGIENE_PATTERNS = (
    ("local user home path", re.compile(r"(?<![A-Za-z0-9_<])/home/(?!<user>)[a-z0-9][a-z0-9_-]*")),
    (
        "internal PR or agent template phrasing",
        re.compile(r"(?:The question is|Validation for this change|No \.?[Cc]ode[Gg]raph index)"),
    ),
    ("hardware or stack typo", re.compile(r"\b(?:RM250N|OCUCU)\b", re.IGNORECASE)),
    ("vendor binary hash or reverse-engineering symbol", re.compile(r"(?:GRSIMWrite\.exe|RadLTE_)")),
    ("Jetson Console misnamed as OCUDU", re.compile(r"\b(?:stop\s+OCUDU|full\s+OCUDU|OCUDU\s+validates)\b")),
    ("retired telemetry port", re.compile(r"127\.0\.0\.1:8001\b")),
    ("retired Spark console directory", re.compile(r"\bspark-platform\b")),
)
HYGIENE_EXEMPT_PREFIXES = ("docs/acceptance/",)
HYGIENE_EXEMPT_FILES = {
    "CHANGELOG.md",
    "docs/coding-agent-codegraph.md",
    "docs/coding-agent-codegraph.zh-CN.md",
}


def current_documents() -> list[Path]:
    documents = [ROOT / name for name in ROOT_DOCUMENTS]
    documents.extend(sorted(DOC_ROOT.rglob("*.md")))
    for area in ("apps", "deploy", "packages", "stacks"):
        for path in sorted((ROOT / area).rglob("README.md")):
            if any(part in {"node_modules", "dist", "build", ".venv"} for part in path.parts):
                continue
            documents.append(path)
    return list(dict.fromkeys(documents))


def check_pairs() -> None:
    for stem in PAIRED_DOCUMENTS:
        base = ROOT if stem == "README" else DOC_ROOT
        english = base / f"{stem}.md"
        chinese = base / f"{stem}.zh-CN.md"
        for path in (english, chinese):
            if not path.is_file():
                raise SystemExit(f"missing documentation pair: {path.relative_to(ROOT)}")


def github_slug(heading: str) -> str:
    slug = heading.strip().lower()
    slug = slug.replace("`", "")
    slug = re.sub(r"[^\w\s\-\u4e00-\u9fff]", "", slug)
    return re.sub(r"\s+", "-", slug)


def heading_anchors(path: Path) -> set[str]:
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^#{1,6}\s+(.+)$", line)
        if not match:
            continue
        slug = github_slug(match.group(1))
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        anchors.add(slug if count == 0 else f"{slug}-{count}")
    return anchors


def check_links(path: Path, text: str) -> None:
    rel_path = str(path.relative_to(ROOT))
    check_fragments = not any(rel_path.startswith(prefix) for prefix in HYGIENE_EXEMPT_PREFIXES)
    for raw_target in LINK.findall(text):
        target = raw_target.strip().split()[0].strip("<>")
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        relative, _, fragment = target.partition("#")
        relative = unquote(relative)
        resolved = path if not relative else (path.parent / relative).resolve()
        try:
            resolved.relative_to(ROOT)
        except ValueError as error:
            raise SystemExit(f"documentation link escapes repository: {path}: {target}") from error
        if not resolved.exists():
            raise SystemExit(
                f"broken documentation link: {rel_path} -> {target}"
            )
        if check_fragments and fragment and resolved.is_file():
            decoded_fragment = unquote(fragment)
            if decoded_fragment not in heading_anchors(resolved):
                raise SystemExit(
                    f"broken documentation anchor: {rel_path} -> {target}"
                )


def check_public_hygiene(rel: str, text: str) -> None:
    if rel in HYGIENE_EXEMPT_FILES or any(rel.startswith(prefix) for prefix in HYGIENE_EXEMPT_PREFIXES):
        return
    for label, pattern in PUBLIC_HYGIENE_PATTERNS:
        match = pattern.search(text)
        if match:
            raise SystemExit(f"public release hygiene failure ({label}) in {rel}: {match.group(0)!r}")


def main() -> None:
    check_pairs()
    documents = current_documents()
    for path in documents:
        if not path.is_file():
            raise SystemExit(f"missing canonical document: {path.relative_to(ROOT)}")
        rel = str(path.relative_to(ROOT))
        text = path.read_text(encoding="utf-8")
        if FORBIDDEN_REFERENCE in text.casefold():
            raise SystemExit(f"external project reference in {rel}")
        if STALE_PATH.search(text):
            raise SystemExit(f"retired path in {rel}")
        check_links(path, text)
        check_public_hygiene(rel, text)
    print(f"Documentation audit passed ({len(documents)} current documents)")


if __name__ == "__main__":
    main()
