"""Native Win32 console mode and input backend.

The application continues to render with ANSI/VT sequences, but reads input
records with ``ReadConsoleInputW``.  Character-stream readers cannot reliably
deliver mouse and window-resize records on Windows consoles.
"""

import ctypes
import sys
from collections import deque
from dataclasses import dataclass
from typing import TypeAlias

from primelock_gis.ui.terminal.backends.base import TerminalBackendError
from primelock_gis.ui.terminal.events import (
    KeyEvent,
    MouseEvent,
    ResizeEvent,
    TerminalEvent,
)

STD_INPUT_HANDLE = -10
STD_OUTPUT_HANDLE = -11

ENABLE_PROCESSED_INPUT = 0x0001
ENABLE_LINE_INPUT = 0x0002
ENABLE_ECHO_INPUT = 0x0004
ENABLE_WINDOW_INPUT = 0x0008
ENABLE_MOUSE_INPUT = 0x0010
ENABLE_QUICK_EDIT_MODE = 0x0040
ENABLE_EXTENDED_FLAGS = 0x0080
ENABLE_VIRTUAL_TERMINAL_INPUT = 0x0200

ENABLE_PROCESSED_OUTPUT = 0x0001
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004

KEY_EVENT = 0x0001
MOUSE_EVENT = 0x0002
WINDOW_BUFFER_SIZE_EVENT = 0x0004

RIGHT_ALT_PRESSED = 0x0001
LEFT_ALT_PRESSED = 0x0002
RIGHT_CTRL_PRESSED = 0x0004
LEFT_CTRL_PRESSED = 0x0008

FROM_LEFT_1ST_BUTTON_PRESSED = 0x0001
RIGHTMOST_BUTTON_PRESSED = 0x0002
FROM_LEFT_2ND_BUTTON_PRESSED = 0x0004
FROM_LEFT_3RD_BUTTON_PRESSED = 0x0008
FROM_LEFT_4TH_BUTTON_PRESSED = 0x0010

MOUSE_MOVED = 0x0001
DOUBLE_CLICK = 0x0002
MOUSE_WHEELED = 0x0004
MOUSE_HWHEELED = 0x0008

WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102
WAIT_FAILED = 0xFFFFFFFF
CP_UTF8 = 65001

VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_PRIOR = 0x21
VK_NEXT = 0x22
VK_END = 0x23
VK_HOME = 0x24
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_INSERT = 0x2D
VK_DELETE = 0x2E
VK_F1 = 0x70
VK_F12 = 0x7B

VIRTUAL_KEY_NAMES = {
    VK_BACK: "\b",
    VK_TAB: "\t",
    VK_RETURN: "\n",
    VK_ESCAPE: "escape",
    VK_PRIOR: "page_up",
    VK_NEXT: "page_down",
    VK_END: "end",
    VK_HOME: "home",
    VK_LEFT: "left",
    VK_UP: "up",
    VK_RIGHT: "right",
    VK_DOWN: "down",
    VK_INSERT: "insert",
    VK_DELETE: "delete",
}

BUTTON_BITS = (
    (FROM_LEFT_1ST_BUTTON_PRESSED, 0),
    (FROM_LEFT_2ND_BUTTON_PRESSED, 1),
    (RIGHTMOST_BUTTON_PRESSED, 2),
    (FROM_LEFT_3RD_BUTTON_PRESSED, 3),
    (FROM_LEFT_4TH_BUTTON_PRESSED, 4),
)
BUTTON_MASK = sum(bit for bit, _ in BUTTON_BITS)


@dataclass(frozen=True)
class WindowsKeyRecord:
    key_down: bool
    repeat_count: int
    virtual_key: int
    char: str = ""
    control_key_state: int = 0


@dataclass(frozen=True)
class WindowsMouseRecord:
    x: int
    y: int
    button_state: int
    event_flags: int


@dataclass(frozen=True)
class WindowsResizeRecord:
    width: int
    height: int


WindowsInputRecord: TypeAlias = (
    WindowsKeyRecord | WindowsMouseRecord | WindowsResizeRecord
)


