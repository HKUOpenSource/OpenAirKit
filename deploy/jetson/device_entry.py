"""Isolated, fixed-path entry point for the V2 Jetson device service."""
import sys


sys.path.insert(0, "/opt/agentic-ocudu/jetson/current/backend")

from aoc_jetson.agent import main


if __name__ == "__main__":
    main()
