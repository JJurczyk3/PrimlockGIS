"""Interactive support panel for the second terminal window."""

from dataclasses import dataclass, field
import os
from pathlib import Path
from queue import Queue
import shutil
import socket
import socketserver
import subprocess
import sys
import textwrap
import threading
import time

from primelock_gis.ui.terminal.events import KeyEvent, MouseEvent, TerminalEvent
from primelock_gis.ui.terminal.input import read_terminal_event
from primelock_gis.ui.terminal.screen import clear_screen, draw_frame
from primelock_gis.ui.terminal.session import TerminalSession
from primelock_gis.ui.terminal.capabilities import (
    TerminalCapabilities,
    detect_terminal_capabilities,
)
from primelock_gis.ui.terminal.theme import (
    TERMINAL_THEME,
    button_state_color,
    color_text,
    status_color,
)


@dataclass
class CommandRequest:
    """A command sent from the support panel to the viewer."""
    text: str
    reply_queue: Queue[str]


@dataclass
class PanelButton:
    label: str
    action: str
    x: int
    y: int
    width: int
    height: int = 1
    state: str = "inactive"

    def contains(self, x: int, y: int) -> bool:
        return (
            self.x <= x < self.x + self.width
            and self.y <= y < self.y + self.height
        )

    @property
    def disabled(self) -> bool:
        return self.state == "disabled"


@dataclass
class SupportPanelState:
    mode: str = "info"
    previous_mode: str = "info"
    synced_viewer_mode: str | None = None
    running: bool = True
    status: str = "Ready"
    command_buffer: str = ""
    command_output: list[str] = field(default_factory=list)
    selected_feature: str = "No feature selected."
    layer_summary: str = "Layers not loaded."
    config_summary: str = "Config not loaded."
    model_summary: str = "Model not loaded."
    dataset_path: str = "unknown"
    grid_x_divisions: int = 20
    grid_y_divisions: int = 20
    grid_input_focus: str | None = None
    grid_x_input: str = ""
    grid_y_input: str = ""
    grid_input_replace_on_type: bool = False
    terrain_opacity: float = 1.0
    terrain_palette: str = "elevation"
    terrain_source: str = "grid"


class CommandServer(socketserver.ThreadingTCPServer):
    """Local TCP server used by the viewer to receive support commands."""

    allow_reuse_address = True

    def __init__(self, server_address, handler_class, command_queue):
        super().__init__(server_address, handler_class)
        self.command_queue = command_queue

    def handle_error(self, request, client_address) -> None:
        """Suppress expected short-connection socket resets."""
        error_type, _, _ = sys.exc_info()

        if (
            error_type is not None
            and issubclass(error_type, (ConnectionResetError, BrokenPipeError))
        ):
            return

        super().handle_error(request, client_address)


class CommandHandler(socketserver.StreamRequestHandler):
    """Handle one support-panel connection."""

    def handle(self):
        try:
            raw_line = self.rfile.readline()
        except ConnectionResetError:
            return

        if not raw_line:
            return

        text = raw_line.decode("utf-8").strip()

        if not text:
            return

        reply_queue = Queue(maxsize=1)
        request = CommandRequest(
            text=text,
            reply_queue=reply_queue,
        )

        self.server.command_queue.put(request)

        try:
            response = reply_queue.get(timeout=2.0)
        except Exception:
            response = "ERROR: viewer did not respond"

        try:
            self.wfile.write((response + "\n").encode("utf-8"))
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return


def start_command_server(
        command_queue,
        host: str = "127.0.0.1",
        port: int = 8765,
) -> CommandServer:
    """Start the viewer command server in a background thread."""
    server = CommandServer(
        (host, port),
        CommandHandler,
        command_queue,
    )

    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )
    thread.start()
    return server


def send_command(
        command: str,
        host: str = "127.0.0.1",
        port: int = 8765,
) -> str:
    """Send one command to the viewer and return the response."""
    with socket.create_connection((host, port), timeout=2.0) as sock:
        file = sock.makefile("rwb")

        file.write((command + "\n").encode("utf-8"))
        file.flush()

        response = file.readline().decode("utf-8").strip()

        if not response:
            return "ERROR: viewer closed connection without response"
    return response


