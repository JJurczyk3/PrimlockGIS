"""Interactive support panel for the second terminal window."""

import os
import shutil
import socket
import socketserver
import subprocess
import sys
import textwrap
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from queue import Queue

from primelock_gis.app.launcher import runtime_command
from primelock_gis.i18n import Language, get_language, normalize_language, tr
from primelock_gis.ui.terminal.backends.base import TerminalBackendError
from primelock_gis.ui.terminal.capabilities import (
    TerminalCapabilities,
    detect_terminal_capabilities,
)
from primelock_gis.ui.terminal.events import (
    KeyEvent,
    MouseEvent,
    ResizeEvent,
    TerminalEvent,
)
from primelock_gis.ui.terminal.screen import (
    character_width,
    clear_screen,
    clip_text,
    draw_frame,
    text_width,
)
from primelock_gis.ui.terminal.session import TerminalSession
from primelock_gis.ui.terminal.theme import (
    TERMINAL_THEME,
    button_state_color,
    color_text,
    status_color,
)

COMMAND_PROTOCOL = "PRIMELOCK/1"


class ViewerProtocolError(RuntimeError):
    """Raised when a port is not serving the expected viewer session."""


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
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height

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
    terminal_warning: str | None = None


class CommandServer(socketserver.ThreadingTCPServer):
    """Local TCP server used by the viewer to receive support commands."""

    allow_reuse_address = False
    daemon_threads = True

    def __init__(
        self,
        server_address,
        handler_class,
        command_queue,
        session_token: str | None = None,
    ):
        super().__init__(server_address, handler_class)
        self.command_queue = command_queue
        self.session_token = session_token

    def handle_error(self, request, client_address) -> None:
        """Suppress expected short-connection socket resets."""
        error_type, _, _ = sys.exc_info()

        if error_type is not None and issubclass(
            error_type, (ConnectionResetError, BrokenPipeError)
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

        try:
            text = raw_line.decode("utf-8").strip()
        except UnicodeDecodeError:
            return

        if not text:
            return

        session_token = self.server.session_token
        if session_token:
            request_prefix = f"{COMMAND_PROTOCOL} {session_token} "
            if not text.startswith(request_prefix):
                self.wfile.write(f"{COMMAND_PROTOCOL} ERROR invalid session\n".encode())
                self.wfile.flush()
                return
            text = text.removeprefix(request_prefix).strip()
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
            if session_token:
                response = f"{COMMAND_PROTOCOL} {session_token} {response}"
            self.wfile.write((response + "\n").encode("utf-8"))
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return


def start_command_server(
    command_queue,
    host: str = "127.0.0.1",
    port: int = 8765,
    session_token: str | None = None,
) -> CommandServer:
    """Start the viewer command server in a background thread."""
    server = CommandServer(
        (host, port),
        CommandHandler,
        command_queue,
        session_token,
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
    session_token: str | None = None,
) -> str:
    """Send one command to the viewer and return the response."""
    with socket.create_connection((host, port), timeout=2.0) as sock:
        file = sock.makefile("rwb")

        request = command
        if session_token:
            request = f"{COMMAND_PROTOCOL} {session_token} {command}"
        file.write((request + "\n").encode("utf-8"))
        file.flush()

        raw_response = file.readline()
        try:
            response = raw_response.decode("utf-8").strip()
        except UnicodeDecodeError as error:
            raise ViewerProtocolError(
                "the selected port returned a non-UTF-8 response and is not "
                "the expected Primelock GIS viewer session"
            ) from error

        if not response:
            return "ERROR: viewer closed connection without response"
        if session_token:
            response_prefix = f"{COMMAND_PROTOCOL} {session_token} "
            if not response.startswith(response_prefix):
                raise ViewerProtocolError(
                    "the selected port is not the expected Primelock GIS viewer session"
                )
            response = response.removeprefix(response_prefix)
    return response


class SupportPanelApp:
    """Run the second-terminal support panel."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        viewer_launch_command: str | Sequence[str] | None = None,
        working_directory: Path | str | None = None,
        capabilities: TerminalCapabilities | None = None,
        session_token: str | None = None,
        startup_timeout: float = 15.0,
        connection_retry_interval: float = 0.25,
        manage_viewer: bool = False,
        clock=None,
        language: Language | str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.working_directory = Path(working_directory or Path.cwd())
        self.capabilities = capabilities or detect_terminal_capabilities()
        self.session_token = session_token
        self.startup_timeout = startup_timeout
        self.connection_retry_interval = connection_retry_interval
        self.manage_viewer = manage_viewer
        self.clock = clock or time.monotonic
        self.language = normalize_language(
            language if language is not None else get_language()
        )
        configured_viewer_command = viewer_launch_command or os.environ.get(
            "PRIMLOCK_GIS_VIEWER_LAUNCH_COMMAND"
        )
        if configured_viewer_command is None and session_token:
            configured_viewer_command = (
                *runtime_command(),
                "viewer",
                "--language",
                self.language,
                "--port",
                str(port),
                f"--session-token={session_token}",
            )
        self.viewer_launch_command = configured_viewer_command
        self.state = SupportPanelState()
        self.state.status = self._text("common.ready", "Ready", "就绪")
        self.state.selected_feature = self._text(
            "viewer.feature.none", "No feature selected.", "未选择任何要素。"
        )
        self.state.layer_summary = self._text(
            "support.layers.not_loaded", "Layers not loaded.", "图层尚未加载。"
        )
        self.state.config_summary = self._text(
            "support.config.not_loaded", "Config not loaded.", "配置尚未加载。"
        )
        self.state.model_summary = self._text(
            "support.model.not_loaded", "Model not loaded.", "模型尚未加载。"
        )
        self.buttons: list[PanelButton] = []
        self.viewer_process: subprocess.Popen | None = None
        self.viewer_connected = False
        self._reset_viewer_wait()

    def _text(self, message_key: str, english: str, chinese: str, **values) -> str:
        """Return one localized support-panel message."""
        default = chinese if self.language == "zh-CN" else english
        return tr(message_key, language=self.language, default=default, **values)

    def run(self) -> None:
        """Run the support panel loop."""
        try:
            with TerminalSession() as terminal:
                if terminal.diagnostic:
                    self.state.terminal_warning = terminal.diagnostic
                self.state.status = self._text(
                    "support.viewer.waiting",
                    "Waiting for viewer...",
                    "正在等待查看器……",
                )
                frame_dirty = True
                terminal_size = shutil.get_terminal_size()

                while self.state.running:
                    if self.refresh_viewer_state():
                        frame_dirty = True
                    next_terminal_size = shutil.get_terminal_size()
                    if next_terminal_size != terminal_size:
                        terminal_size = next_terminal_size
                        frame_dirty = True
                    if frame_dirty:
                        self.render()
                        frame_dirty = False
                    event = terminal.read_event(timeout=0.08)

                    if event is not None:
                        self.handle_event(event)
                        frame_dirty = True
        except KeyboardInterrupt:
            self.state.running = False
        except TerminalBackendError as error:
            self.state.running = False
            print(
                self._text(
                    "support.terminal.error",
                    "ERROR: {error}",
                    "错误：{error}",
                    error=error,
                ),
                file=sys.stderr,
            )
        finally:
            if self.manage_viewer:
                self._shutdown_managed_viewer()

    def refresh_viewer_state(self, now: float | None = None) -> bool:
        """Poll viewer state and report whether visible panel state changed."""
        previous_state = replace(
            self.state,
            command_output=list(self.state.command_output),
        )
        if not self._ensure_viewer_connection(now):
            return self.state != previous_state

        if self.state.synced_viewer_mode != self.state.mode:
            self._sync_viewer_mode()

        if self.state.mode == "info":
            response = self.send("selected feature")
            if response.startswith("OK: "):
                self.state.selected_feature = response.removeprefix("OK: ")
            elif response.startswith("ERROR: ") and self.viewer_connected:
                self.state.status = response

        if self.state.mode == "layers":
            self._refresh_layers()

        if self.state.mode in ("model", "dataset"):
            self._refresh_config()

        if self.state.mode == "dataset":
            self._refresh_model_summary()

        return self.state != previous_state

    def _ensure_viewer_connection(self, now: float | None = None) -> bool:
        """Pace startup probes and keep retrying after a useful timeout message."""
        if self.viewer_connected:
            return True
        now = self.clock() if now is None else now
        if now < self._next_connection_attempt:
            return False

        response = self.send("ping")
        if response == "OK: viewer ready":
            self.viewer_connected = True
            self.state.status = self._text(
                "support.viewer.connected", "Viewer connected", "查看器已连接"
            )
            self.state.synced_viewer_mode = None
            return True

        if now < self._viewer_wait_deadline:
            remaining = max(1, int(self._viewer_wait_deadline - now + 0.999))
            self.state.status = self._text(
                "support.viewer.waiting_seconds",
                "Waiting for viewer... ({remaining}s)",
                "正在等待查看器……（{remaining} 秒）",
                remaining=remaining,
            )
            retry_delay = self.connection_retry_interval
        else:
            self.state.status = self._text(
                "support.viewer.timeout",
                "ERROR: viewer did not start in time; still retrying. "
                "Run PrimelockGIS.exe doctor if this continues.",
                "ERROR: 查看器未能及时启动，系统仍在重试。"
                "如果问题持续，请运行 PrimelockGIS.exe doctor。",
            )
            retry_delay = max(2.0, self.connection_retry_interval)
        self._next_connection_attempt = now + retry_delay
        return False

    def _mark_viewer_disconnected(self) -> None:
        """Return to the paced waiting state after a connected viewer disappears."""
        was_connected = self.viewer_connected
        self.viewer_connected = False
        self.state.synced_viewer_mode = None
        if was_connected:
            self._reset_viewer_wait()

    def _reset_viewer_wait(self) -> None:
        """Start a fresh paced startup/reconnect window."""
        self.viewer_connected = False
        self.state.synced_viewer_mode = None
        now = self.clock()
        self._viewer_wait_deadline = now + self.startup_timeout
        self._next_connection_attempt = now
        self.state.status = self._text(
            "support.viewer.waiting", "Waiting for viewer...", "正在等待查看器……"
        )

    def _shutdown_managed_viewer(self) -> None:
        """Best-effort shutdown, including a viewer that is still starting."""
        if not self.session_token and not self.viewer_connected:
            return

        for attempt in range(20):
            try:
                response = send_command(
                    "quit viewer",
                    self.host,
                    self.port,
                    self.session_token,
                )
            except (OSError, ViewerProtocolError):
                response = ""
            if response.startswith("OK: "):
                self.viewer_connected = False
                return

            process = self.viewer_process
            if process is not None and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=2.0)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        process.kill()
                    except OSError:
                        pass
                self.viewer_connected = False
                return

            if attempt < 19:
                time.sleep(0.1)

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
            self._text(
                "support.title",
                "Primelock GIS Support / Control",
                "Primelock GIS 支持与控制面板",
            ),
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
            color=status_color(self._status_line()),
        )

        clear_screen()
        draw_frame("\n".join(lines))

    def handle_event(self, event: TerminalEvent) -> None:
        """Route one support-panel event."""
        if isinstance(event, ResizeEvent):
            return

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
                    self.state.status = self._text(
                        "support.button.disabled",
                        "WARN: {label} is disabled",
                        "警告：{label}当前不可用",
                        label=button.label,
                    )
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
            self._focus_grid_input("y" if self.state.grid_input_focus == "x" else "x")
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
        self.state.status = self._text(
            "support.grid.cancelled",
            "OK: grid input cancelled",
            "OK: 已取消网格输入",
        )

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
            self.state.status = self._text(
                "support.grid.integer_error",
                "ERROR: grid divisions must be integers",
                "ERROR: 网格划分数必须是整数",
            )
            return

        if x_value < 1 or y_value < 1:
            self.state.status = self._text(
                "support.grid.positive_error",
                "ERROR: grid divisions must be positive",
                "ERROR: 网格划分数必须为正数",
            )
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
            return self._text(
                "support.command.empty", "ERROR: empty command", "ERROR: 命令不能为空"
            )

        if parts == ["help"]:
            return self._text(
                "support.command.help",
                "OK: commands: viewer status, start viewer, quit viewer, restart viewer, "
                "summary, contour summary, config, model summary, set grid X Y, "
                "load dataset PATH, reload dataset, contour interval N, "
                "contour source grid|tin, terrain opacity N, "
                "terrain palette elevation|grayscale|heat",
                "OK: 可用命令：viewer status（查看状态）、start viewer（启动查看器）、"
                "quit viewer（退出查看器）、restart viewer（重启查看器）、summary（摘要）、"
                "contour summary（等高线摘要）、config（配置）、model summary（模型摘要）、"
                "set grid X Y（设置网格）、load dataset PATH（加载数据集）、"
                "reload dataset（重新加载）、contour interval N（设置等高距）、"
                "contour source grid|tin（设置等高线数据源）、terrain opacity N（地形不透明度）、"
                "terrain palette elevation|grayscale|heat（地形色带）",
            )

        if parts in (["viewer", "status"], ["status"]):
            response = self.send("summary")
            if response.startswith("OK: "):
                return self._text(
                    "support.viewer.responding",
                    "OK: viewer responding | {details}",
                    "OK: 查看器响应正常 | {details}",
                    details=response.removeprefix("OK: "),
                )
            return self._text(
                "support.viewer.not_responding",
                "ERROR: viewer not responding | {details}",
                "ERROR: 查看器无响应 | {details}",
                details=response,
            )

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
            return self._text(
                "support.viewer.already_running",
                "OK: viewer already responding",
                "OK: 查看器已经在运行",
            )

        if self.viewer_process is not None and self.viewer_process.poll() is None:
            return self._text(
                "support.viewer.process_running",
                "OK: viewer process already started pid={pid}",
                "OK: 查看器进程已经启动，进程号={pid}",
                pid=self.viewer_process.pid,
            )

        if not self.viewer_launch_command:
            return self._text(
                "support.viewer.command_missing",
                "ERROR: viewer launch command is not configured. "
                "Set PRIMLOCK_GIS_VIEWER_LAUNCH_COMMAND.",
                "ERROR: 未配置查看器启动命令。请设置 "
                "PRIMLOCK_GIS_VIEWER_LAUNCH_COMMAND。",
            )

        try:
            popen_kwargs = {}
            if os.name == "nt" and hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
                popen_kwargs["creationflags"] = (
                    subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                popen_kwargs["start_new_session"] = True
                popen_kwargs["stdin"] = subprocess.DEVNULL
                popen_kwargs["stdout"] = subprocess.DEVNULL
                popen_kwargs["stderr"] = subprocess.DEVNULL

            self.viewer_process = subprocess.Popen(
                self.viewer_launch_command,
                cwd=self.working_directory,
                shell=isinstance(self.viewer_launch_command, str),
                **popen_kwargs,
            )
        except OSError as error:
            return self._text(
                "support.viewer.start_error",
                "ERROR: could not start viewer: {error}",
                "ERROR: 无法启动查看器：{error}",
                error=error,
            )

        self.state.synced_viewer_mode = None
        self._reset_viewer_wait()
        return self._text(
            "support.viewer.start_requested",
            "OK: viewer start requested pid={pid}",
            "OK: 已请求启动查看器，进程号={pid}",
            pid=self.viewer_process.pid,
        )

    def quit_viewer(self) -> str:
        """Ask a responsive viewer to quit, or stop a locally started process."""
        response = self.send("quit viewer")
        if response.startswith("OK: "):
            self._reset_viewer_wait()
            return response

        if self.viewer_process is not None and self.viewer_process.poll() is None:
            self.viewer_process.terminate()
            self._reset_viewer_wait()
            return self._text(
                "support.viewer.terminated",
                "OK: viewer process terminated pid={pid}",
                "OK: 查看器进程已终止，进程号={pid}",
                pid=self.viewer_process.pid,
            )

        return self._text(
            "support.viewer.not_responding",
            "ERROR: viewer not responding | {details}",
            "ERROR: 查看器无响应 | {details}",
            details=response,
        )

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
            response = self.send("mode info")
            if not self.viewer_connected:
                return
            self.state.status = response
            if response.startswith("OK: "):
                self.state.synced_viewer_mode = self.state.mode
                if self.language == "zh-CN":
                    self.state.status = self._text(
                        "support.mode.synced",
                        response,
                        "OK: 查看器交互模式已同步",
                    )
            else:
                self.state.synced_viewer_mode = None
            return

        response = self.send("mode normal")
        if not self.viewer_connected:
            return
        self.state.status = response
        if response.startswith("OK: "):
            self.state.synced_viewer_mode = self.state.mode
            if self.language == "zh-CN":
                self.state.status = self._text(
                    "support.mode.synced",
                    response,
                    "OK: 查看器交互模式已同步",
                )
        else:
            self.state.synced_viewer_mode = None

    def send(self, command: str) -> str:
        """Send a support command to the viewer, returning an error string on failure."""
        try:
            return send_command(
                command,
                self.host,
                self.port,
                self.session_token,
            )
        except (OSError, ViewerProtocolError) as error:
            self._mark_viewer_disconnected()
            return self._text(
                "support.viewer.connect_error",
                "ERROR: could not connect to viewer: {error}",
                "ERROR: 无法连接查看器：{error}",
                error=error,
            )

    def _render_top_buttons(self, lines: list[str], width: int) -> None:
        x = 0
        labels = [
            (self._text("support.tab.info", "Info", "信息"), "mode:info"),
            (self._text("support.tab.layers", "Layers", "图层"), "mode:layers"),
            (self._text("support.tab.model", "Model", "模型"), "mode:model"),
            (self._text("support.tab.dataset", "Dataset", "数据集"), "mode:dataset"),
            (self._text("support.tab.admin", "Admin", "管理"), "mode:admin"),
            (self._text("support.tab.help", "Help", "帮助"), "mode:help"),
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
        self._write_line(
            lines,
            start_y,
            self._text("support.info.title", "Info Mode", "要素信息"),
            width,
            color=TERMINAL_THEME.active,
        )
        self._write_line(
            lines,
            start_y + 1,
            self._text(
                "support.info.instruction",
                "Click a feature in the viewer terminal.",
                "请在查看器终端中单击一个要素。",
            ),
            width,
        )
        self._write_line(
            lines,
            start_y + 3,
            self._text(
                "support.info.selected", "Selected feature:", "当前选择的要素："
            ),
            width,
        )

        row = start_y + 4
        for text in self._split_info_text(self.state.selected_feature):
            row = self._write_wrapped_line(lines, row, text, width)

    def _render_layers_panel(
        self,
        lines: list[str],
        width: int,
        start_y: int = 4,
    ) -> None:
        self._write_line(
            lines,
            start_y,
            self._text("support.layers.title", "Layers", "图层控制"),
            width,
            color=TERMINAL_THEME.active,
        )
        self._write_wrapped_line(
            lines, start_y + 1, self._display_layer_summary(), width
        )

        actions = [
            (
                self._text("support.layers.points", "Toggle Points", "显示/隐藏点"),
                "command:toggle points",
            ),
            (
                self._text("support.layers.terrain", "Toggle Terrain", "显示/隐藏地形"),
                "command:toggle terrain",
            ),
            (
                self._text("support.layers.grid", "Toggle Grid", "显示/隐藏网格"),
                "command:toggle grid",
            ),
            (
                self._text("support.layers.tin", "Toggle TIN", "显示/隐藏 TIN"),
                "command:toggle tin",
            ),
            (
                self._text(
                    "support.layers.contours", "Toggle Contours", "显示/隐藏等高线"
                ),
                "command:toggle contours",
            ),
            (
                self._text("support.layers.source", "Contour Source", "等高线数据源"),
                "command:toggle contour source",
            ),
            (
                self._text("support.layers.labels", "Toggle Labels", "显示/隐藏标注"),
                "command:toggle contour labels",
            ),
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
                self._text(
                    "support.terrain.summary",
                    "Terrain: source={source} palette={palette} opacity={opacity}%",
                    "地形：数据源={source} 色带={palette} 不透明度={opacity}%",
                    source=self._display_source(self.state.terrain_source),
                    palette=self._display_palette(self.state.terrain_palette),
                    opacity=opacity_percent,
                )
            ),
            width,
        )
        lower_opacity = max(0.0, self.state.terrain_opacity - 0.1)
        higher_opacity = min(1.0, self.state.terrain_opacity + 0.1)
        self._draw_button(
            lines,
            x=0,
            y=terrain_y + 2,
            label=self._text("support.terrain.opacity_down", "Opacity -", "不透明度 -"),
            action=f"command:terrain opacity {lower_opacity:.1f}",
            state="inactive" if self.state.terrain_opacity > 0.0 else "disabled",
        )
        self._draw_button(
            lines,
            x=14,
            y=terrain_y + 2,
            label=self._text("support.terrain.opacity_up", "Opacity +", "不透明度 +"),
            action=f"command:terrain opacity {higher_opacity:.1f}",
            state="inactive" if self.state.terrain_opacity < 1.0 else "disabled",
        )
        self._draw_button(
            lines,
            x=28,
            y=terrain_y + 2,
            label=self._text("support.terrain.palette", "Palette", "切换色带"),
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
            self._text("support.model.title", "Model Settings", "模型设置"),
            width,
            color=TERMINAL_THEME.active,
        )
        self._write_wrapped_line(
            lines, start_y + 1, self._display_config_summary(), width
        )
        self._write_line(
            lines,
            start_y + 3,
            self._text("support.model.divisions", "Grid divisions", "网格划分数"),
            width,
        )

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

        self._write_line(
            lines,
            start_y + 11,
            self._text("support.model.typed", "Typed divisions", "手动输入划分数"),
            width,
        )
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
            label=self._text("support.common.apply", "Apply", "应用"),
            action="model-grid-apply",
            state="success",
            width=10,
        )

        self._write_line(
            lines,
            start_y + 16,
            self._text("support.model.presets", "Presets", "预设"),
            width,
        )
        preset_x = 0
        for divisions in (10, 20, 40):
            state = (
                "active" if (x_value, y_value) == (divisions, divisions) else "inactive"
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
            self._text("support.dataset.title", "Dataset", "数据集"),
            width,
            color=TERMINAL_THEME.active,
        )
        self._write_line(
            lines,
            start_y + 2,
            self._text("support.dataset.current", "Current:", "当前数据集："),
            width,
        )
        self._write_wrapped_line(lines, start_y + 3, self.state.dataset_path, width)
        self._draw_button(
            lines,
            x=0,
            y=start_y + 6,
            label=self._text("support.dataset.reload", "Reload", "重新加载"),
            action="command:reload dataset",
            state="warning",
        )
        self._write_line(
            lines,
            start_y + 10,
            self._text("support.dataset.config", "Config:", "配置："),
            width,
        )
        row = self._write_wrapped_line(
            lines, start_y + 11, self._display_config_summary(), width
        )
        self._write_line(
            lines,
            row + 1,
            self._text("support.dataset.model", "Model:", "模型："),
            width,
        )
        self._write_wrapped_line(lines, row + 2, self._display_model_summary(), width)
        self._write_wrapped_line(
            lines,
            row + 5,
            self._text(
                "support.dataset.admin_hint",
                "Use Admin for: load dataset <path>",
                "可在“管理”页输入：load dataset <路径>",
            ),
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
            self._text("support.admin.title", "Admin Mode", "管理模式"),
            width,
            color=TERMINAL_THEME.focused,
        )
        self._write_wrapped_line(
            lines,
            start_y + 1,
            self._text(
                "support.admin.instruction",
                "Commands run here even when viewer is down.",
                "即使查看器未运行，也可以在此输入管理命令。",
            ),
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
        self._write_line(
            lines,
            start_y + 9,
            self._text("support.admin.output", "Output:", "输出："),
            width,
        )

        available_rows = max(0, height - (start_y + 12))
        output_lines = self._wrap_lines(self.state.command_output, width)
        output_lines = output_lines[-available_rows:]

        for offset, text in enumerate(output_lines):
            self._write_line(lines, start_y + 10 + offset, text, width)

    def _render_admin_buttons(self, lines: list[str], width: int, y: int = 7) -> None:
        actions = [
            (
                self._text("support.admin.status", "Status", "状态"),
                "admin:viewer status",
                "focused",
            ),
            (
                self._text("support.admin.start", "Start", "启动"),
                "admin:start viewer",
                "focused",
            ),
            (
                self._text("support.admin.quit", "Quit", "退出"),
                "admin:quit viewer",
                "warning",
            ),
            (
                self._text("support.admin.restart", "Restart", "重启"),
                "admin:restart viewer",
                "warning",
            ),
            (
                self._text("support.admin.config", "Config", "配置"),
                "admin:config",
                "focused",
            ),
            (
                self._text("support.admin.summary", "Summary", "摘要"),
                "admin:model summary",
                "focused",
            ),
        ]
        x = 0

        for label, action, state in actions:
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
        quit_help = (
            self._text(
                "support.help.quit_all",
                "q: quit complete application",
                "q：退出整个应用程序",
            )
            if self.manage_viewer
            else self._text(
                "support.help.quit_panel",
                "q: quit support panel",
                "q：退出支持面板",
            )
        )
        help_lines = [
            self._text("support.help.title", "Help", "帮助"),
            self._text("support.help.info", "i: Info mode", "i：要素信息模式"),
            self._text("support.help.layers", "l: Layers mode", "l：图层控制模式"),
            self._text("support.help.model", "m: Model mode", "m：模型设置模式"),
            self._text("support.help.dataset", "d: Dataset mode", "d：数据集模式"),
            self._text("support.help.admin", "a: Admin mode", "a：管理模式"),
            self._text("support.help.help", "?: Help mode", "?：帮助模式"),
            quit_help,
            self._text(
                "support.help.mouse", "Mouse: click panel buttons", "鼠标：单击面板按钮"
            ),
            "",
            self._text(
                "support.help.viewer_controls",
                "Viewer controls stay in the viewer terminal:",
                "查看器的快捷键仍在查看器终端中使用：",
            ),
            self._text(
                "support.help.navigation",
                "h/j/k/l pan, +/- zoom, mouse drag pan.",
                "h/j/k/l 平移，+/- 缩放，拖动鼠标平移。",
            ),
            self._text(
                "support.help.layers_shortcuts",
                "b terrain, c contours, m contour source, v labels.",
                "b 地形，c 等高线，m 切换等高线数据源，v 标注。",
            ),
            "",
            self._text(
                "support.help.admin_commands",
                "Admin: viewer status, quit viewer, restart viewer, summary.",
                "管理命令：viewer status、quit viewer、restart viewer、summary。",
            ),
            self._text(
                "support.help.model_commands",
                "Model admin: set grid 30 30, load dataset path.csv, reload dataset.",
                "模型命令：set grid 30 30、load dataset path.csv、reload dataset。",
            ),
            self._text(
                "support.help.contour_commands",
                "Contour admin: contour interval 25, contour source tin.",
                "等高线命令：contour interval 25、contour source tin。",
            ),
            self._text(
                "support.help.terrain_commands",
                "Terrain admin: terrain opacity 0.7, terrain palette heat.",
                "地形命令：terrain opacity 0.7、terrain palette heat。",
            ),
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
            width = max(6, text_width(label) + 4)

        inner_width = max(1, width - 2)
        clipped_label = clip_text(label, inner_width)
        padding = inner_width - text_width(clipped_label)
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

    def _display_layer_summary(self) -> str:
        """Return a localized copy of the machine-readable layer summary."""
        if self.language != "zh-CN":
            return self.state.layer_summary
        return self._localize_summary(
            self.state.layer_summary,
            {
                "points": "点",
                "terrain": "地形",
                "grid": "网格",
                "tin": "TIN",
                "contours": "等高线",
                "contour_labels": "等高线标注",
                "contour_source": "等高线数据源",
                "contour_interval": "等高距",
                "terrain_source": "地形数据源",
                "terrain_opacity": "地形不透明度",
                "terrain_palette": "地形色带",
            },
        )

    def _display_config_summary(self) -> str:
        """Return a localized copy of the machine-readable project config."""
        if self.language != "zh-CN":
            return self.state.config_summary
        return self._localize_summary(
            self.state.config_summary,
            {
                "dataset": "数据集",
                "grid": "网格",
                "interpolation": "插值方法",
                "contour_source": "等高线数据源",
                "contour_interval": "等高距",
            },
        )

    def _display_model_summary(self) -> str:
        """Return the model summary in the selected display language."""
        if self.language != "zh-CN":
            return self.state.model_summary
        return self._localize_summary(
            self.state.model_summary,
            {
                "points": "点数",
                "grid": "网格",
                "tin_vertices": "TIN 顶点数",
                "tin_triangles": "TIN 三角形数",
                "dataset": "数据集",
                "interpolation": "插值方法",
            },
        )

    def _localize_summary(self, summary: str, labels: dict[str, str]) -> str:
        localized = summary
        for key in sorted(labels, key=len, reverse=True):
            localized = localized.replace(f"{key}=", f"{labels[key]}=")
        localized = localized.replace("=on", "=开").replace("=off", "=关")
        localized = localized.replace("=grid", "=网格")
        localized = localized.replace("=elevation", "=高程")
        localized = localized.replace("=grayscale", "=灰度")
        localized = localized.replace("=heat", "=热力")
        return localized

    def _display_source(self, source: str) -> str:
        if self.language == "zh-CN" and source == "grid":
            return "网格"
        return source

    def _display_palette(self, palette: str) -> str:
        if self.language != "zh-CN":
            return palette
        return {
            "elevation": "高程",
            "grayscale": "灰度",
            "heat": "热力",
        }.get(palette, palette)

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
        mode_label = {
            "info": "信息",
            "layers": "图层",
            "model": "模型",
            "dataset": "数据集",
            "admin": "管理",
            "help": "帮助",
        }.get(self.state.mode, self.state.mode)
        status = self._text(
            "support.status",
            "mode={mode} | {status}",
            "模式={mode} | {status}",
            mode=mode_label if self.language == "zh-CN" else self.state.mode,
            status=self.state.status,
        )
        if self.state.terminal_warning:
            return self._text(
                "support.warning",
                "WARN: {warning} | {status}",
                "警告：{warning} | {status}",
                warning=self.state.terminal_warning,
                status=status,
            )
        return status

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
        clipped = clip_text(text, available_width)
        line = lines[y]
        raw_start = self._raw_index_for_visible_column(line, x)
        raw_end = self._raw_index_for_visible_column(line, x + text_width(clipped))
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

            width += character_width(text[index])
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

            character_cells = character_width(text[index])
            if visible_column + character_cells > column:
                break
            visible_column += character_cells
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

        if all(character_width(character) <= 1 for character in text):
            return textwrap.wrap(
                text,
                width=width,
                break_long_words=True,
                break_on_hyphens=False,
            ) or [""]

        lines = []
        remainder = text
        while remainder:
            line = clip_text(remainder, width)
            if not line:
                break
            lines.append(line)
            remainder = remainder[len(line) :]
        return lines or [""]


def run_support_panel(
    host: str = "127.0.0.1",
    port: int = 8765,
    session_token: str | None = None,
    startup_timeout: float = 15.0,
    manage_viewer: bool = False,
    language: Language | str | None = None,
) -> None:
    """Run the interactive support panel terminal."""
    SupportPanelApp(
        host,
        port,
        session_token=session_token,
        startup_timeout=startup_timeout,
        manage_viewer=manage_viewer,
        language=language,
    ).run()
