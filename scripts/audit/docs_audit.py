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
    "INTERNAL_RELEASE.md",
    "CHANGELOG.md",
    "THIRD_PARTY_NOTICES.md",
    "AGENTS.md",
)
PAIRED_DOCUMENTS = (
    "README",
    "architecture",
    "coding-agent-codegraph",
    "setup-ue-jetson",
    "setup-bs-spark",
    "jetson-operations",
    "spark-operations",
    "troubleshooting-ue-jetson",
    "troubleshooting-bs-spark",
    "releasing",
)
STALE_PATH = re.compile(r"(?:^|[\s`(/])(?:modules/|deploy-v2(?:/|\b)|aoc_monitor\b|aoc_jetson_v2\b)")
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
# Current documentation must stand on its own and may not name the retired
# reference project. Keeping this token assembled avoids making the audit
# source itself look like project documentation to repository-wide scans.
FORBIDDEN_REFERENCE = "biver" + "ge"


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


def check_links(path: Path, text: str) -> None:
    for raw_target in LINK.findall(text):
        target = raw_target.strip().split()[0].strip("<>")
        if not target or target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        relative = unquote(target.split("#", 1)[0])
        if not relative:
            continue
        resolved = (path.parent / relative).resolve()
        try:
            resolved.relative_to(ROOT)
        except ValueError as error:
            raise SystemExit(f"documentation link escapes repository: {path}: {target}") from error
        if not resolved.exists():
            raise SystemExit(
                f"broken documentation link: {path.relative_to(ROOT)} -> {target}"
            )


def main() -> None:
    check_pairs()
    documents = current_documents()
    for path in documents:
        if not path.is_file():
            raise SystemExit(f"missing canonical document: {path.relative_to(ROOT)}")
        text = path.read_text(encoding="utf-8")
        if FORBIDDEN_REFERENCE in text.casefold():
            raise SystemExit(f"external project reference in {path.relative_to(ROOT)}")
        if STALE_PATH.search(text):
            raise SystemExit(f"retired path in {path.relative_to(ROOT)}")
        check_links(path, text)
    print(f"Documentation audit passed ({len(documents)} current documents)")


if __name__ == "__main__":
    main()
