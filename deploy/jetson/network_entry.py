"""Isolated, fixed-path entry point for the constrained network helper."""
import sys


sys.path.insert(0, "/opt/agentic-ocudu/jetson/current/backend")

from aoc_jetson.network import main


if __name__ == "__main__":
    raise SystemExit(main())
