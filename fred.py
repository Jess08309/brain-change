"""Run one FRED instruction on this laptop, then stop."""

import sys
from pathlib import Path

from laptop.surface import handle
from sandbox.box import main as sandbox_main

ROOT = Path(__file__).resolve().parent


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "sandbox":
        sandbox_main(sys.argv[2:])
        return
    text = " ".join(sys.argv[1:]).strip()
    print(handle(text, ROOT))


if __name__ == "__main__":
    main()
