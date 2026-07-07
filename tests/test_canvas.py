import pytest

from primelock_gis.ui.terminal.canvas import (
    TerminalCanvas,
    is_safe_cell_char,
    safe_cell_char,
    clip_text_to_width,
)
from primelock_gis.ui.terminal.capabilities import TerminalCapabilities


def test_write_text():
    canvas = TerminalCanvas(5, 2, ".")

    canvas.write_text(1, 0, "ABC")
    assert canvas.to_string() == ".ABC.\n....."
    canvas.clear()
    canvas.write_text(3, 0, "ABCDE")
    assert canvas.to_string() == "...AB\n....."
    canvas.clear()
    canvas.write_text(-1, 0, "ABC")
    assert canvas.to_string() == "BC...\n....."


def test_clear_resets_canvas():
    canvas = TerminalCanvas(5, 2, ".")
    canvas.set_cell(2, 1, "X")

    canvas.clear()

    assert canvas.to_string() == ".....\n....."


def test_clear_reuses_existing_cell_objects():
    canvas = TerminalCanvas(5, 2, ".")
    first_cell = canvas.cells[0][0]
    last_cell = canvas.cells[1][4]

    canvas.set_cell(0, 0, "X", foreground="#ff0000")
    canvas.set_line_cell(4, 1, {"left", "right"})
    canvas.clear()

    assert canvas.cells[0][0] is first_cell
    assert canvas.cells[1][4] is last_cell
    assert canvas.to_string() == ".....\n....."
def test_canvas_starts_filled():
    canvas = TerminalCanvas(5, 2, ".")

    canvas.clear()
    assert canvas.to_string() == ".....\n....."


def test_clear_can_change_fill_char():
    canvas = TerminalCanvas(5, 2, ".")

    canvas.clear(" ")

    assert canvas.to_string() == "     \n     "


def test_invalid_width_raises_error():
    with pytest.raises(ValueError):
        TerminalCanvas(0, 2)


def test_invalid_height_raises_error():
    with pytest.raises(ValueError):
        TerminalCanvas(5, 0)


def test_set_cell_writes_one_safe_character():
    canvas = TerminalCanvas(5, 2, ".")

    canvas.set_cell(2, 1, "X")

    assert canvas.to_string() == ".....\n..X.."


def test_set_cell_ignores_out_of_bounds_positions():
    canvas = TerminalCanvas(5, 2, ".")

    canvas.set_cell(-1, 0, "X")
    canvas.set_cell(5, 0, "X")
    canvas.set_cell(0, -1, "X")
    canvas.set_cell(0, 2, "X")

    assert canvas.to_string() == ".....\n....."


def test_set_cell_replaces_unsafe_character_with_fallback():
    canvas = TerminalCanvas(5, 2, ".")

    canvas.set_cell(2, 1, "AB")

    assert canvas.to_string() == ".....\n.. .."


def test_set_cell_ignores_empty_character_or_replaces_safely():
    canvas = TerminalCanvas(5, 2, ".")

    canvas.set_cell(2, 1, "")

    assert canvas.to_string() == ".....\n....."


def test_set_cell_replaces_newline_with_fallback():
    canvas = TerminalCanvas(5, 2, ".")

    canvas.set_cell(2, 1, "\n")

    assert canvas.to_string() == ".....\n.. .."


def test_write_text_writes_text_horizontally():
    canvas = TerminalCanvas(5, 2, ".")

    canvas.write_text(1, 0, "ABC")

    assert canvas.to_string() == ".ABC.\n....."


def test_write_text_clips_at_right_edge():
    canvas = TerminalCanvas(5, 2, ".")

    canvas.write_text(3, 0, "ABCDE")

    assert canvas.to_string() == "...AB\n....."


def test_write_text_ignores_y_out_of_bounds():
    canvas = TerminalCanvas(5, 2, ".")

    canvas.write_text(0, -1, "ABC")
    canvas.write_text(0, 2, "ABC")

    assert canvas.to_string() == ".....\n....."


def test_write_text_clips_negative_x():
    canvas = TerminalCanvas(5, 2, ".")

    canvas.write_text(-1, 0, "ABC")

    assert canvas.to_string() == "BC...\n....."


def test_write_text_ignores_x_beyond_right_edge():
    canvas = TerminalCanvas(5, 2, ".")

    canvas.write_text(5, 0, "ABC")

    assert canvas.to_string() == ".....\n....."


def test_write_text_replaces_unsafe_characters():
    canvas = TerminalCanvas(5, 2, ".")

    canvas.write_text(0, 0, "A\nB")

    assert canvas.to_string() == "A B..\n....."


def test_is_safe_cell_char_accepts_simple_characters():
    assert is_safe_cell_char("A") is True
    assert is_safe_cell_char("●") is True
    assert is_safe_cell_char("─") is True


