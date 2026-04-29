"""A simple canvas for drawing characters in a terminal."""

from dataclasses import dataclass, field


@dataclass
class TerminalCanvas:
    width: int
    height: int
    fill_char: str = " "
    cells: list[list[str]] = field(init=False)

    # If the input dimensions are valid, build an empty canvas.
    def __post_init__(self) -> None:
        if self.width <= 0:
            raise ValueError("Canvas width must be positive")
        if self.height <= 0:
            raise ValueError("Canvas height must be positive")

        self.clear()

    # Reset the whole canvas
    def clear(self, fill_char: str | None = None) -> None:
        if fill_char is not None:
            self.fill_char = fill_char
        self.cells = []

        for _ in range(self.height):
            row = []

            for _ in range(self.width):
                row.append(self.fill_char)

            self.cells.append(row)

    # Write the character to one terminal cell.
    def set_cell(self, x: int, y: int, char: str) -> None:

        if not char:
            return
        
        if 0 <= x < self.width and 0 <= y < self.height:
            self.cells[y][x] = safe_cell_char(char)
    
    # Write a text label horizontally into the canvas.
    def write_text(self, x: int, y: int, text: str) -> None:
        
        if y < 0 or y >= self.height:
            return
        if x >= self.width:
            return

        if x < 0:
            text = text[abs(x):]
            x = 0

        available_width = self.width - x
        text = clip_text_to_width(text, available_width)

        for i, char in enumerate(text):
            valid_char = safe_cell_char(char)
            self.set_cell(x + i, y, valid_char)

    # Convert canvas grid into printable text.
    def to_string(self) -> str:
        rows = []

        for row in self.cells:
            rows.append("".join(row))

        return "\n".join(rows)
    


# Return True if char is safe to put into one terminal cell.
def is_safe_cell_char(char: str) -> bool:
    if char == "":
        return False
    elif not isinstance(char, str):
        return False
    elif len(char) != 1:
        return False
    elif char in ("\n", "\t", "\r"):
        return False
    return True

# Return char if it is safe. Otherwise return fallback.
def safe_cell_char(char: str, fallback=" ") -> str:
    if is_safe_cell_char(char):
        return char
    else:
        return fallback

# Make sure text fits within max_width by truncating it if necessary.
def clip_text_to_width(text: str, available_width: int) -> str:
    if len(text) <= available_width:
        return text
    else:
        return text[:available_width]
    