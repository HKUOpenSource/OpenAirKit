#!/usr/bin/env python3
"""Build pinned OCUDU in a private Ubuntu ARM64 workspace without sudo or RF access."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time


COMMIT = "050a2bb72e1d794cd60570d809987c1fcda3e54b"
PACKAGES = ("libmbedtls-dev=2.28.8-1", "libgtest-dev=1.14.0-1")


def run(argv, cwd=None):
    print("+ " + " ".join(map(str, argv)), flush=True)
    subprocess.run(list(map(str, argv)), cwd=cwd, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=2, choices=range(1, 5))
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() != "aarch64" or os.geteuid() == 0:
        parser.error("Run as an ordinary user on Ubuntu ARM64")
    root = args.workspace.resolve()
    if Path.home() not in root.parents:
        parser.error("Workspace must be a dedicated directory under the invoking user's home")
    root.mkdir(parents=True, exist_ok=True)
    os.nice(15)
    source, build = root / "source", root / "build"
    packages, sysroot = root / "packages", root / "sysroot"
    packages.mkdir(exist_ok=True)
    sysroot.mkdir(exist_ok=True)
    if not source.exists():
        run(["git", "clone", "--depth", "1", "--branch", "release_26_04",
             "https://gitlab.com/ocudu/ocudu.git", source])
    actual = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"], text=True)
    if actual != COMMIT or dirty:
        parser.error("Source differs from the pinned clean OCUDU release")
    run(["apt-get", "download", *PACKAGES], cwd=packages)
    for package in sorted(packages.glob("*.deb")):
        run(["dpkg-deb", "--extract", package, sysroot])
    private_lib = sysroot / "usr/lib/aarch64-linux-gnu"
    crypto = private_lib / "libmbedcrypto.a"
    if not crypto.is_file():
        parser.error("Private static mbedcrypto library is missing")
    # This release links some test targets by name without imported include paths.
    os.environ["CPLUS_INCLUDE_PATH"] = str(sysroot / "usr/include")
    run(["cmake", "-S", source, "-B", build, "-DCMAKE_BUILD_TYPE=Release",
         "-U", "HAVE_ARM_CRYPTO", "-U", "HAVE_PLUS_CRYPTO", "-DMARCH=armv8.2-a",
         "-DCMAKE_INSTALL_PREFIX=" + str(root / "install"),
         "-DCMAKE_PREFIX_PATH=" + str(sysroot / "usr") + ";/usr/local",
         "-DCMAKE_EXE_LINKER_FLAGS=-L" + str(private_lib),
         "-DMBEDTLS_INCLUDE_DIRS=" + str(sysroot / "usr/include"),
         "-DMBEDTLS_LIBRARIES=" + str(crypto),
         "-DMBEDTLS_STATIC_LIBRARIES=" + str(crypto),
         "-DENABLE_UHD=ON", "-DENABLE_ZEROMQ=OFF", "-DENABLE_DPDK=OFF",
         "-DBUILD_TESTING=ON"])
    targets = ["gnb", "security_test", "timer_test", "network_test"]
    run(["cmake", "--build", build, "--parallel", args.jobs, "--target", *targets])
    run([build / "apps/gnb/gnb", "--version"])
    # These bounded tests never open the SDR; PHY vector tests are a separate suite.
    for test in ("security/security_test", "support/timer_test", "support/network/network_test"):
        run([build / "tests/unittests" / test])
    binary = build / "apps/gnb/gnb"
    result = {"commit": actual, "architecture": platform.machine(), "completed_at": time.time(),
              "binary": str(binary), "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
              "packages": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in packages.glob("*.deb")},
              "tests": ["security_test", "timer_test", "network_test"], "rf_opened": False}
    (root / "build-result.json").write_text(json.dumps(result, indent=2) + "\n")
    print("Build and non-RF checks completed: " + str(root / "build-result.json"))


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
