"""Run Primelock GIS."""

import sys

from primelock_gis.app.startup import run_terminal_beta
from primelock_gis.ui.terminal.support_panel import run_support_panel


def main() -> None:
    mode = "viewer"

    if len(sys.argv) > 1:
        mode = sys.argv[1]

    if mode == "viewer":
        run_terminal_beta()
        return

    if mode == "support":
        run_support_panel()
        return

    print(f"Unknown mode: {mode}")
    print("Usage:")
    print("  python -m primelock_gis viewer")
    print("  python -m primelock_gis support")


if __name__ == "__main__":
    main()
