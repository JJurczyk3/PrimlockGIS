import pytest

from primelock_gis.app.project_builder import build_project_state
from primelock_gis.app.project_state import ProjectConfig
from primelock_gis.app.project_state import ProjectState
from primelock_gis.core.algorithms.tin import build_tin_from_points
from primelock_gis.core.models.grid import GridModel
from primelock_gis.core.models.vector import SpecialPoint
from primelock_gis.core.rendering.viewport import Viewport
from primelock_gis.ui.terminal.capabilities import TerminalCapabilities
from primelock_gis.ui.terminal.events import KeyEvent, MouseEvent
from primelock_gis.ui.terminal.interactive_app import (
    InteractiveTerminalApp,
    coalesce_terminal_events,
)


def make_app() -> InteractiveTerminalApp:
    points = [
        SpecialPoint(1, "A", 0.0, 0.0, 10.0),
        SpecialPoint(2, "B", 10.0, 0.0, 20.0),
        SpecialPoint(3, "C", 0.0, 10.0, 30.0),
    ]
    grid = GridModel(
        x_min=0.0,
        y_min=0.0,
        x_max=10.0,
        y_max=10.0,
        x_divisions=1,
        y_divisions=1,
        node_values=[
            [10.0, 20.0],
            [30.0, 40.0],
        ],
    )
    project_state = ProjectState(
        points=points,
        idw_grid=grid,
        tin=build_tin_from_points(points),
    )
    viewport = Viewport(
        world_min_x=0.0,
        world_min_y=0.0,
        world_max_x=10.0,
        world_max_y=10.0,
        view_width=100,
        view_height=100,
    )
    return InteractiveTerminalApp(
        project_state=project_state,
        viewport=viewport,
        capabilities=TerminalCapabilities(),
    )


