# SPDX-License-Identifier: MIT
"""Terminal styling and console output reporters."""
import sys


class Colors:
    """ANSI color codes for terminal styling."""

    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"


def print_progress_bar(
    iteration: int,
    total: int,
    prefix: str = "",
    suffix: str = "",
    length: int = 40,
    fill: str = "█",
) -> None:
    """Display progress bar in terminal.

    Args:
        iteration: Current iteration.
        total: Total iterations.
        prefix: Prefix string.
        suffix: Suffix string.
        length: Character length of bar.
        fill: Bar fill character.
    """
    if total <= 0:
        return
    percent = f"{100 * (iteration / float(total)):.1f}"
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + "-" * (length - filled_length)
    sys.stdout.write(f"\r{Colors.CYAN}{prefix}{Colors.ENDC} |{bar}| {percent}% {suffix}")
    sys.stdout.flush()
    if iteration == total:
        sys.stdout.write("\n")
        sys.stdout.flush()
