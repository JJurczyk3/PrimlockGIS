import io
from queue import Queue
from types import SimpleNamespace
import threading

from primelock_gis.ui.terminal.events import KeyEvent, MouseEvent
from primelock_gis.ui.terminal.support_panel import (
    CommandHandler,
    PanelButton,
    SupportPanelApp,
)


class FakeSupportPanelApp(SupportPanelApp):
    def __init__(self):
        super().__init__()
        self.sent_commands = []
        self.responses = {}

    def send(self, command: str) -> str:
        self.sent_commands.append(command)
        if command in self.responses:
            return self.responses[command]
        return f"OK: {command}"


def test_support_panel_mode_button_switches_mode():
    app = FakeSupportPanelApp()

    app.activate_button("mode:layers")

    assert app.state.mode == "layers"
    assert app.sent_commands == ["mode normal"]
    assert app.state.status == "OK: mode normal"
    assert app.state.synced_viewer_mode == "layers"


def test_support_panel_info_mode_tells_viewer_to_use_info_mode():
    app = FakeSupportPanelApp()

    app.activate_button("mode:info")

    assert app.state.mode == "info"
    assert app.sent_commands == ["mode info"]
    assert app.state.status == "OK: mode info"
    assert app.state.synced_viewer_mode == "info"


def test_command_server_handles_one_command_per_connection():
    command_queue = Queue()
    handler = object.__new__(CommandHandler)
    handler.server = SimpleNamespace(command_queue=command_queue)
    handler.rfile = io.BytesIO(b"summary\n")
    handler.wfile = io.BytesIO()

    worker = threading.Thread(target=handler.handle)
    worker.start()
    request = command_queue.get(timeout=1.0)

    assert request.text == "summary"
    request.reply_queue.put("OK: summary")
    worker.join(timeout=1.0)

    assert handler.wfile.getvalue() == b"OK: summary\n"


def test_command_server_ignores_client_reset_before_command():
    command_queue = Queue()

    class ResettingInput:
        def readline(self):
            raise ConnectionResetError

    handler = object.__new__(CommandHandler)
    handler.server = SimpleNamespace(command_queue=command_queue)
    handler.rfile = ResettingInput()
    handler.wfile = io.BytesIO()

    handler.handle()

    assert command_queue.empty()


def test_support_panel_info_refresh_resyncs_and_displays_selection():
    app = FakeSupportPanelApp()
    app.responses["selected feature"] = "OK: TIN arc | start_vertex=1 | end_vertex=2"

    app.refresh_viewer_state()

    assert app.sent_commands == ["mode info", "selected feature"]
    assert app.state.selected_feature == "TIN arc | start_vertex=1 | end_vertex=2"


def test_support_panel_retries_mode_sync_after_connection_error():
    app = FakeSupportPanelApp()
    app.responses["mode info"] = "ERROR: could not connect to viewer"

    app.refresh_viewer_state()
    app.responses["mode info"] = "OK: mode=info"
    app.refresh_viewer_state()

    assert app.sent_commands == [
        "mode info",
        "selected feature",
        "mode info",
        "selected feature",
    ]
    assert app.state.synced_viewer_mode == "info"


def test_support_panel_info_render_writes_selected_feature_lines():
    app = FakeSupportPanelApp()
    app.state.selected_feature = "Grid node | row=0 | col=1"
    lines = [" " * 40 for _ in range(12)]

    app._render_info_panel(lines, width=40)

    assert "Grid node" in lines[8]
    assert "row=0" in lines[9]
    assert "col=1" in lines[10]


def test_support_panel_info_render_wraps_long_selected_feature_text():
    app = FakeSupportPanelApp()
    app.state.selected_feature = (
        "TIN arc | start_vertex=123456789 | end_vertex=987654321"
    )
    lines = [" " * 20 for _ in range(14)]

    app._render_info_panel(lines, width=20)

    rendered = "\n".join(lines)
    assert "start_vertex=12345" in rendered
    assert "89" in rendered
    assert "end_vertex=98765" in rendered
    assert "4321" in rendered or "987654321" in rendered


def test_support_panel_command_button_sends_viewer_command():
    app = FakeSupportPanelApp()

    app.activate_button("command:toggle grid")

    assert app.sent_commands == ["toggle grid"]
    assert app.state.status == "OK: toggle grid"