def write_points_csv(path):
    path.write_text(
        "\n".join(
            [
                "No.,Data point name,x_coord,y_coord,z_coord",
                "1,A,0,0,10",
                "2,B,10,0,20",
                "3,C,0,10,30",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def make_configured_app(tmp_path, grid_x=1, grid_y=1) -> InteractiveTerminalApp:
    csv_path = tmp_path / "points.csv"
    write_points_csv(csv_path)
    project_state = build_project_state(
        ProjectConfig(
            dataset_path=csv_path,
            grid_x_divisions=grid_x,
            grid_y_divisions=grid_y,
        )
    )
    viewport = Viewport(
        world_min_x=0.0,
        world_min_y=0.0,
        world_max_x=10.0,
        world_max_y=10.0,
        view_width=100,
        view_height=100,
    )
    return InteractiveTerminalApp(
        project_state=project_state,
        viewport=viewport,
        capabilities=TerminalCapabilities(),
    )


def test_non_hjkl_direction_names_do_not_pan_viewport():
    app = make_app()

    app.handle_key("right")

    assert app.viewport.world_min_x == 0.0
    assert app.viewport.world_max_x == 10.0
    assert app.state.status_message == "Unknown key: 'right'"


def test_coalesce_terminal_events_preserves_press_latest_drag_and_release():
    events = [
        MouseEvent(kind="press", x=1, y=1, button=0),
        MouseEvent(kind="drag", x=2, y=1, button=0),
        MouseEvent(kind="drag", x=3, y=1, button=0),
        MouseEvent(kind="drag", x=4, y=1, button=0),
        MouseEvent(kind="release", x=4, y=1, button=0),
    ]

    coalesced = coalesce_terminal_events(events)

    assert coalesced == [
        MouseEvent(kind="press", x=1, y=1, button=0),
        MouseEvent(kind="drag", x=4, y=1, button=0),
        MouseEvent(kind="release", x=4, y=1, button=0),
    ]


def test_coalesce_terminal_events_keeps_latest_wheel_in_burst():
    events = [
        MouseEvent(kind="wheel_up", x=1, y=1),
        MouseEvent(kind="wheel_up", x=2, y=2),
        MouseEvent(kind="wheel_down", x=3, y=3),
        KeyEvent("x"),
    ]

    coalesced = coalesce_terminal_events(events)

    assert coalesced == [
        MouseEvent(kind="wheel_down", x=3, y=3),
        KeyEvent("x"),
    ]


def test_vim_key_pans_viewport():
    app = make_app()

    app.handle_key("h")

    assert app.viewport.world_min_x == pytest.approx(-0.1)
    assert app.viewport.world_max_x == pytest.approx(9.9)
    assert app.state.status_message == "Panned left"


def test_vim_vertical_key_pans_by_one_terminal_cell():
    app = make_app()

    app.handle_key("k")

    assert app.viewport.world_min_y == pytest.approx(0.1)
    assert app.viewport.world_max_y == pytest.approx(10.1)
    assert app.state.status_message == "Panned up"


def test_debug_key_is_not_a_viewer_shortcut():
    app = make_app()

    app.handle_key("d")

    assert app.state.debug_input_enabled is False
    assert app.state.status_message == "Unknown key: 'd'"


def test_support_debug_input_commands_poll_raw_input_sequences():
    app = make_app()

    start_response = app.handle_support_command("debug input start")
    app.handle_event(KeyEvent("x", raw_sequence="x"))
    poll_response = app.handle_support_command("debug input poll")
    empty_response = app.handle_support_command("debug input poll")
    stop_response = app.handle_support_command("debug input stop")

    assert start_response == "OK: input debug enabled"
    assert poll_response == "OK: input Input debug: KeyEvent raw=x"
    assert empty_response == "OK: no input"
    assert stop_response == "OK: input debug disabled"
    assert app.state.debug_input_enabled is False


def test_support_commands_set_mode_and_report_selected_feature():
    app = make_app()

    assert app.handle_support_command("mode info") == "OK: mode=info"
    app.handle_mouse(MouseEvent(kind="press", x=0, y=99, button=0))
    app.handle_mouse(MouseEvent(kind="release", x=0, y=99, button=0))

    response = app.handle_support_command("selected feature")

    assert app.state.interaction_mode == "info"
    assert response.startswith("OK: Point | id=1 | name=A")


def test_support_commands_configure_contours():
    app = make_app()

    assert app.handle_support_command("toggle contours") == "OK: Contours visible"
    assert app.handle_support_command("toggle contour labels") == (
        "OK: Contour labels visible"
    )
    assert app.handle_support_command("contour source tin") == (
        "OK: Contour source: tin"
    )
    assert app.handle_support_command("contour interval 10") == (
        "OK: Contour interval: 10"
    )
    summary = app.handle_support_command("contour summary")

    assert app.state.show_contours is True
    assert app.state.show_contour_labels is True
    assert app.state.contour_source == "tin"
    assert app.state.contour_interval == 10
    assert summary.startswith("OK: source=tin, interval=10")


def test_support_commands_report_current_config_and_model_summary(tmp_path):
    app = make_configured_app(tmp_path, grid_x=2, grid_y=3)

    config_response = app.handle_support_command("get current config")
    summary_response = app.handle_support_command("get model summary")

    assert "grid=2x3" in config_response
    assert "interpolation=idw" in config_response
    assert summary_response.startswith("OK: points=3, grid=2x3")


def test_support_command_sets_grid_divisions_through_rebuild(tmp_path):
    app = make_configured_app(tmp_path)

    response = app.handle_support_command("set grid 4 5")

    assert response == "OK: Grid divisions set to 4x5"
    assert app.project_state.config.grid_x_divisions == 4
    assert app.project_state.config.grid_y_divisions == 5
    assert app.project_state.idw_grid.x_divisions == 4
    assert app.project_state.idw_grid.y_divisions == 5


def test_support_command_rejects_invalid_grid_divisions(tmp_path):
    app = make_configured_app(tmp_path)

    assert app.handle_support_command("set grid west 5") == (
        "ERROR: grid divisions must be integers"
    )
    assert app.handle_support_command("set grid 0 5") == (
        "ERROR: grid_x_divisions must be positive"
    )


def test_failed_dataset_load_keeps_current_project(tmp_path):
    app = make_configured_app(tmp_path)
    current_project = app.project_state

    response = app.handle_support_command(
        f"load dataset {tmp_path / 'missing.csv'}"
    )

    assert response.startswith("ERROR: dataset load failed:")
    assert app.project_state is current_project
    assert app.project_state.config.dataset_path == current_project.config.dataset_path


def test_reload_dataset_uses_current_config(tmp_path):
    app = make_configured_app(tmp_path, grid_x=2, grid_y=2)

    response = app.handle_support_command("reload dataset")

    assert response.startswith("OK: Dataset reloaded:")
    assert app.project_state.idw_grid.x_divisions == 2
    assert app.project_state.idw_grid.y_divisions == 2


def test_support_command_rejects_invalid_contour_settings():
    app = make_app()

    assert app.handle_support_command("contour source raster") == (
        "ERROR: contour source must be grid or tin"
    )
    assert app.handle_support_command("contour interval 0") == (
        "ERROR: contour interval must be positive"
    )


def test_support_layers_summary_reports_visibility():
    app = make_app()

    response = app.handle_support_command("layers summary")

    assert response == (
        "OK: points=on grid=off tin=on contours=off contour_labels=off "
        "contour_source=grid contour_interval=50"
    )


def test_status_instruction_and_info_are_separate_rows():
    app = make_app()
    app.state.status_message = "Selected feature details"

    assert "q quit" in app.status_instruction_text()
    assert "Selected feature details" not in app.status_instruction_text()
    assert app.status_info_text() == "Selected feature details"


def test_build_scene_reuses_cached_scene_while_layer_visibility_is_unchanged():
    app = make_app()

    scene = app.build_scene()
    same_scene = app.build_scene()

    assert same_scene is scene


def test_build_scene_rebuilds_cached_scene_when_layer_visibility_changes():
    app = make_app()
    scene = app.build_scene()

    app.state.show_grid = True
    updated_scene = app.build_scene()

    assert updated_scene is not scene
    assert app.scene_cache is updated_scene


def test_c_key_toggles_contours():
    app = make_app()

    app.handle_key("c")

    assert app.state.show_contours is True
    assert app.state.status_message == "Contours visible"


def test_m_key_switches_contour_source():
    app = make_app()

    app.handle_key("m")

    assert app.state.contour_source == "tin"
    assert app.state.status_message == "Contour source: tin"


def test_v_key_toggles_contour_labels():
    app = make_app()

    app.handle_key("v")

    assert app.state.show_contour_labels is True
    assert app.state.status_message == "Contour labels visible"


def test_bracket_keys_change_contour_interval():
    app = make_app()

    app.handle_key("[")
    assert app.state.contour_interval == pytest.approx(25.0)

    app.handle_key("]")
    assert app.state.contour_interval == pytest.approx(50.0)


def test_build_scene_includes_grid_contours_when_enabled():
    app = make_app()
    app.state.show_grid = False
    app.state.show_tin = False
    app.state.show_points = False
    app.state.show_contours = True
    app.state.contour_interval = 10.0

    scene = app.build_scene()

    assert scene.polylines
    assert {polyline.style.color for polyline in scene.polylines} == {"#7DD3FC"}


def test_build_scene_includes_contour_labels_when_enabled():
    app = make_app()
    app.state.show_grid = False
    app.state.show_tin = False
    app.state.show_points = False
    app.state.show_contours = True
    app.state.show_contour_labels = True
    app.state.contour_interval = 10.0

    scene = app.build_scene()

    assert scene.texts
    assert {text.text for text in scene.texts} == {"20", "30"}


def test_tin_layer_uses_braille_line_style():
    app = make_app()
    app.state.show_points = False
    app.state.show_grid = False
    app.state.show_tin = True

    scene = app.build_scene()

    assert scene.polylines
    assert {polyline.style.line_type for polyline in scene.polylines} == {"braille"}


def test_grid_layer_keeps_solid_line_style():
    app = make_app()
    app.state.show_points = False
    app.state.show_grid = True
    app.state.show_tin = False

    scene = app.build_scene()

    assert scene.polylines
    assert {polyline.style.line_type for polyline in scene.polylines} == {"solid"}


def test_plus_key_zooms_in_around_view_center():
    app = make_app()

    app.handle_key("+")

    assert app.viewport.world_max_x - app.viewport.world_min_x == pytest.approx(8.0)
    assert app.viewport.world_max_y - app.viewport.world_min_y == pytest.approx(8.0)
    assert app.state.status_message == "Zoomed in"


def test_mouse_wheel_zooms_at_cursor():
    app = make_app()

    app.handle_mouse(MouseEvent(kind="wheel_up", x=50, y=50))

    assert app.viewport.world_max_x - app.viewport.world_min_x == pytest.approx(10 / 1.2)
    assert app.state.status_message == "Zoomed in"


def test_mouse_drag_pans_from_last_mouse_position():
    app = make_app()

    app.handle_mouse(MouseEvent(kind="press", x=50, y=50, button=0))
    app.handle_mouse(MouseEvent(kind="drag", x=60, y=50, button=0))

    assert app.viewport.world_min_x == pytest.approx(-1.0)
    assert app.viewport.world_max_x == pytest.approx(9.0)
    assert app.state.status_message == "Mouse pan"


def test_mouse_drag_does_not_select_feature_in_info_mode():
    app = make_app()
    app.handle_support_command("mode info")

    app.handle_mouse(MouseEvent(kind="press", x=0, y=99, button=0))
    app.handle_mouse(MouseEvent(kind="drag", x=20, y=99, button=0))
    app.handle_mouse(MouseEvent(kind="release", x=20, y=99, button=0))

    assert app.state.selected_feature == "No feature selected."
    assert app.state.status_message == "Mouse pan"


def test_left_click_queries_nearest_point_in_info_mode():
    app = make_app()
    app.handle_support_command("mode info")

    app.handle_mouse(MouseEvent(kind="press", x=0, y=99, button=0))
    app.handle_mouse(MouseEvent(kind="release", x=0, y=99, button=0))

    assert app.state.selected_feature.startswith("Point | id=1 | name=A")
    assert app.state.status_message.startswith("Point, id=1, name=A")


def test_left_click_selects_feature_without_info_mode_gate():
    app = make_app()

    app.handle_mouse(MouseEvent(kind="press", x=0, y=99, button=0))
    app.handle_mouse(MouseEvent(kind="release", x=0, y=99, button=0))

    assert app.state.selected_feature.startswith("Point | id=1 | name=A")


def test_press_only_click_can_select_after_short_delay():
    app = make_app()

    app.handle_mouse(MouseEvent(kind="press", x=0, y=99, button=0))

    assert app.pending_click_started_at is not None
    app.commit_pending_click_if_ready(
        now=app.pending_click_started_at + app.PENDING_CLICK_SECONDS + 0.01,
    )

    assert app.state.selected_feature.startswith("Point | id=1 | name=A")


def test_drag_after_pending_click_commit_restores_previous_selection():
    app = make_app()

    app.handle_mouse(MouseEvent(kind="press", x=0, y=99, button=0))
    app.handle_mouse(MouseEvent(kind="release", x=0, y=99, button=0))
    selected_before_drag = app.state.selected_feature

    app.handle_mouse(MouseEvent(kind="press", x=99, y=99, button=0))
    assert app.pending_click_started_at is not None
    app.commit_pending_click_if_ready(
        now=app.pending_click_started_at + app.PENDING_CLICK_SECONDS + 0.01,
    )
    app.handle_mouse(MouseEvent(kind="drag", x=80, y=99, button=0))

    assert app.state.selected_feature == selected_before_drag
    assert app.state.status_message == "Mouse pan"


def test_selection_ignores_hidden_point_layer():
    app = make_app()
    app.state.show_points = False

    app.handle_mouse(MouseEvent(kind="press", x=0, y=99, button=0))
    app.handle_mouse(MouseEvent(kind="release", x=0, y=99, button=0))

    assert not app.state.selected_feature.startswith("Point")


def test_selection_ignores_hidden_grid_layer():
    app = make_app()
    app.state.show_points = False
    app.state.show_grid = False
    app.state.show_tin = False

    app.handle_mouse(MouseEvent(kind="press", x=50, y=50, button=0))
    app.handle_mouse(MouseEvent(kind="release", x=50, y=50, button=0))

    assert app.state.selected_feature == "No selectable visible feature near click."


def test_selection_can_pick_visible_tin_arc():
    app = make_app()
    app.state.show_points = False
    app.state.show_grid = False
    app.state.show_tin = True

    app.handle_mouse(MouseEvent(kind="press", x=50, y=99, button=0))
    app.handle_mouse(MouseEvent(kind="release", x=50, y=99, button=0))

    assert app.state.selected_feature.startswith("TIN arc")


def test_selection_can_pick_visible_grid_node():
    app = make_app()
    app.state.show_points = False
    app.state.show_grid = True
    app.state.show_tin = False

    app.handle_mouse(MouseEvent(kind="press", x=99, y=99, button=0))
    app.handle_mouse(MouseEvent(kind="release", x=99, y=99, button=0))

    assert app.state.selected_feature.startswith("Grid node | row=0 | col=1")


def test_selection_snaps_to_closest_visible_feature_in_range():
    app = make_app()
    app.state.show_points = True
    app.state.show_grid = False
    app.state.show_tin = True

    app.handle_mouse(MouseEvent(kind="press", x=5, y=99, button=0))
    app.handle_mouse(MouseEvent(kind="release", x=5, y=99, button=0))

    assert app.state.selected_feature.startswith("TIN arc")
