#!/usr/bin/env python3
"""Stage hash-verified upstream sources without modifying a host installation."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import urllib.request


ROOT = Path(__file__).resolve().parents[1]


def load_lock(path):
    lock = json.loads(Path(path).read_text())
    if lock.get("schema_version") != 1 or lock.get("platform") != "linux/arm64":
        raise ValueError("Unsupported source lock")
    expected = {"open5gs", "freeDiameter", "prometheus-client-c"}
    sources = lock.get("sources", [])
    if len(sources) != 3 or {s.get("name") for s in sources} != expected:
        raise ValueError("Incomplete source lock")
    for source in sources:
        if not re.fullmatch(r"[0-9a-f]{40}", source.get("commit", "")):
            raise ValueError("Source revision must be a commit")
        if not re.fullmatch(r"[0-9a-f]{64}", source.get("sha256", "")):
            raise ValueError("Source archive must have a SHA256")
        if source.get("repository") != "open5gs/" + source["name"]:
            raise ValueError("Unexpected source repository")
    for name, repository in (("ubuntu", "ubuntu"), ("mongodb", "mongo")):
        ref = lock.get("images", {}).get(name, {}).get("reference", "")
        if not re.fullmatch(repository + r"@sha256:[0-9a-f]{64}", ref):
            raise ValueError("Image reference must have a platform manifest digest")
    return lock


def verify_archive(path, source):
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if digest != source["sha256"]:
        raise ValueError("Source archive checksum mismatch: " + source["name"])


def prepare(destination, cache):
    lock = load_lock(ROOT / "sources.lock.json")
    destination = Path(destination)
    if destination.exists():
        raise ValueError("Build context already exists; use a new directory")
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    archives = []
    for source in lock["sources"]:
        archive = cache / (source["name"] + "-" + source["commit"] + ".tar.gz")
        if not archive.exists():
            url = "https://codeload.github.com/{}/tar.gz/{}".format(
                source["repository"], source["commit"])
            partial = archive.with_suffix(".partial")
            with urllib.request.urlopen(url, timeout=120) as response, partial.open("wb") as stream:
                shutil.copyfileobj(response, stream)
            verify_archive(partial, source)
            partial.rename(archive)
        verify_archive(archive, source)
        archives.append((source, archive))
    # Only archives verified against the reviewed lock are extracted.
    destination.mkdir(parents=True)
    for source, archive in archives:
        target = destination / "source"
        if source["name"] != "open5gs":
            target = target / "subprojects" / source["name"]
        target.mkdir(parents=True, exist_ok=True)
        subprocess.run(["tar", "-xzf", str(archive.resolve()), "--strip-components=1",
                        "-C", str(target.resolve())], check=True, timeout=60)
    shutil.copy2(ROOT / "sources.lock.json", destination / "sources.lock.json")
    for filename in ("Dockerfile", "smoke_inside.py", ".dockerignore"):
        shutil.copy2(ROOT / "build" / filename, destination / filename)
    return lock


def pack(context, archive):
    def exclude_metadata(member):
        if any(part.startswith("._") or part == ".DS_Store" for part in Path(member.name).parts):
            return None
        return member
    with Path(archive).open("xb") as stream, tarfile.open(fileobj=stream, mode="w:gz") as bundle:
        bundle.add(context, arcname=".", filter=exclude_metadata)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    prepare(args.output, args.cache)
    if args.archive:
        pack(args.output, args.archive)
    print("Verified build context: " + str(args.output))


if __name__ == "__main__":
    main()
