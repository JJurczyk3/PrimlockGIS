from primelock_gis.ui.terminal.capabilities import (
    detect_terminal_name,
    supports_truecolor,
    detect_terminal_capabilities,
)


def test_detects_ghostty():
    env = {"TERM": "xterm-ghostty"}

    assert detect_terminal_name(env) == "ghostty"


def test_detects_iterm2():
    env = {"TERM_PROGRAM": "iTerm.app"}

    assert detect_terminal_name(env) == "iterm2"


def test_detects_kitty():
    env = {"TERM": "xterm-kitty"}

    assert detect_terminal_name(env) == "kitty"


def test_detects_wezterm():
    env = {"TERM_PROGRAM": "WezTerm"}

    assert detect_terminal_name(env) == "wezterm"


def test_unknown_terminal():
    env = {}

    assert detect_terminal_name(env) == "unknown"


def test_supports_truecolor():
    env = {"COLORTERM": "truecolor"}

    assert supports_truecolor(env) is True


def test_supports_24bit():
    env = {"COLORTERM": "24bit"}

    assert supports_truecolor(env) is True


def test_missing_truecolor():
    env = {}

    assert supports_truecolor(env) is False


def test_detect_terminal_capabilities_returns_dataclass():
    env = {
        "TERM": "xterm-ghostty",
        "COLORTERM": "truecolor",
    }

    caps = detect_terminal_capabilities(env)

    assert caps.name == "ghostty"
    assert caps.supports_unicode is True
    assert caps.supports_braille is True
    assert caps.supports_color is True
    assert caps.supports_truecolor is True