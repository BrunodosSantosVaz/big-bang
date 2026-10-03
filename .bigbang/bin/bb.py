"""Universal entry point of the bb CLI: python .bigbang/bin/bb.py <comando> (Linux, macOS and Windows)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bb.cli import main  # noqa: E402

if __name__ == "__main__":
    if sys.version_info < (3, 11):
        sys.exit("bb: Python 3.11 ou superior é necessário")
    sys.exit(main())
