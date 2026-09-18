"""Wrapper to run Python pipeline benchmark.

Allows running via `python -m benchmarks.benchmark_python`.
"""

import sys
from .benchmark_pipeline import main

if __name__ == "__main__":
    sys.exit(main())
