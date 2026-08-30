# SPDX-License-Identifier: MIT
"""Compatibility shim for tools.extract.breadbakers."""
import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from tools.extract.breadbakers import *
from tools.extract.breadbakers import (
    classify_message,
    preprocess_message,
    process_directory,
    process_single_file,
    main,
)

if __name__ == "__main__":
    main()
