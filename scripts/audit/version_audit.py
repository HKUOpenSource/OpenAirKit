"""Audit version and shared dependency parity across separated consoles."""

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
PY_VERSION = re.compile(r'^__version__\s*=\s*"([^"]+)"', re.MULTILINE)
PY_LOCK_PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s;]+)$")


def read_root_version() -> str:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not SEMVER.fullmatch(version):
        raise SystemExit(f"invalid root VERSION format: {version!r}")
    return version


def check_versions(version: str) -> None:
    backends = (
        ROOT / "apps/jetson-console/backend/aoc_jetson/__init__.py",
        ROOT / "apps/spark-console/backend/aoc_spark/__init__.py",
    )
    for path in backends:
        match = PY_VERSION.search(path.read_text(encoding="utf-8"))
        actual = match.group(1) if match else None
        if actual != version:
            raise SystemExit(f"version mismatch in {path.relative_to(ROOT)}: {actual!r} != {version!r}")

    manifests = (
        ROOT / "apps/jetson-console/frontend/package.json",
        ROOT / "apps/spark-console/frontend/package.json",
        ROOT / "packages/console-ui/package.json",
    )
    for path in manifests:
        actual = json.loads(path.read_text(encoding="utf-8")).get("version")
        if actual != version:
            raise SystemExit(f"version mismatch in {path.relative_to(ROOT)}: {actual!r} != {version!r}")

    lockfiles = (
        ROOT / "apps/jetson-console/frontend/package-lock.json",
        ROOT / "apps/spark-console/frontend/package-lock.json",
    )
    for path in lockfiles:
        data = json.loads(path.read_text(encoding="utf-8"))
        top = data.get("version")
        root_pkg = data.get("packages", {}).get("", {}).get("version")
        if top != version or root_pkg != version:
            raise SystemExit(
                f"lockfile root version mismatch in {path.relative_to(ROOT)}: "
                f"top={top!r}, root={root_pkg!r}, expected={version!r}"
            )

    for rel in ("README.md", "README.zh-CN.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        expected_tokens = (
            f"Spark Console: {version}",
            f"Spark_Console-{version}-blue",
            f"Jetson Console: {version}",
            f"Jetson_Console-{version}-blue",
        )
        for token in expected_tokens:
            if token not in text:
                raise SystemExit(f"missing version badge {token!r} in {rel}")

    for rel in ("docs/releasing.md", "docs/releasing.zh-CN.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        if f"`{version}`" not in text:
            raise SystemExit(f"missing unified version `{version}` in {rel}")


def parse_python_lock(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        spec = line.split(";", 1)[0].strip()
        match = PY_LOCK_PIN.fullmatch(spec)
        if not match:
            raise SystemExit(f"unpinned or unsupported entry in {path.relative_to(ROOT)}: {raw!r}")
        name = re.sub(r"[-_.]+", "-", match.group(1)).lower()
        pins[name] = match.group(2)
    return pins


def check_shared_python_pins() -> None:
    jetson = parse_python_lock(ROOT / "apps/jetson-console/requirements-jetson.lock")
    spark = parse_python_lock(ROOT / "apps/spark-console/requirements-spark.lock")
    mismatches = [
        f"{pkg}: jetson={jetson[pkg]} spark={spark[pkg]}"
        for pkg in sorted(set(jetson) & set(spark))
        if jetson[pkg] != spark[pkg]
    ]
    if mismatches:
        raise SystemExit("shared Python lockfile pin drift: " + "; ".join(mismatches))


def check_shared_npm_pins() -> None:
    jetson = json.loads((ROOT / "apps/jetson-console/frontend/package.json").read_text(encoding="utf-8"))
    spark = json.loads((ROOT / "apps/spark-console/frontend/package.json").read_text(encoding="utf-8"))
    for section in ("dependencies", "devDependencies"):
        j_deps = jetson.get(section, {})
        s_deps = spark.get(section, {})
        mismatches = [
            f"{section}.{pkg}: jetson={j_deps[pkg]} spark={s_deps[pkg]}"
            for pkg in sorted(set(j_deps) & set(s_deps))
            if j_deps[pkg] != s_deps[pkg]
        ]
        if mismatches:
            raise SystemExit("shared npm dependency drift: " + "; ".join(mismatches))


def main() -> None:
    version = read_root_version()
    check_versions(version)
    check_shared_python_pins()
    check_shared_npm_pins()
    print(f"Version and dependency parity audit passed ({version})")


if __name__ == "__main__":
    main()