class WindowsRecordTranslator:
    """Translate high-level Win32 records into the application's events."""

    def __init__(self) -> None:
        self.button_state = 0

    def translate(
        self,
        record: WindowsInputRecord,
        origin: tuple[int, int] = (0, 0),
    ) -> list[TerminalEvent]:
        if isinstance(record, WindowsKeyRecord):
            return self._translate_key(record)
        if isinstance(record, WindowsResizeRecord):
            return [ResizeEvent(record.width, record.height)]
        return self._translate_mouse(record, origin)

    def _translate_key(self, record: WindowsKeyRecord) -> list[TerminalEvent]:
        if not record.key_down:
            return []

        key = record.char
        if key == "\r":
            key = "\n"
        elif key == "\x1b":
            key = "escape"
        if not key or key == "\x00":
            key = VIRTUAL_KEY_NAMES.get(record.virtual_key, "")
        if not key and VK_F1 <= record.virtual_key <= VK_F12:
            key = f"f{record.virtual_key - VK_F1 + 1}"
        if not key:
            return []

        repeat_count = max(1, record.repeat_count)
        return [KeyEvent(key) for _ in range(repeat_count)]

    def _translate_mouse(
        self,
        record: WindowsMouseRecord,
        origin: tuple[int, int],
    ) -> list[TerminalEvent]:
        x = record.x - origin[0]
        y = record.y - origin[1]
        next_buttons = record.button_state & BUTTON_MASK

        if record.event_flags & MOUSE_WHEELED:
            self.button_state = next_buttons
            delta = _signed_high_word(record.button_state)
            kind = "wheel_up" if delta > 0 else "wheel_down"
            return [MouseEvent(kind=kind, x=x, y=y)] if delta else []

        if record.event_flags & MOUSE_HWHEELED:
            self.button_state = next_buttons
            return []

        if record.event_flags & MOUSE_MOVED:
            self.button_state = next_buttons
            button = _first_pressed_button(next_buttons)
            if button is None:
                return []
            return [MouseEvent(kind="drag", x=x, y=y, button=button)]

        previous_buttons = self.button_state
        self.button_state = next_buttons
        events: list[TerminalEvent] = []
        for bit, button in BUTTON_BITS:
            if next_buttons & bit and not previous_buttons & bit:
                events.append(MouseEvent("press", x, y, button))
            elif previous_buttons & bit and not next_buttons & bit:
                events.append(MouseEvent("release", x, y, button))
        return events


def _first_pressed_button(button_state: int) -> int | None:
    for bit, button in BUTTON_BITS:
        if button_state & bit:
            return button
    return None


def _signed_high_word(value: int) -> int:
    return ctypes.c_int16((value >> 16) & 0xFFFF).value


class _COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_int16), ("Y", ctypes.c_int16)]


class _SMALL_RECT(ctypes.Structure):
    _fields_ = [
        ("Left", ctypes.c_int16),
        ("Top", ctypes.c_int16),
        ("Right", ctypes.c_int16),
        ("Bottom", ctypes.c_int16),
    ]


class _CHAR_UNION(ctypes.Union):
    _fields_ = [("UnicodeChar", ctypes.c_uint16), ("AsciiChar", ctypes.c_char)]


class _KEY_EVENT_RECORD(ctypes.Structure):
    _fields_ = [
        ("bKeyDown", ctypes.c_int32),
        ("wRepeatCount", ctypes.c_uint16),
        ("wVirtualKeyCode", ctypes.c_uint16),
        ("wVirtualScanCode", ctypes.c_uint16),
        ("uChar", _CHAR_UNION),
        ("dwControlKeyState", ctypes.c_uint32),
    ]


class _MOUSE_EVENT_RECORD(ctypes.Structure):
    _fields_ = [
        ("dwMousePosition", _COORD),
        ("dwButtonState", ctypes.c_uint32),
        ("dwControlKeyState", ctypes.c_uint32),
        ("dwEventFlags", ctypes.c_uint32),
    ]


class _WINDOW_BUFFER_SIZE_RECORD(ctypes.Structure):
    _fields_ = [("dwSize", _COORD)]


class _INPUT_EVENT_UNION(ctypes.Union):
    _fields_ = [
        ("KeyEvent", _KEY_EVENT_RECORD),
        ("MouseEvent", _MOUSE_EVENT_RECORD),
        ("WindowBufferSizeEvent", _WINDOW_BUFFER_SIZE_RECORD),
        ("_padding", ctypes.c_byte * 16),
    ]


