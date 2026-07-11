"""
conftest.py — Makes `services.*` / `handlers.*` / `config` importable from
tests without installing the project as a package.
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