def test_is_safe_cell_char_rejects_bad_values():
    assert is_safe_cell_char("") is False
    assert is_safe_cell_char("AB") is False
    assert is_safe_cell_char("\n") is False
    assert is_safe_cell_char("\t") is False
    assert is_safe_cell_char("\r") is False
    assert is_safe_cell_char(None) is False


def test_safe_cell_char_returns_fallback_for_bad_values():
    assert safe_cell_char("A") == "A"
    assert safe_cell_char("AB") == " "
    assert safe_cell_char("") == " "
    assert safe_cell_char("\n") == " "
    assert safe_cell_char("AB", fallback="?") == "?"


def test_clip_text_to_width_keeps_short_text():
    assert clip_text_to_width("ABC", 5) == "ABC"


def test_clip_text_to_width_truncates_long_text():
    assert clip_text_to_width("ABCDE", 2) == "AB"


def test_clip_text_to_width_zero_width_returns_empty_string():
    assert clip_text_to_width("ABCDE", 0) == ""


def test_set_cell_stores_foreground_color_without_plain_ansi_output():
    canvas = TerminalCanvas(3, 1, ".")

    canvas.set_cell(1, 0, "X", foreground="#ff0000")

    assert canvas.cells[0][1].foreground == "#ff0000"
    assert canvas.to_string() == ".X."


def test_to_string_emits_truecolor_when_supported():
    canvas = TerminalCanvas(3, 1, ".")
    capabilities = TerminalCapabilities(
        supports_color=True,
        supports_truecolor=True,
    )

    canvas.set_cell(1, 0, "X", foreground="#ff0000")

    assert canvas.to_string(capabilities) == ".\x1b[38;2;255;0;0mX\x1b[0m."


def test_to_string_emits_truecolor_background_when_supported():
    canvas = TerminalCanvas(2, 1, ".")
    capabilities = TerminalCapabilities(
        supports_color=True,
        supports_truecolor=True,
    )

    canvas.set_background_cell(0, 0, "#0000ff")

    assert canvas.to_string(capabilities) == "\x1b[48;2;0;0;255m \x1b[0m."


def test_foreground_overlay_preserves_background_color():
    canvas = TerminalCanvas(1, 1, ".")

    canvas.set_background_cell(0, 0, "#0000ff")
    canvas.set_cell(0, 0, "X", foreground="#ff0000")

    assert canvas.cells[0][0].char == "X"
    assert canvas.cells[0][0].foreground == "#ff0000"
    assert canvas.cells[0][0].background == "#0000ff"


def test_to_string_emits_basic_ansi_when_truecolor_is_not_supported():
    canvas = TerminalCanvas(3, 1, ".")
    capabilities = TerminalCapabilities(
        supports_color=True,
        supports_truecolor=False,
    )

    canvas.set_cell(1, 0, "X", foreground="#ff0000")

    assert canvas.to_string(capabilities) == ".\x1b[31mX\x1b[0m."


def test_to_string_omits_ansi_when_color_is_not_supported():
    canvas = TerminalCanvas(3, 1, ".")
    capabilities = TerminalCapabilities(supports_color=False)

    canvas.set_cell(1, 0, "X", foreground="#ff0000")

    assert canvas.to_string(capabilities) == ".X."


def test_line_cells_merge_into_unicode_junctions():
    canvas = TerminalCanvas(3, 3, ".")

    canvas.set_line_cell(1, 1, {"left", "right"})
    canvas.set_line_cell(1, 1, {"up", "down"})

    assert canvas.to_string() == "...\n.┼.\n..."


def test_line_cells_have_ascii_fallback():
    canvas = TerminalCanvas(3, 3, ".")
    capabilities = TerminalCapabilities(supports_unicode=False)

    canvas.set_line_cell(1, 1, {"left", "right"})
    canvas.set_line_cell(1, 1, {"up", "down"})

    assert canvas.to_string(capabilities) == "...\n.+.\n..."


def test_braille_dots_merge_inside_one_cell():
    canvas = TerminalCanvas(3, 1, ".")

    canvas.set_braille_dot(1, 0, 0, 0)
    canvas.set_braille_dot(1, 0, 1, 3)

    assert canvas.to_string() == f".{chr(0x2800 + 0x01 + 0x80)}."


def test_braille_dots_have_ascii_fallback():
    canvas = TerminalCanvas(3, 1, ".")
    capabilities = TerminalCapabilities(
        supports_unicode=False,
        supports_braille=False,
    )

    canvas.set_braille_dot(1, 0, 0, 0)

    assert canvas.to_string(capabilities) == ".*."


def test_braille_dots_store_color_and_emit_ansi():
    canvas = TerminalCanvas(3, 1, ".")
    capabilities = TerminalCapabilities(
        supports_color=True,
        supports_truecolor=True,
    )

    canvas.set_braille_dot(1, 0, 0, 0, color="#ff0000")

    assert "\x1b[38;2;255;0;0m" in canvas.to_string(capabilities)
