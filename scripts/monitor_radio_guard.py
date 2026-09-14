#!/usr/bin/env python3
"""Protect the fixed loopback OCUDU control port before the radio starts."""
import os
import subprocess

RULES = '''table inet aoc_metrics_guard {
 chain output { type filter hook output priority -10; policy accept;
  ip daddr 127.0.0.1 tcp dport 8001 meta skuid != 0 reject
 }
}
'''


def main():
    if os.geteuid() != 0:
        raise SystemExit('Requires installed root service')
    existing = subprocess.run(['nft', '-nn', 'list', 'table', 'inet', 'aoc_metrics_guard'], capture_output=True, text=True, timeout=5)
    if existing.returncode == 0:
        if 'tcp dport 8001' not in existing.stdout or 'skuid != 0 reject' not in existing.stdout:
            raise SystemExit('Existing metrics guard differs; refusing radio startup')
        return
    subprocess.run(['nft', '--check', '-f', '-'], input=RULES, text=True, check=True, timeout=5)
    subprocess.run(['nft', '-f', '-'], input=RULES, text=True, check=True, timeout=5)


if __name__ == '__main__':
    main()