def test_support_panel_layers_render_adds_contour_buttons():
    app = FakeSupportPanelApp()
    lines = [" " * 60 for _ in range(26)]

    app._render_layers_panel(lines, width=60)

    actions = {button.action for button in app.buttons}
    assert "command:toggle terrain" in actions
    assert "command:toggle contours" in actions
    assert "command:toggle contour source" in actions
    assert "command:toggle contour labels" in actions
    assert "command:terrain opacity 0.9" in actions
    assert "command:cycle terrain palette" in actions


def test_support_panel_parses_terrain_settings_from_layer_summary():
    app = FakeSupportPanelApp()

    app._parse_layer_summary(
        "points=on terrain=on contour_source=tin terrain_source=tin "
        "terrain_opacity=0.7 terrain_palette=heat"
    )

    assert app.state.terrain_source == "tin"
    assert app.state.terrain_opacity == 0.7
    assert app.state.terrain_palette == "heat"


def test_support_panel_terrain_palette_button_refreshes_layers():
    app = FakeSupportPanelApp()
    app.state.mode = "layers"
    app.responses["layers summary"] = (
        "OK: points=on terrain=on contour_source=grid "
        "terrain_source=grid terrain_opacity=1 terrain_palette=grayscale"
    )
    lines = [" " * 60 for _ in range(26)]

    app._render_layers_panel(lines, width=60)
    palette_button = next(button for button in app.buttons if button.label == "Palette")
    app.handle_mouse(
        MouseEvent(
            kind="press",
            x=palette_button.x + 1,
            y=palette_button.y + 1,
            button=0,
        )
    )

    assert app.sent_commands == ["cycle terrain palette", "layers summary"]
    assert app.state.terrain_palette == "grayscale"


def test_support_panel_mouse_click_activates_button():
    app = FakeSupportPanelApp()
    app.buttons = [
        PanelButton(
            label="Layers",
            action="mode:layers",
            x=2,
            y=3,
            width=8,
        )
    ]

    app.handle_mouse(MouseEvent(kind="press", x=4, y=3, button=0))

    assert app.state.mode == "layers"
    assert app.sent_commands == ["mode normal"]


def test_panel_button_hit_testing_supports_framed_rectangles():
    button = PanelButton(
        label="Apply",
        action="command:set grid 20 20",
        x=5,
        y=4,
        width=12,
        height=3,
    )

    assert button.contains(5, 4)
    assert button.contains(16, 6)
    assert not button.contains(17, 6)
    assert not button.contains(8, 7)


def test_support_panel_model_preset_button_sends_grid_command():
    app = FakeSupportPanelApp()
    app.state.mode = "model"
    app.state.grid_x_divisions = 20
    app.state.grid_y_divisions = 20
    lines = [" " * 60 for _ in range(24)]

    app._render_model_panel(lines, width=60)
    preset = next(button for button in app.buttons if button.label == "40x40")
    app.handle_mouse(
        MouseEvent(
            kind="press",
            x=preset.x + 1,
            y=preset.y + 1,
            button=0,
        )
    )

    assert app.sent_commands[0] == "set grid 40 40"


def test_support_panel_model_typed_grid_divisions_apply_button():
    app = FakeSupportPanelApp()
    app.state.mode = "model"
    app.state.grid_x_divisions = 8
    app.state.grid_y_divisions = 8
    lines = [" " * 70 for _ in range(28)]

    app._render_model_panel(lines, width=70)
    x_input = next(button for button in app.buttons if button.action == "model-input:x")
    y_input = next(button for button in app.buttons if button.action == "model-input:y")
    apply_button = next(
        button for button in app.buttons if button.action == "model-grid-apply"
    )

    app.handle_mouse(
        MouseEvent(kind="press", x=x_input.x + 1, y=x_input.y + 1, button=0)
    )
    for char in "120":
        app.handle_key(char)

    app.handle_mouse(
        MouseEvent(kind="press", x=y_input.x + 1, y=y_input.y + 1, button=0)
    )
    for char in "80":
        app.handle_key(char)

    app.handle_mouse(
        MouseEvent(
            kind="press",
            x=apply_button.x + 1,
            y=apply_button.y + 1,
            button=0,
        )
    )

    assert app.sent_commands[0] == "set grid 120 80"
    assert app.state.grid_x_divisions == 120
    assert app.state.grid_y_divisions == 80
    assert app.state.grid_input_focus is None


