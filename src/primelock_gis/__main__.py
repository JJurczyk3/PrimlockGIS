"""Run Primelock GIS."""

from pathlib import Path
import shutil

from primelock_gis.app.startup import run_terminal_beta


def main() -> None:
    run_terminal_beta()


if __name__ == "__main__":
    main()