class _INPUT_RECORD(ctypes.Structure):
    _fields_ = [("EventType", ctypes.c_uint16), ("Event", _INPUT_EVENT_UNION)]


class _CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
    _fields_ = [
        ("dwSize", _COORD),
        ("dwCursorPosition", _COORD),
        ("wAttributes", ctypes.c_uint16),
        ("srWindow", _SMALL_RECT),
        ("dwMaximumWindowSize", _COORD),
    ]


class WindowsConsoleAPI:
    """Checked, pointer-safe wrapper around the Win32 console functions."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise TerminalBackendError(
                "The Win32 console API is only available on Windows."
            )

        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle_type = ctypes.c_void_p
        dword_pointer = ctypes.POINTER(ctypes.c_uint32)

        self.kernel32.GetStdHandle.argtypes = [ctypes.c_int32]
        self.kernel32.GetStdHandle.restype = handle_type
        self.kernel32.GetConsoleMode.argtypes = [handle_type, dword_pointer]
        self.kernel32.GetConsoleMode.restype = ctypes.c_int32
        self.kernel32.SetConsoleMode.argtypes = [handle_type, ctypes.c_uint32]
        self.kernel32.SetConsoleMode.restype = ctypes.c_int32
        self.kernel32.GetConsoleCP.argtypes = []
        self.kernel32.GetConsoleCP.restype = ctypes.c_uint32
        self.kernel32.GetConsoleOutputCP.argtypes = []
        self.kernel32.GetConsoleOutputCP.restype = ctypes.c_uint32
        self.kernel32.SetConsoleCP.argtypes = [ctypes.c_uint32]
        self.kernel32.SetConsoleCP.restype = ctypes.c_int32
        self.kernel32.SetConsoleOutputCP.argtypes = [ctypes.c_uint32]
        self.kernel32.SetConsoleOutputCP.restype = ctypes.c_int32
        self.kernel32.WaitForSingleObject.argtypes = [handle_type, ctypes.c_uint32]
        self.kernel32.WaitForSingleObject.restype = ctypes.c_uint32
        self.kernel32.ReadConsoleInputW.argtypes = [
            handle_type,
            ctypes.POINTER(_INPUT_RECORD),
            ctypes.c_uint32,
            dword_pointer,
        ]
        self.kernel32.ReadConsoleInputW.restype = ctypes.c_int32
        self.kernel32.GetConsoleScreenBufferInfo.argtypes = [
            handle_type,
            ctypes.POINTER(_CONSOLE_SCREEN_BUFFER_INFO),
        ]
        self.kernel32.GetConsoleScreenBufferInfo.restype = ctypes.c_int32

    def get_std_handle(self, identifier: int) -> int:
        handle = self.kernel32.GetStdHandle(identifier)
        invalid_handle = ctypes.c_void_p(-1).value
        if handle in (None, 0, invalid_handle):
            self._raise_last_error("GetStdHandle")
        return handle

    def get_console_mode(self, handle: int) -> int:
        mode = ctypes.c_uint32()
        if not self.kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            self._raise_last_error("GetConsoleMode")
        return mode.value

    def set_console_mode(self, handle: int, mode: int) -> bool:
        return bool(self.kernel32.SetConsoleMode(handle, mode))

    def get_console_cp(self) -> int:
        code_page = int(self.kernel32.GetConsoleCP())
        if not code_page:
            self._raise_last_error("GetConsoleCP")
        return code_page

    def get_console_output_cp(self) -> int:
        code_page = int(self.kernel32.GetConsoleOutputCP())
        if not code_page:
            self._raise_last_error("GetConsoleOutputCP")
        return code_page

    def set_console_cp(self, code_page: int) -> bool:
        return bool(self.kernel32.SetConsoleCP(code_page))

    def set_console_output_cp(self, code_page: int) -> bool:
        return bool(self.kernel32.SetConsoleOutputCP(code_page))

    def wait_for_input(self, handle: int, timeout: float) -> bool:
        milliseconds = max(0, min(0xFFFFFFFE, round(timeout * 1000)))
        result = self.kernel32.WaitForSingleObject(handle, milliseconds)
        if result == WAIT_OBJECT_0:
            return True
        if result == WAIT_TIMEOUT:
            return False
        if result == WAIT_FAILED:
            self._raise_last_error("WaitForSingleObject")
        raise TerminalBackendError(f"Unexpected console wait result: {result:#x}")

    def read_input_records(
        self,
        handle: int,
        maximum: int = 128,
    ) -> list[WindowsInputRecord]:
        records = (_INPUT_RECORD * maximum)()
        count = ctypes.c_uint32()
        if not self.kernel32.ReadConsoleInputW(
            handle,
            records,
            maximum,
            ctypes.byref(count),
        ):
            self._raise_last_error("ReadConsoleInputW")

        result: list[WindowsInputRecord] = []
        for index in range(count.value):
            record = records[index]
            if record.EventType == KEY_EVENT:
                key = record.Event.KeyEvent
                char = chr(key.uChar.UnicodeChar) if key.uChar.UnicodeChar else ""
                result.append(
                    WindowsKeyRecord(
                        bool(key.bKeyDown),
                        key.wRepeatCount,
                        key.wVirtualKeyCode,
                        char,
                        key.dwControlKeyState,
                    )
                )
            elif record.EventType == MOUSE_EVENT:
                mouse = record.Event.MouseEvent
                result.append(
                    WindowsMouseRecord(
                        mouse.dwMousePosition.X,
                        mouse.dwMousePosition.Y,
                        mouse.dwButtonState,
                        mouse.dwEventFlags,
                    )
                )
            elif record.EventType == WINDOW_BUFFER_SIZE_EVENT:
                size = record.Event.WindowBufferSizeEvent.dwSize
                result.append(WindowsResizeRecord(size.X, size.Y))
        return result

    def get_window_origin(self, handle: int) -> tuple[int, int]:
        info = _CONSOLE_SCREEN_BUFFER_INFO()
        if not self.kernel32.GetConsoleScreenBufferInfo(handle, ctypes.byref(info)):
            self._raise_last_error("GetConsoleScreenBufferInfo")
        return info.srWindow.Left, info.srWindow.Top

    @staticmethod
    def _raise_last_error(function_name: str) -> None:
        error = ctypes.get_last_error()
        raise TerminalBackendError(
            f"{function_name} failed with Windows error {error}: "
            f"{ctypes.FormatError(error).strip()}"
        )


class WindowsTerminalBackend:
    """Configure and consume a real Windows console."""

    supports_ansi = False
    supports_mouse = False
    supports_resize_events = False

    def __init__(self, stdin=None, stdout=None, api=None) -> None:
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout
        self.api = api or WindowsConsoleAPI()
        self.diagnostic: str | None = None
        self.input_handle: int | None = None
        self.output_handle: int | None = None
        self.original_input_mode: int | None = None
        self.original_output_mode: int | None = None
        self.original_input_cp: int | None = None
        self.original_output_cp: int | None = None
        self._pending: deque[TerminalEvent] = deque()
        self._translator = WindowsRecordTranslator()
        self._entered = False

    def enter(self) -> None:
        if self._entered:
            return
        self.diagnostic = None
        if not self.stdin.isatty() or not self.stdout.isatty():
            raise TerminalBackendError(
                "Primelock GIS requires a real interactive Windows console; "
                "stdin or stdout is redirected. Run it in Windows Terminal."
            )

        try:
            self.input_handle = self.api.get_std_handle(STD_INPUT_HANDLE)
            self.output_handle = self.api.get_std_handle(STD_OUTPUT_HANDLE)
            self.original_input_mode = self.api.get_console_mode(self.input_handle)
            self.original_output_mode = self.api.get_console_mode(self.output_handle)
            self.original_input_cp = self.api.get_console_cp()
            self.original_output_cp = self.api.get_console_output_cp()

            output_mode = self.original_output_mode | ENABLE_PROCESSED_OUTPUT
            output_mode |= ENABLE_VIRTUAL_TERMINAL_PROCESSING
            if not self.api.set_console_mode(self.output_handle, output_mode):
                raise TerminalBackendError(
                    "This console cannot enable ANSI virtual-terminal output. "
                    "Run Primelock GIS in a current Windows Terminal session."
                )
            self.supports_ansi = True

            input_mode = self.original_input_mode | ENABLE_PROCESSED_INPUT
            input_mode |= (
                ENABLE_EXTENDED_FLAGS | ENABLE_MOUSE_INPUT | ENABLE_WINDOW_INPUT
            )
            input_mode &= ~(
                ENABLE_LINE_INPUT
                | ENABLE_ECHO_INPUT
                | ENABLE_QUICK_EDIT_MODE
                | ENABLE_VIRTUAL_TERMINAL_INPUT
            )
            if self.api.set_console_mode(self.input_handle, input_mode):
                self.supports_mouse = True
                self.supports_resize_events = True
            else:
                keyboard_mode = self.original_input_mode | ENABLE_PROCESSED_INPUT
                keyboard_mode |= ENABLE_EXTENDED_FLAGS
                keyboard_mode &= ~(
                    ENABLE_LINE_INPUT
                    | ENABLE_ECHO_INPUT
                    | ENABLE_QUICK_EDIT_MODE
                    | ENABLE_VIRTUAL_TERMINAL_INPUT
                    | ENABLE_MOUSE_INPUT
                    | ENABLE_WINDOW_INPUT
                )
                if not self.api.set_console_mode(self.input_handle, keyboard_mode):
                    raise TerminalBackendError(
                        "The Windows console input mode could not be configured."
                    )
                self._add_diagnostic(
                    "Mouse and resize input are unavailable in this console; "
                    "keyboard controls remain active. Try Windows Terminal for full input."
                )

            if not self.api.set_console_cp(CP_UTF8):
                self._add_diagnostic(
                    "The console input code page could not be set to UTF-8."
                )
            if not self.api.set_console_output_cp(CP_UTF8):
                self._add_diagnostic(
                    "The console output code page could not be set to UTF-8."
                )
            self._entered = True
        except BaseException as enter_error:
            try:
                self.exit()
            except BaseException as cleanup_error:
                if hasattr(enter_error, "add_note"):
                    enter_error.add_note(
                        f"Windows console rollback also failed: {cleanup_error}"
                    )
            raise

    def exit(self) -> None:
        errors: list[str] = []

        def restore(description: str, action) -> None:
            try:
                if not action():
                    errors.append(description)
            except BaseException:
                errors.append(description)

        if self.input_handle is not None and self.original_input_mode is not None:
            restore(
                "input console mode",
                lambda: self.api.set_console_mode(
                    self.input_handle, self.original_input_mode  # type: ignore[arg-type]
                ),
            )
        if self.output_handle is not None and self.original_output_mode is not None:
            restore(
                "output console mode",
                lambda: self.api.set_console_mode(
                    self.output_handle, self.original_output_mode  # type: ignore[arg-type]
                ),
            )
        if self.original_input_cp is not None:
            restore(
                "input console code page",
                lambda: self.api.set_console_cp(self.original_input_cp),
            )
        if self.original_output_cp is not None:
            restore(
                "output console code page",
                lambda: self.api.set_console_output_cp(self.original_output_cp),
            )

        self._entered = False
        self.supports_ansi = False
        self.supports_mouse = False
        self.supports_resize_events = False
        self.input_handle = None
        self.output_handle = None
        self.original_input_mode = None
        self.original_output_mode = None
        self.original_input_cp = None
        self.original_output_cp = None
        self._pending.clear()
        self._translator = WindowsRecordTranslator()
        if errors:
            self._add_diagnostic("Could not restore " + ", ".join(errors) + ".")
            raise TerminalBackendError(self.diagnostic)

    def read_event(self, timeout: float = 0.05) -> TerminalEvent | None:
        if self._pending:
            return self._pending.popleft()
        if not self._entered or self.input_handle is None:
            raise TerminalBackendError("The Windows terminal backend is not active.")
        if not self.api.wait_for_input(self.input_handle, timeout):
            return None

        origin = (0, 0)
        if self.output_handle is not None:
            try:
                origin = self.api.get_window_origin(self.output_handle)
            except TerminalBackendError:
                pass
        for record in self.api.read_input_records(self.input_handle):
            self._pending.extend(self._translator.translate(record, origin))
        return self._pending.popleft() if self._pending else None

    def _add_diagnostic(self, message: str) -> None:
        if self.diagnostic:
            self.diagnostic = f"{self.diagnostic} {message}"
        else:
            self.diagnostic = message
