#!/usr/bin/env python3
"""Run the whole suite. `python3 tests/run_all.py`"""
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.discover(str(HERE), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2, warnings="ignore")
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
