"""Terminal capability detection.

终端能力检测。
"""

from dataclasses import dataclass
import os
from collections.abc import Mapping


@dataclass
class TerminalCapabilities:
    name: str = "unknown"
    supports_unicode: bool = True
    supports_braille: bool = True
    supports_color: bool = True
    supports_truecolor: bool = False

# Check what terminal the user is using.
def detect_terminal_name(env: Mapping[str, str] | None = None) -> str:
    if env is None:
        env = os.environ

    term = env.get("TERM", "")
    term_program = env.get("TERM_PROGRAM", "")

    term_lower = term.lower()
    term_program_lower = term_program.lower()

    if "ghostty" in term_lower or "ghostty" in term_program_lower:
        return "ghostty"

    if term_program_lower == "iterm.app" or "iterm" in term_program_lower:
        return "iterm2"

    if "kitty" in term_lower or "kitty" in term_program_lower:
        return "kitty"

    if "wezterm" in term_lower or "wezterm" in term_program_lower:
        return "wezterm"

    if "apple_terminal" in term_program_lower or term_program_lower == "apple_terminal":
        return "apple-terminal"

    if "xterm" in term_lower:
        return "xterm"

    return "unknown"

# Check what color range is supported.
def supports_truecolor(env: Mapping[str, str] | None = None) -> bool:
    if env is None:
        env = os.environ

    color_term = env.get("COLORTERM", "")
    color_term_lower = color_term.lower()

    return color_term_lower in ("truecolor", "24bit")

# Return the terminal capabilities.
def detect_terminal_capabilities(env: Mapping[str, str] | None = None) -> TerminalCapabilities:
    name = detect_terminal_name(env)
    truecolor = supports_truecolor(env)

    return TerminalCapabilities(
        name=name,
        supports_unicode=True,
        supports_braille=True,
        supports_color=True,
        supports_truecolor=truecolor,
    )