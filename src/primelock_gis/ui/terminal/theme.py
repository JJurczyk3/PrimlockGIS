"""Shared terminal theme values for the viewer and support panel."""

from dataclasses import dataclass

from primelock_gis.ui.terminal.canvas import color_to_ansi


@dataclass(frozen=True)
class TerminalTheme:
    background: str = "#0B1020"
    foreground: str = "#E6EDF3"
    muted: str = "#8B949E"
    frame: str = "#6E7681"
    active: str = "#7DD3FC"
    inactive: str = "#C9D1D9"
    focused: str = "#A78BFA"
    disabled: str = "#484F58"
    success: str = "#3FB950"
    warning: str = "#D29922"
    error: str = "#F85149"
    points: str = "#E9C46A"
    grid: str = "#546A76"
    tin: str = "#DDA15E"
    contours: str = "#7DD3FC"
    contour_labels: str = "#BAE6FD"
    terrain_low: str = "#1E3A8A"
    terrain_low_mid: str = "#15803D"
    terrain_high_mid: str = "#EAB308"
    terrain_high: str = "#DC2626"


TERMINAL_THEME = TerminalTheme()


def button_state_color(state: str, theme: TerminalTheme = TERMINAL_THEME) -> str:
    """Return the theme colour for a button state."""
    if state == "active":
        return theme.active
    if state == "focused":
        return theme.focused
    if state == "disabled":
        return theme.disabled
    if state == "success":
        return theme.success
    if state == "warning":
        return theme.warning
    if state == "error":
        return theme.error
    return theme.inactive


def status_color(status: str, theme: TerminalTheme = TERMINAL_THEME) -> str:
    """Return a semantic colour for a status or command response."""
    if status.startswith(("OK:", "SUCCESS:")):
        return theme.success
    if status.startswith(("WARN:", "WARNING:")):
        return theme.warning
    if status.startswith(("ERROR:", "FAIL:")):
        return theme.error
    return theme.foreground


def color_text(text: str, color: str | None, capabilities=None) -> str:
    """Wrap text in an ANSI foreground colour when supported."""
    code = color_to_ansi(color, capabilities)
    if code is None:
        return text
    return f"{code}{text}\x1b[0m"