class SupportPanelApp:
    """Run the second-terminal support panel."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        viewer_launch_command: str | None = None,
        working_directory: Path | str | None = None,
        capabilities: TerminalCapabilities | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.viewer_launch_command = (
            viewer_launch_command
            or os.environ.get("PRIMLOCK_GIS_VIEWER_LAUNCH_COMMAND")
        )
        self.working_directory = Path(working_directory or Path.cwd())
        self.capabilities = capabilities or detect_terminal_capabilities()
        self.state = SupportPanelState()
        self.buttons: list[PanelButton] = []
        self.viewer_process: subprocess.Popen | None = None

    def run(self) -> None:
        """Run the support panel loop."""
        with TerminalSession():
            self.activate_button("mode:info")

            while self.state.running:
                self.refresh_viewer_state()
                self.render()
                event = read_terminal_event(timeout=0.08)

                if event is not None:
                    self.handle_event(event)

    def refresh_viewer_state(self) -> None:
        """Poll lightweight viewer state needed by the current panel."""
        if self.state.synced_viewer_mode != self.state.mode:
            self._sync_viewer_mode()

        if self.state.mode == "info":
            response = self.send("selected feature")
            if response.startswith("OK: "):
                self.state.selected_feature = response.removeprefix("OK: ")
            elif response.startswith("ERROR: "):
                self.state.status = response

        if self.state.mode == "layers":
            self._refresh_layers()

        if self.state.mode in ("model", "dataset"):
            self._refresh_config()

        if self.state.mode == "dataset":
            self._refresh_model_summary()

    def render(self) -> None:
        """Render the current panel to the support terminal."""
        terminal_size = shutil.get_terminal_size()
        width = max(30, terminal_size.columns)
        height = max(10, terminal_size.lines)
        lines = [" " * width for _ in range(height)]

        self.buttons = []
        self._write_line(
            lines,
            0,
            "PrimlockGIS Support Panel",
            color=TERMINAL_THEME.foreground,
        )
        self._render_top_buttons(lines, width)

        if self.state.mode == "info":
            self._render_info_panel(lines, width, start_y=5)
        elif self.state.mode == "layers":
            self._render_layers_panel(lines, width, start_y=5)
        elif self.state.mode == "model":
            self._render_model_panel(lines, width, start_y=5)
        elif self.state.mode == "dataset":
            self._render_dataset_panel(lines, width, start_y=5)
        elif self.state.mode == "admin":
            self._render_admin_panel(lines, width, height, start_y=5)
        else:
            self._render_help_panel(lines, width, start_y=5)

        self._write_line(
            lines,
            height - 2,
            "-" * width,
            color=TERMINAL_THEME.frame,
        )
        self._write_line(
            lines,
            height - 1,
            self._status_line(),
            width,
            color=status_color(self.state.status),
        )

        clear_screen()
        draw_frame("\n".join(lines))

    def handle_event(self, event: TerminalEvent) -> None:
        """Route one support-panel event."""
        if isinstance(event, MouseEvent):
            self.handle_mouse(event)
            return

        if isinstance(event, KeyEvent):
            self.handle_key(event.key)

    def handle_mouse(self, event: MouseEvent) -> None:
        """Handle support-panel mouse clicks."""
        if event.kind != "press" or event.button != 0:
            return

        for button in self.buttons:
            if button.contains(event.x, event.y):
                if button.disabled:
                    self.state.status = f"WARN: {button.label} is disabled"
                    return
                self.activate_button(button.action)
                return

    def handle_key(self, key: str) -> None:
        """Handle support-panel keyboard input."""
        if self.state.mode == "admin":
            self.handle_admin_key(key)
            return

        if self.state.mode == "model" and self.handle_model_key(key):
            return

        if key == "q":
            self.state.running = False
            return

        if key == "i":
            self.activate_button("mode:info")
        elif key == "l":
            self.activate_button("mode:layers")
        elif key == "m":
            self.activate_button("mode:model")
        elif key == "d":
            self.activate_button("mode:dataset")
        elif key == "a":
            self.activate_button("mode:admin")
        elif key == "?":
            self.activate_button("mode:help")

    def handle_admin_key(self, key: str) -> None:
        """Handle typed command input inside Admin mode."""
        if key == "escape":
            self.state.mode = self.state.previous_mode
            self._sync_viewer_mode()
            return

        if key in ("\r", "\n"):
            self.run_admin_command()
            return

        if key in ("\x7f", "\b"):
            self.state.command_buffer = self.state.command_buffer[:-1]
            return

        if len(key) == 1 and key.isprintable():
            self.state.command_buffer += key

    def handle_model_key(self, key: str) -> bool:
        """Handle typed grid-division input inside Model mode."""
        if self.state.grid_input_focus is None:
            if key == "x":
                self._focus_grid_input("x")
                return True
            if key == "y":
                self._focus_grid_input("y")
                return True
            if key in ("\r", "\n") and (
                self.state.grid_x_input or self.state.grid_y_input
            ):
                self._apply_grid_input()
                return True
            return False

        if key == "escape":
            self._cancel_grid_input()
            return True

        if key == "\t":
            self._focus_grid_input(
                "y" if self.state.grid_input_focus == "x" else "x"
            )
            return True

        if key in ("\r", "\n"):
            self._apply_grid_input()
            return True

        if key in ("\x7f", "\b"):
            self._backspace_grid_input()
            return True

        if len(key) == 1 and key.isdigit():
            self._append_grid_input_digit(key)
            return True

        return True

    def run_admin_command(self) -> None:
        """Send the current admin-mode command to the viewer."""
        command = self.state.command_buffer.strip()
        self.state.command_buffer = ""

        if not command:
            return

        if command in ("exit", "quit"):
            self.state.mode = self.state.previous_mode
            self._sync_viewer_mode()
            return

        self._run_admin_command_text(command)

    def _focus_grid_input(self, axis: str) -> None:
        """Focus one Model-tab grid input field."""
        if axis not in ("x", "y"):
            return

        self.state.grid_input_focus = axis
        if axis == "x" and not self.state.grid_x_input:
            self.state.grid_x_input = str(self.state.grid_x_divisions)
            self.state.grid_input_replace_on_type = True
        elif axis == "y" and not self.state.grid_y_input:
            self.state.grid_y_input = str(self.state.grid_y_divisions)
            self.state.grid_input_replace_on_type = True
        else:
            self.state.grid_input_replace_on_type = False

    def _cancel_grid_input(self) -> None:
        """Cancel typed Model-tab grid input."""
        self.state.grid_input_focus = None
        self.state.grid_x_input = ""
        self.state.grid_y_input = ""
        self.state.grid_input_replace_on_type = False
        self.state.status = "OK: grid input cancelled"

    def _backspace_grid_input(self) -> None:
        """Remove one digit from the focused grid input."""
        if self.state.grid_input_focus == "x":
            value = self.state.grid_x_input
            self.state.grid_x_input = (
                "" if self.state.grid_input_replace_on_type else value[:-1]
            )
        elif self.state.grid_input_focus == "y":
            value = self.state.grid_y_input
            self.state.grid_y_input = (
                "" if self.state.grid_input_replace_on_type else value[:-1]
            )

        self.state.grid_input_replace_on_type = False

    def _append_grid_input_digit(self, digit: str) -> None:
        """Append or replace one digit in the focused grid input."""
        if self.state.grid_input_focus == "x":
            if self.state.grid_input_replace_on_type:
                self.state.grid_x_input = digit
            else:
                self.state.grid_x_input += digit
        elif self.state.grid_input_focus == "y":
            if self.state.grid_input_replace_on_type:
                self.state.grid_y_input = digit
            else:
                self.state.grid_y_input += digit

        self.state.grid_input_replace_on_type = False

    def _apply_grid_input(self) -> None:
        """Apply typed Model-tab grid divisions through the viewer command."""
        x_text = self.state.grid_x_input or str(self.state.grid_x_divisions)
        y_text = self.state.grid_y_input or str(self.state.grid_y_divisions)

        try:
            x_value = int(x_text)
            y_value = int(y_text)
        except ValueError:
            self.state.status = "ERROR: grid divisions must be integers"
            return

        if x_value < 1 or y_value < 1:
            self.state.status = "ERROR: grid divisions must be positive"
            return

        response = self.send(f"set grid {x_value} {y_value}")
        self.state.status = response

        if response.startswith("OK: "):
            self.state.grid_x_divisions = x_value
            self.state.grid_y_divisions = y_value
            self.state.grid_input_focus = None
            self.state.grid_x_input = ""
            self.state.grid_y_input = ""
            self.state.grid_input_replace_on_type = False
            self._refresh_config()

    def activate_button(self, action: str) -> None:
        """Run one support-panel button action."""
        if action.startswith("mode:"):
            mode = action.split(":", 1)[1]
            if mode == "admin":
                self.state.previous_mode = self.state.mode
            self.state.mode = mode
            self._sync_viewer_mode()
            return

        if action.startswith("command:"):
            command = action.split(":", 1)[1]
            response = self.send(command)
            self.state.status = response
            if self.state.mode == "layers":
                self._refresh_layers()
            if self.state.mode in ("model", "dataset"):
                self._refresh_config()
            if self.state.mode == "dataset":
                self._refresh_model_summary()

        if action.startswith("model-input:"):
            axis = action.split(":", 1)[1]
            self._focus_grid_input(axis)

        if action == "model-grid-apply":
            self._apply_grid_input()

        if action.startswith("admin:"):
            command = action.split(":", 1)[1]
            self._run_admin_command_text(command)

    def _run_admin_command_text(self, command: str) -> None:
        """Run one Admin-panel command and record its output."""
        response = self.handle_admin_command(command)
        self.state.command_output.extend([f"> {command}", response])
        self.state.command_output = self.state.command_output[-12:]
        self.state.status = response

    def handle_admin_command(self, command: str) -> str:
        """Handle Admin-panel commands, including local viewer lifecycle control."""
        parts = command.strip().lower().split()

        if not parts:
            return "ERROR: empty command"

        if parts == ["help"]:
            return (
                "OK: commands: viewer status, start viewer, "
                "quit viewer, restart viewer, summary, contour summary, "
                "config, model summary, set grid X Y, load dataset PATH, "
                "reload dataset, contour interval N, contour source grid|tin, "
                "terrain opacity N, terrain palette elevation|grayscale|heat"
            )

        if parts in (["viewer", "status"], ["status"]):
            response = self.send("summary")
            if response.startswith("OK: "):
                return f"OK: viewer responding | {response.removeprefix('OK: ')}"
            return f"ERROR: viewer not responding | {response}"

        if parts in (["start", "viewer"], ["viewer", "start"]):
            return self.start_viewer()

        if parts in (["quit", "viewer"], ["stop", "viewer"], ["viewer", "quit"]):
            return self.quit_viewer()

        if parts in (["restart", "viewer"], ["viewer", "restart"]):
            return self.restart_viewer()

        return self.send(command)

    def start_viewer(self) -> str:
        """Start a viewer using the configured launch command."""
        response = self.send("summary")
        if response.startswith("OK: "):
            return "OK: viewer already responding"

        if self.viewer_process is not None and self.viewer_process.poll() is None:
            return f"OK: viewer process already started pid={self.viewer_process.pid}"

        if not self.viewer_launch_command:
            return (
                "ERROR: viewer launch command is not configured. "
                "Set PRIMLOCK_GIS_VIEWER_LAUNCH_COMMAND."
            )

        try:
            popen_kwargs = {}
            if os.name == "nt" and hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
                popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                popen_kwargs["start_new_session"] = True

            self.viewer_process = subprocess.Popen(
                self.viewer_launch_command,
                cwd=self.working_directory,
                shell=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **popen_kwargs,
            )
        except OSError as error:
            return f"ERROR: could not start viewer: {error}"

        self.state.synced_viewer_mode = None
        return f"OK: viewer start requested pid={self.viewer_process.pid}"

    def quit_viewer(self) -> str:
        """Ask a responsive viewer to quit, or stop a locally started process."""
        response = self.send("quit viewer")
        if response.startswith("OK: "):
            self.state.synced_viewer_mode = None
            return response

        if self.viewer_process is not None and self.viewer_process.poll() is None:
            self.viewer_process.terminate()
            self.state.synced_viewer_mode = None
            return f"OK: viewer process terminated pid={self.viewer_process.pid}"

        return f"ERROR: viewer not responding | {response}"

    def restart_viewer(self) -> str:
        """Quit the current viewer if possible, then start a new one."""
        quit_response = self.quit_viewer()
        time.sleep(0.2)
        start_response = self.start_viewer()

        if start_response.startswith("OK: "):
            return f"{start_response} | previous={quit_response}"

        return f"{start_response} | previous={quit_response}"

    def _sync_viewer_mode(self) -> None:
        """Tell the viewer which interaction mode should be active."""
        if self.state.mode == "info":
            self.state.status = self.send("mode info")
            if self.state.status.startswith("OK: "):
                self.state.synced_viewer_mode = self.state.mode
            else:
                self.state.synced_viewer_mode = None
            return

        self.state.status = self.send("mode normal")
        if self.state.status.startswith("OK: "):
            self.state.synced_viewer_mode = self.state.mode
        else:
            self.state.synced_viewer_mode = None

    def send(self, command: str) -> str:
        """Send a support command to the viewer, returning an error string on failure."""
        try:
            return send_command(command, self.host, self.port)
        except OSError as error:
            return f"ERROR: could not connect to viewer: {error}"

    def _render_top_buttons(self, lines: list[str], width: int) -> None:
        x = 0
        labels = [
            ("Info", "mode:info"),
            ("Layers", "mode:layers"),
            ("Model", "mode:model"),
            ("Dataset", "mode:dataset"),
            ("Admin", "mode:admin"),
            ("Help", "mode:help"),
        ]

        for label, action in labels:
            mode = action.split(":", 1)[1]
            state = "active" if self.state.mode == mode else "inactive"
            button = self._draw_button(
                lines,
                x=x,
                y=1,
                label=label,
                action=action,
                state=state,
            )
            x += button.width + 1

            if x >= width:
                break

    def _render_info_panel(
        self,
        lines: list[str],
        width: int,
        start_y: int = 4,
    ) -> None:
        self._write_line(lines, start_y, "Info Mode", width, color=TERMINAL_THEME.active)
        self._write_line(lines, start_y + 1, "Click a feature in the viewer terminal.", width)
        self._write_line(lines, start_y + 3, "Selected feature:", width)

        row = start_y + 4
        for text in self._split_info_text(self.state.selected_feature):
            row = self._write_wrapped_line(lines, row, text, width)

    def _render_layers_panel(
        self,
        lines: list[str],
        width: int,
        start_y: int = 4,
    ) -> None:
        self._write_line(lines, start_y, "Layers", width, color=TERMINAL_THEME.active)
        self._write_wrapped_line(lines, start_y + 1, self.state.layer_summary, width)

        actions = [
            ("Toggle Points", "command:toggle points"),
            ("Toggle Terrain", "command:toggle terrain"),
            ("Toggle Grid", "command:toggle grid"),
            ("Toggle TIN", "command:toggle tin"),
            ("Toggle Contours", "command:toggle contours"),
            ("Contour Source", "command:toggle contour source"),
            ("Toggle Labels", "command:toggle contour labels"),
        ]

        for index, (label, action) in enumerate(actions):
            y = start_y + 3 + (index // 2) * 3
            x = (index % 2) * 22
            layer_name = self._layer_name_for_action(action)
            state = self._layer_button_state(layer_name)
            self._draw_button(
                lines,
                x=x,
                y=y,
                label=label,
                action=action,
                state=state,
            )

        terrain_y = start_y + 15
        opacity_percent = round(self.state.terrain_opacity * 100)
        self._write_line(
            lines,
            terrain_y,
            (
                f"Terrain: source={self.state.terrain_source} "
                f"palette={self.state.terrain_palette} "
                f"opacity={opacity_percent}%"
            ),
            width,
        )
        lower_opacity = max(0.0, self.state.terrain_opacity - 0.1)
        higher_opacity = min(1.0, self.state.terrain_opacity + 0.1)
        self._draw_button(
            lines,
            x=0,
            y=terrain_y + 2,
            label="Opacity -",
            action=f"command:terrain opacity {lower_opacity:.1f}",
            state="inactive" if self.state.terrain_opacity > 0.0 else "disabled",
        )
        self._draw_button(
            lines,
            x=14,
            y=terrain_y + 2,
            label="Opacity +",
            action=f"command:terrain opacity {higher_opacity:.1f}",
            state="inactive" if self.state.terrain_opacity < 1.0 else "disabled",
        )
        self._draw_button(
            lines,
            x=28,
            y=terrain_y + 2,
            label="Palette",
            action="command:cycle terrain palette",
            state="focused",
        )

    def _render_model_panel(
        self,
        lines: list[str],
        width: int,
        start_y: int = 4,
    ) -> None:
        self._write_line(
            lines,
            start_y,
            "Model Settings",
            width,
            color=TERMINAL_THEME.active,
        )
        self._write_wrapped_line(lines, start_y + 1, self.state.config_summary, width)
        self._write_line(lines, start_y + 3, "Grid divisions", width)

        x_value = self.state.grid_x_divisions
        y_value = self.state.grid_y_divisions
        self._write_line(lines, start_y + 5, f"X: {x_value}", width)
        self._draw_button(
            lines,
            x=10,
            y=start_y + 4,
            label="-",
            action=f"command:set grid {max(1, x_value - 1)} {y_value}",
            state="inactive" if x_value > 1 else "disabled",
            width=5,
        )
        self._draw_button(
            lines,
            x=16,
            y=start_y + 4,
            label="+",
            action=f"command:set grid {x_value + 1} {y_value}",
            state="inactive",
            width=5,
        )

        self._write_line(lines, start_y + 8, f"Y: {y_value}", width)
        self._draw_button(
            lines,
            x=10,
            y=start_y + 7,
            label="-",
            action=f"command:set grid {x_value} {max(1, y_value - 1)}",
            state="inactive" if y_value > 1 else "disabled",
            width=5,
        )
        self._draw_button(
            lines,
            x=16,
            y=start_y + 7,
            label="+",
            action=f"command:set grid {x_value} {y_value + 1}",
            state="inactive",
            width=5,
        )

        self._write_line(lines, start_y + 11, "Typed divisions", width)
        self._write_at(lines, 0, start_y + 13, "X", width)
        self._draw_button(
            lines,
            x=3,
            y=start_y + 12,
            label=self._grid_input_label("x"),
            action="model-input:x",
            state=self._grid_input_state("x"),
            width=12,
        )
        self._write_at(lines, 15, start_y + 13, "Y", width)
        self._draw_button(
            lines,
            x=18,
            y=start_y + 12,
            label=self._grid_input_label("y"),
            action="model-input:y",
            state=self._grid_input_state("y"),
            width=12,
        )
        self._draw_button(
            lines,
            x=33,
            y=start_y + 12,
            label="Apply",
            action="model-grid-apply",
            state="success",
            width=10,
        )

        self._write_line(lines, start_y + 16, "Presets", width)
        preset_x = 0
        for divisions in (10, 20, 40):
            state = (
                "active"
                if (x_value, y_value) == (divisions, divisions)
                else "inactive"
            )
            button = self._draw_button(
                lines,
                x=preset_x,
                y=start_y + 17,
                label=f"{divisions}x{divisions}",
                action=f"command:set grid {divisions} {divisions}",
                state=state,
            )
            preset_x += button.width + 1

    def _render_dataset_panel(
        self,
        lines: list[str],
        width: int,
        start_y: int = 4,
    ) -> None:
        self._write_line(
            lines,
            start_y,
            "Dataset",
            width,
            color=TERMINAL_THEME.active,
        )
        self._write_line(lines, start_y + 2, "Current:", width)
        self._write_wrapped_line(lines, start_y + 3, self.state.dataset_path, width)
        self._draw_button(
            lines,
            x=0,
            y=start_y + 6,
            label="Reload",
            action="command:reload dataset",
            state="warning",
        )
        self._write_line(lines, start_y + 10, "Config:", width)
        row = self._write_wrapped_line(lines, start_y + 11, self.state.config_summary, width)
        self._write_line(lines, row + 1, "Model:", width)
        self._write_wrapped_line(lines, row + 2, self.state.model_summary, width)
        self._write_wrapped_line(
            lines,
            row + 5,
            "Use Admin for: load dataset <path>",
            width,
            color=TERMINAL_THEME.muted,
        )

    def _render_admin_panel(
        self,
        lines: list[str],
        width: int,
        height: int,
        start_y: int = 4,
    ) -> None:
        self._write_line(
            lines,
            start_y,
            "Admin Mode",
            width,
            color=TERMINAL_THEME.focused,
        )
        self._write_wrapped_line(
            lines,
            start_y + 1,
            "Commands run here even when viewer is down.",
            width,
        )
        self._render_admin_buttons(lines, width, y=start_y + 3)
        self._write_line(
            lines,
            start_y + 7,
            f"> {self.state.command_buffer}",
            width,
            color=TERMINAL_THEME.focused,
        )
        self._write_line(lines, start_y + 9, "Output:", width)

        available_rows = max(0, height - (start_y + 12))
        output_lines = self._wrap_lines(self.state.command_output, width)
        output_lines = output_lines[-available_rows:]

        for offset, text in enumerate(output_lines):
            self._write_line(lines, start_y + 10 + offset, text, width)

    def _render_admin_buttons(self, lines: list[str], width: int, y: int = 7) -> None:
        actions = [
            ("Status", "admin:viewer status"),
            ("Start", "admin:start viewer"),
            ("Quit", "admin:quit viewer"),
            ("Restart", "admin:restart viewer"),
            ("Config", "admin:config"),
            ("Summary", "admin:model summary"),
        ]
        x = 0

        for label, action in actions:
            state = "warning" if label in ("Quit", "Restart") else "focused"
            button = self._draw_button(
                lines,
                x=x,
                y=y,
                label=label,
                action=action,
                state=state,
            )
            x += button.width + 1

            if x >= width:
                break

    def _render_help_panel(
        self,
        lines: list[str],
        width: int,
        start_y: int = 4,
    ) -> None:
        help_lines = [
            "Help",
            "i: Info mode",
            "l: Layers mode",
            "m: Model mode",
            "d: Dataset mode",
            "a: Admin mode",
            "?: Help mode",
            "q: quit support panel",
            "Mouse: click panel buttons",
            "",
            "Viewer controls stay in the viewer terminal:",
            "h/j/k/l pan, +/- zoom, mouse drag pan.",
            "b terrain, c contours, m contour source, v labels.",
            "",
            "Admin: viewer status, quit viewer, restart viewer, summary.",
            "Model admin: set grid 30 30, load dataset path.csv, reload dataset.",
            "Contour admin: contour interval 25, contour source tin.",
            "Terrain admin: terrain opacity 0.7, terrain palette heat.",
        ]

        row = start_y
        for text in help_lines:
            row = self._write_wrapped_line(lines, row, text, width)

    def _draw_button(
        self,
        lines: list[str],
        x: int,
        y: int,
        label: str,
        action: str,
        state: str = "inactive",
        width: int | None = None,
    ) -> PanelButton:
        """Draw a framed button and register its hit target."""
        if width is None:
            width = max(6, len(label) + 4)

        inner_width = max(1, width - 2)
        clipped_label = label[:inner_width]
        padding = inner_width - len(clipped_label)
        left_padding = padding // 2
        right_padding = padding - left_padding
        color = button_state_color(state)

        self._write_at(lines, x, y, "┌" + "─" * inner_width + "┐", color=color)
        self._write_at(
            lines,
            x,
            y + 1,
            "│" + " " * left_padding + clipped_label + " " * right_padding + "│",
            color=color,
        )
        self._write_at(lines, x, y + 2, "└" + "─" * inner_width + "┘", color=color)

        button = PanelButton(
            label=label,
            action=action,
            x=x,
            y=y,
            width=width,
            height=3,
            state=state,
        )
        self.buttons.append(button)
        return button

    def _refresh_config(self) -> None:
        """Fetch and parse the current viewer project config."""
        response = self.send("config")
        if response.startswith("OK: "):
            self.state.config_summary = response.removeprefix("OK: ")
            self._parse_config_summary(self.state.config_summary)
            return

        if response.startswith("ERROR: "):
            self.state.status = response

    def _refresh_layers(self) -> None:
        """Fetch and parse the current viewer layer state."""
        response = self.send("layers summary")
        if response.startswith("OK: "):
            self.state.layer_summary = response.removeprefix("OK: ")
            self._parse_layer_summary(self.state.layer_summary)
            return

        if response.startswith("ERROR: "):
            self.state.status = response

    def _refresh_model_summary(self) -> None:
        """Fetch the current viewer model summary."""
        response = self.send("model summary")
        if response.startswith("OK: "):
            self.state.model_summary = response.removeprefix("OK: ")
            return

        if response.startswith("ERROR: "):
            self.state.status = response

    def _parse_config_summary(self, summary: str) -> None:
        """Parse the viewer's compact config summary for panel controls."""
        grid_marker = " grid="
        if summary.startswith("dataset=") and grid_marker in summary:
            dataset_text, remainder = summary.split(grid_marker, 1)
            self.state.dataset_path = dataset_text.removeprefix("dataset=")
            summary = "grid=" + remainder

        values = {}
        for token in summary.split():
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            values[key] = value

        grid_text = values.get("grid")
        if grid_text and "x" in grid_text:
            x_text, y_text = grid_text.split("x", 1)
            try:
                self.state.grid_x_divisions = int(x_text)
                self.state.grid_y_divisions = int(y_text)
            except ValueError:
                pass

    def _parse_layer_summary(self, summary: str) -> None:
        """Parse terrain control values from the viewer layer summary."""
        values = {}
        for token in summary.split():
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            values[key] = value

        if "terrain_source" in values:
            self.state.terrain_source = values["terrain_source"]

        if "terrain_palette" in values:
            self.state.terrain_palette = values["terrain_palette"]

        if "terrain_opacity" in values:
            try:
                self.state.terrain_opacity = float(values["terrain_opacity"])
            except ValueError:
                pass

    def _grid_input_label(self, axis: str) -> str:
        """Return the label shown inside one typed grid input field."""
        if axis == "x":
            value = self.state.grid_x_input or str(self.state.grid_x_divisions)
        else:
            value = self.state.grid_y_input or str(self.state.grid_y_divisions)

        if self.state.grid_input_focus == axis:
            return value + "_"

        return value

    def _grid_input_state(self, axis: str) -> str:
        """Return the visual state for one typed grid input field."""
        if self.state.grid_input_focus == axis:
            return "focused"

        return "inactive"

    def _layer_name_for_action(self, action: str) -> str:
        if action.endswith("toggle points"):
            return "points"
        if action.endswith("toggle terrain"):
            return "terrain"
        if action.endswith("toggle grid"):
            return "grid"
        if action.endswith("toggle tin"):
            return "tin"
        if action.endswith("toggle contours"):
            return "contours"
        if action.endswith("toggle contour labels"):
            return "contour_labels"
        if action.endswith("toggle contour source"):
            return "contour_source"
        return ""

    def _layer_button_state(self, layer_name: str) -> str:
        if layer_name == "contour_source":
            return "focused"

        token = f"{layer_name}=on"
        if token in self.state.layer_summary:
            return "active"
        return "inactive"

    def _status_line(self) -> str:
        return f"mode={self.state.mode} | {self.state.status}"

    def _split_info_text(self, text: str) -> list[str]:
        return [part.strip() for part in text.split(" | ") if part.strip()]

    def _write_line(
        self,
        lines: list[str],
        y: int,
        text: str,
        width: int | None = None,
        color: str | None = None,
    ) -> None:
        self._write_at(lines, 0, y, text, width, color=color)

    def _write_wrapped_line(
        self,
        lines: list[str],
        y: int,
        text: str,
        width: int | None = None,
        color: str | None = None,
    ) -> int:
        if y >= len(lines):
            return y

        if width is None:
            width = len(lines[y])

        row = y
        for wrapped_line in self._wrap_text(text, width):
            if row >= len(lines):
                break

            self._write_line(lines, row, wrapped_line, width, color=color)
            row += 1

        return row

    def _write_at(
        self,
        lines: list[str],
        x: int,
        y: int,
        text: str,
        width: int | None = None,
        color: str | None = None,
    ) -> None:
        if y < 0 or y >= len(lines):
            return

        if width is None:
            width = self._visible_width(lines[y])

        if x >= width:
            return

        available_width = max(0, width - x)
        clipped = text[:available_width]
        line = lines[y]
        raw_start = self._raw_index_for_visible_column(line, x)
        raw_end = self._raw_index_for_visible_column(line, x + len(clipped))
        rendered = color_text(clipped, color, self.capabilities)
        lines[y] = line[:raw_start] + rendered + line[raw_end:]

    def _visible_width(self, text: str) -> int:
        """Return text width ignoring ANSI escape sequences."""
        width = 0
        index = 0

        while index < len(text):
            if text[index] == "\x1b":
                index = self._skip_ansi_sequence(text, index)
                continue

            width += 1
            index += 1

        return width

    def _raw_index_for_visible_column(self, text: str, column: int) -> int:
        """Return the raw string index at a visible column."""
        visible_column = 0
        index = 0

        while index < len(text) and visible_column < column:
            if text[index] == "\x1b":
                index = self._skip_ansi_sequence(text, index)
                continue

            visible_column += 1
            index += 1

        return index

    def _skip_ansi_sequence(self, text: str, index: int) -> int:
        if index >= len(text) or text[index] != "\x1b":
            return index + 1

        index += 1
        if index < len(text) and text[index] == "[":
            index += 1
            while index < len(text) and text[index] != "m":
                index += 1
            return min(len(text), index + 1)

        return index

    def _wrap_lines(self, texts: list[str], width: int) -> list[str]:
        wrapped_lines = []

        for text in texts:
            wrapped_lines.extend(self._wrap_text(text, width))

        return wrapped_lines

    def _wrap_text(self, text: str, width: int) -> list[str]:
        if width <= 0:
            return [""]

        if text == "":
            return [""]

        return textwrap.wrap(
            text,
            width=width,
            break_long_words=True,
            break_on_hyphens=False,
        ) or [""]


def run_support_panel(
        host: str = "127.0.0.1",
        port: int = 8765,
) -> None:
    """Run the interactive support panel terminal."""
    SupportPanelApp(host, port).run()
