"""Build-time validation for the two Linux ARM64 offline application releases."""
import hashlib
import json
from email.parser import BytesParser
from pathlib import Path
import subprocess
import sys
import tarfile
import zipfile

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.tags import compatible_tags, cpython_tags, parse_tag
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {"jetson": ("3.10", 35), "spark": ("3.12", 39)}


def environment(platform):
    python, _ = TARGETS[platform]
    return {**default_environment(), "python_version": python,
            "python_full_version": python + ".0", "implementation_name": "cpython",
            "implementation_version": python + ".0", "os_name": "posix",
            "sys_platform": "linux", "platform_system": "Linux",
            "platform_machine": "aarch64", "platform_python_implementation": "CPython",
            "extra": ""}


def platforms(platform):
    return [f"manylinux_2_{minor}_aarch64" for minor in range(TARGETS[platform][1], 16, -1)] + ["manylinux2014_aarch64"]


def locked_requirements(lock, platform):
    selected = {}
    for line in lock.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        requirement = Requirement(line)
        pins = list(requirement.specifier)
        if requirement.url or requirement.extras or len(pins) != 1 or pins[0].operator != "==" or "*" in pins[0].version:
            raise ValueError("Release dependencies must be exactly pinned: " + line)
        if requirement.marker and not requirement.marker.evaluate(environment(platform)):
            continue
        name = canonicalize_name(requirement.name)
        if name in selected:
            raise ValueError("Duplicate locked dependency: " + name)
        selected[name] = pins[0].version
    if not selected:
        raise ValueError("Empty dependency lock")
    return selected


def validate_wheels(directory, lock, platform):
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Wheelhouse must be a real directory")
    expected = locked_requirements(lock, platform)
    version = tuple(map(int, TARGETS[platform][0].split(".")))
    accepted = set(cpython_tags(version, platforms=platforms(platform)))
    accepted.update(compatible_tags(version, interpreter="cp" + "".join(map(str, version)), platforms=platforms(platform)))
    found, metadata = {}, []
    for path in directory.iterdir():
        if path.is_symlink() or not path.is_file() or path.suffix != ".whl":
            raise ValueError("Unexpected wheelhouse entry: " + path.name)
        name, release, _, tags = parse_wheel_filename(path.name)
        if name in found or name not in expected or release != Version(expected[name]) or not tags & accepted:
            raise ValueError("Wheel is duplicated, unlocked or incompatible with target: " + path.name)
        with zipfile.ZipFile(path) as wheel:
            records = [p for p in wheel.namelist() if p.endswith('.dist-info/METADATA')]
            if len(records) != 1 or wheel.testzip() is not None:
                raise ValueError("Invalid wheel metadata or checksum: " + path.name)
            info = BytesParser().parsebytes(wheel.read(records[0]))
            wheel_info = BytesParser().parsebytes(wheel.read(records[0].replace('/METADATA', '/WHEEL')))
            internal_tags = set()
            for tag in wheel_info.get_all('Tag', []):
                internal_tags.update(parse_tag(tag))
            if internal_tags != tags:
                raise ValueError("Wheel metadata tags differ from filename: " + path.name)
        if canonicalize_name(info["Name"] or "") != name or Version(info["Version"] or "0") != release:
            raise ValueError("Wheel metadata differs from filename: " + path.name)
        if not SpecifierSet(info.get("Requires-Python", "")).contains(TARGETS[platform][0] + ".0"):
            raise ValueError("Wheel requires a different Python: " + path.name)
        found[name] = str(release)
        metadata.append(info)
    if set(found) != set(expected):
        raise ValueError("Incomplete wheelhouse: " + ", ".join(sorted(set(expected) - set(found))))
    for info in metadata:
        for raw in info.get_all("Requires-Dist", []):
            dependency = Requirement(raw)
            if dependency.marker and not dependency.marker.evaluate(environment(platform)):
                continue
            name = canonicalize_name(dependency.name)
            if dependency.url or name not in found or not dependency.specifier.contains(found[name]):
                raise ValueError("Lock does not satisfy wheel dependency: " + raw)
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(directory.iterdir())}


def download_wheels(directory, lock, platform):
    if directory.exists() and any(directory.iterdir()):
        raise ValueError("Wheel download requires an empty directory")
    directory.mkdir(parents=True, exist_ok=True)
    arguments = [sys.executable, "-m", "pip", "download", "--only-binary=:all:",
                 "--no-deps", "--implementation", "cp", "--python-version", TARGETS[platform][0],
                 "--abi", "cp" + TARGETS[platform][0].replace(".", ""), "--dest", str(directory)]
    for target in platforms(platform):
        arguments += ["--platform", target]
    # Evaluate markers against the target, not the builder's Python version.
    arguments += [name + "==" + version for name, version in locked_requirements(lock, platform).items()]
    subprocess.run(arguments, check=True)
    return validate_wheels(directory, lock, platform)


def source_metadata(platform):
    return {"git_base": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
            "architecture": "aarch64", "python": TARGETS[platform][0],
            "product": "agentic-ocudu-" + platform}


def archive(stage, destination, platform):
    version = (stage / "RELEASE-VERSION").read_text().strip()
    Version(version)
    name = f"agentic-ocudu-{platform}-{version}-linux-arm64"
    target = destination / (name + ".tar.gz")
    if target.exists():
        raise FileExistsError(target)
    paths = sorted(stage.rglob("*"))
    if any(p.is_symlink() or not (p.is_file() or p.is_dir()) for p in paths):
        raise ValueError("Release contains a symlink or special file")
    with tarfile.open(target, "x:gz") as bundle:
        bundle.add(stage, arcname=name, recursive=False)
        for path in paths:
            bundle.add(path, arcname=name + "/" + path.relative_to(stage).as_posix(), recursive=False)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(target.suffix + ".sha256").write_text(digest + "  " + target.name + "\n")
    return target