def test_support_panel_model_typed_grid_divisions_enter_key_applies():
    app = FakeSupportPanelApp()
    app.state.mode = "model"

    app.handle_key("x")
    for char in "64":
        app.handle_key(char)
    app.handle_key("\t")
    for char in "96":
        app.handle_key(char)
    app.handle_key("\n")

    assert app.sent_commands[0] == "set grid 64 96"


def test_support_panel_dataset_reload_button_sends_reload_command():
    app = FakeSupportPanelApp()
    app.state.mode = "dataset"
    lines = [" " * 60 for _ in range(24)]

    app._render_dataset_panel(lines, width=60)
    reload_button = next(button for button in app.buttons if button.label == "Reload")
    app.handle_mouse(
        MouseEvent(
            kind="press",
            x=reload_button.x + 1,
            y=reload_button.y + 1,
            button=0,
        )
    )

    assert app.sent_commands[0] == "reload dataset"


def test_support_panel_admin_mode_sends_typed_command():
    app = FakeSupportPanelApp()
    app.activate_button("mode:admin")

    for char in "summary":
        app.handle_event(KeyEvent(char))
    app.handle_event(KeyEvent("\n"))

    assert app.sent_commands == ["mode normal", "summary"]
    assert app.state.command_output == ["> summary", "OK: summary"]


def test_support_panel_admin_status_reports_responsive_viewer():
    app = FakeSupportPanelApp()
    app.responses["summary"] = "OK: points=3"

    response = app.handle_admin_command("viewer status")

    assert response == "OK: viewer responding | points=3"
    assert app.sent_commands == ["summary"]


def test_support_panel_admin_status_reports_unresponsive_viewer():
    app = FakeSupportPanelApp()
    app.responses["summary"] = "ERROR: could not connect to viewer"

    response = app.handle_admin_command("viewer status")

    assert response == (
        "ERROR: viewer not responding | ERROR: could not connect to viewer"
    )


def test_support_panel_admin_start_requires_launch_command_when_viewer_is_down():
    app = FakeSupportPanelApp()
    app.responses["summary"] = "ERROR: could not connect to viewer"

    response = app.handle_admin_command("start viewer")

    assert "PRIMLOCK_GIS_VIEWER_LAUNCH_COMMAND" in response


def test_support_panel_admin_quit_viewer_sends_quit_command():
    app = FakeSupportPanelApp()
    app.responses["quit viewer"] = "OK: viewer quitting"

    response = app.handle_admin_command("quit viewer")

    assert response == "OK: viewer quitting"
    assert app.sent_commands == ["quit viewer"]


def test_support_panel_admin_button_records_command_output():
    app = FakeSupportPanelApp()
    app.responses["summary"] = "OK: points=3"

    app.activate_button("admin:viewer status")

    assert app.state.command_output == [
        "> viewer status",
        "OK: viewer responding | points=3",
    ]
    assert app.state.status == "OK: viewer responding | points=3"


def test_support_panel_admin_output_wraps_long_lines():
    app = FakeSupportPanelApp()
    app.state.command_output = [
        "> restart viewer",
        (
            "ERROR: viewer launch command is not configured. "
            "Set PRIMLOCK_GIS_VIEWER_LAUNCH_COMMAND."
        ),
    ]
    lines = [" " * 28 for _ in range(22)]

    app._render_admin_panel(lines, width=28, height=22)

    rendered = "\n".join(lines)
    assert "ERROR: viewer launch command" in rendered
    assert "is not configured." in rendered
    assert "PRIML" in rendered
    assert "OCK_GIS_VIEWER_LAUNCH" in rendered


def test_support_panel_admin_exit_returns_to_previous_mode():
    app = FakeSupportPanelApp()
    app.state.mode = "info"
    app.activate_button("mode:admin")

    for char in "exit":
        app.handle_event(KeyEvent(char))
    app.handle_event(KeyEvent("\n"))

    assert app.state.mode == "info"
    assert app.sent_commands == ["mode normal", "mode info"]
    assert app.state.status == "OK: mode info"
