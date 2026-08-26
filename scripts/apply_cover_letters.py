#!/usr/bin/env python
"""Compatibility wrapper for `hermes apply`."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.cli import main

raise SystemExit(main(["apply", *sys.argv[1:]]))
