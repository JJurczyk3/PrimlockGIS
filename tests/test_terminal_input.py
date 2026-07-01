from primelock_gis.ui.terminal.events import KeyEvent, MouseEvent
from primelock_gis.ui.terminal.input import (
    parse_input_sequence,
    parse_sgr_mouse_sequence,
    parse_x10_mouse_sequence,
)


def test_parse_plain_key():
    event = parse_input_sequence("q")

    assert event == KeyEvent("q")


def test_escape_sequences_are_kept_as_raw_key_events():
    event = parse_input_sequence("\x1b[1;2A")

    assert event == KeyEvent("\x1b[1;2A")
    assert event.raw_sequence == "\x1b[1;2A"


def test_parse_escape_key():
    assert parse_input_sequence("\x1b") == KeyEvent("escape")


def test_parse_sgr_mouse_press_converts_to_zero_based_coordinates():
    event = parse_sgr_mouse_sequence("\x1b[<0;12;5M")

    assert event == MouseEvent(kind="press", x=11, y=4, button=0)


def test_parse_sgr_mouse_drag():
    event = parse_sgr_mouse_sequence("\x1b[<32;13;6M")

    assert event == MouseEvent(kind="drag", x=12, y=5, button=0)


def test_parse_sgr_mouse_release():
    event = parse_sgr_mouse_sequence("\x1b[<0;13;6m")

    assert event == MouseEvent(kind="release", x=12, y=5, button=0)


def test_parse_sgr_mouse_wheel():
    assert parse_sgr_mouse_sequence("\x1b[<64;7;8M") == MouseEvent(
        kind="wheel_up",
        x=6,
        y=7,
        button=None,
    )
    assert parse_sgr_mouse_sequence("\x1b[<65;7;8M") == MouseEvent(
        kind="wheel_down",
        x=6,
        y=7,
        button=None,
    )


def test_parse_invalid_sgr_mouse_sequence_returns_none():
    assert parse_sgr_mouse_sequence("\x1b[A") is None


def test_parse_x10_mouse_press_converts_to_zero_based_coordinates():
    sequence = "\x1b[M" + chr(32) + chr(12 + 33) + chr(5 + 33)

    event = parse_x10_mouse_sequence(sequence)

    assert event == MouseEvent(kind="press", x=12, y=5, button=0)


def test_parse_x10_mouse_drag():
    sequence = "\x1b[M" + chr(32 + 32) + chr(13 + 33) + chr(6 + 33)

    event = parse_x10_mouse_sequence(sequence)

    assert event == MouseEvent(kind="drag", x=13, y=6, button=0)


def test_parse_x10_mouse_release():
    sequence = "\x1b[M" + chr(32 + 3) + chr(13 + 33) + chr(6 + 33)

    event = parse_x10_mouse_sequence(sequence)

    assert event == MouseEvent(kind="release", x=13, y=6, button=None)


def test_parse_input_sequence_accepts_x10_mouse_sequence():
    sequence = "\x1b[M" + chr(32) + chr(1 + 33) + chr(2 + 33)

    event = parse_input_sequence(sequence)

    assert event == MouseEvent(kind="press", x=1, y=2, button=0)
