from primelock_gis.core.geometry import Point
from primelock_gis.core.rendering.scene import DrawablePoint, Scene
from primelock_gis.core.rendering.symbology import PointStyle
from primelock_gis.core.rendering.viewport import Viewport
from primelock_gis.ui.terminal.capabilities import TerminalCapabilities
from primelock_gis.ui.terminal.render_app import TerminalRenderApp


def test_redraw_clears_previous_frame_before_rendering_next_scene():
    viewport = Viewport(
        world_min_x=0.0,
        world_min_y=0.0,
        world_max_x=10.0,
        world_max_y=10.0,
        view_width=10,
        view_height=10,
    )
    scene = Scene(
        points=[
            DrawablePoint(
                position=Point(5.0, 5.0),
                style=PointStyle(char="X"),
            )
        ]
    )
    app = TerminalRenderApp(
        scene=scene,
        viewport=viewport,
        capabilities=TerminalCapabilities(supports_color=False),
    )

    assert "X" in app.redraw()

    app.scene = Scene()

    assert "X" not in app.redraw()


def test_redraw_clears_canvas_once_through_renderer_base():
    viewport = Viewport(
        world_min_x=0.0,
        world_min_y=0.0,
        world_max_x=10.0,
        world_max_y=10.0,
        view_width=10,
        view_height=10,
    )
    app = TerminalRenderApp(
        scene=Scene(),
        viewport=viewport,
        capabilities=TerminalCapabilities(supports_color=False),
    )
    clear_count = 0
    original_clear = app.renderer.clear

    def counted_clear():
        nonlocal clear_count
        clear_count += 1
        original_clear()

    app.renderer.clear = counted_clear

    app.redraw()

    assert clear_count == 1
