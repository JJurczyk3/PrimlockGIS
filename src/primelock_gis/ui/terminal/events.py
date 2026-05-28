""" Terminal input event models. """

from dataclasses import dataclass


@dataclass
class KeyEvent:
    key: str


@dataclass
class MouseEvent:
    kind: str
    x: int
    y: int
    button: int | None = None