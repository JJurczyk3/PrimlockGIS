from primelock_gis.ui.terminal.canvas import (
    TerminalCanvas,
    is_safe_cell_char,
    safe_cell_char,
    clip_text_to_width,
)


"""Manually written test casses"""
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



""" More test casses written by an LLM"""
def test_canvas_starts_filled():
    canvas = TerminalCanvas(5, 2, ".")

    canvas.clear()
    assert canvas.to_string() == ".....\n....."


def test_clear_can_change_fill_char():
    canvas = TerminalCanvas(5, 2, ".")

    canvas.clear(" ")

    assert canvas.to_string() == "     \n     "


def test_invalid_width_raises_error():
    try:
        TerminalCanvas(0, 2)
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_invalid_height_raises_error():
    try:
        TerminalCanvas(5, 0)
        assert False, "Expected ValueError"
    except ValueError:
        pass


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