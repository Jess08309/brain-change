"""Run one FRED instruction on this laptop, then stop."""

import sys
from pathlib import Path

from laptop.surface import handle

ROOT = Path(__file__).resolve().parent


def main() -> None:
    text = " ".join(sys.argv[1:]).strip()
    print(handle(text, ROOT))


if __name__ == "__main__":
    main()
