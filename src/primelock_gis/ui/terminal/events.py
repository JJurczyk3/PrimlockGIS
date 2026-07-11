"""Terminal input event models."""

from dataclasses import dataclass, field


@dataclass
class KeyEvent:
    key: str
    raw_sequence: str | None = field(default=None, compare=False)


@dataclass
class MouseEvent:
    kind: str
    x: int
    y: int
    button: int | None = None
    raw_sequence: str | None = field(default=None, compare=False)


@dataclass
class ResizeEvent:
    width: int
    height: int


TerminalEvent = KeyEvent | MouseEvent | ResizeEvent
