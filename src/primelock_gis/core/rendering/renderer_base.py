"""Interface for rendering backend-independent GIS scenes."""

from .scene import (
    DrawablePoint,
    DrawablePolyline,
    DrawableTerrain,
    DrawableText,
    Scene,
)


class RendererBase:
    """Base class for all rendering backends."""

    def clear(self) -> None:
        raise NotImplementedError("clear() must be implemented by subclasses")

    def draw_terrain(self, drawable: DrawableTerrain) -> None:
        raise NotImplementedError("draw_terrain() must be implemented by subclasses")

    def draw_polyline(self, drawable: DrawablePolyline) -> None:
        raise NotImplementedError("draw_polyline() must be implemented by subclasses")

    def draw_point(self, drawable: DrawablePoint) -> None:
        raise NotImplementedError("draw_point() must be implemented by subclasses")

    def draw_text(self, drawable: DrawableText) -> None:
        raise NotImplementedError("draw_text() must be implemented by subclasses")

    def render_scene(self, scene: Scene) -> None:
        """Render a full scene in GIS display order."""
        self.clear()

        for terrain in scene.terrains:
            if terrain.visible:
                self.draw_terrain(terrain)

        for polyline in scene.polylines:
            if polyline.visible:
                self.draw_polyline(polyline)

        for point in scene.points:
            if point.visible:
                self.draw_point(point)

        for text in scene.texts:
            if text.visible:
                self.draw_text(text)
