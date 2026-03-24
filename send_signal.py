from __future__ import annotations

from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if _SRC.is_dir():
    sys.path.insert(0, str(_SRC))
    __path__ = [str(_SRC / "ghost")]

from ghost.cli import main


if __name__ == "__main__":
    main()
