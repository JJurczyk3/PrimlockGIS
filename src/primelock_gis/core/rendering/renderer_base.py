"""Base renderer interface for Primelock GIS.

This module describes HOW renderers draw the drawable objects defined
in scene.py. Concrete renderers, such as terminal or Tkinter renderers,
will implement these methods.
"""

from .scene import (
    Scene,
    DrawablePolygon,
    DrawablePolyline,
    DrawablePoint,
    DrawableText,
)


class RendererBase:
    """Base class for all rendering backends."""

    def clear(self) -> None:
        raise NotImplementedError("clear() must be implemented by subclasses")

    def draw_polygon(self, drawable: DrawablePolygon) -> None:
        raise NotImplementedError("draw_polygon() must be implemented by subclasses")

    def draw_polyline(self, drawable: DrawablePolyline) -> None:
        raise NotImplementedError("draw_polyline() must be implemented by subclasses")

    def draw_point(self, drawable: DrawablePoint) -> None:
        raise NotImplementedError("draw_point() must be implemented by subclasses")

    def draw_text(self, drawable: DrawableText) -> None:
        raise NotImplementedError("draw_text() must be implemented by subclasses")

    def render_scene(self, scene: Scene) -> None:
        """Render a full scene in GIS display order."""

        self.clear()

        for polygon in scene.polygons:
            if polygon.visible:
                self.draw_polygon(polygon)

        for polyline in scene.polylines:
            if polyline.visible:
                self.draw_polyline(polyline)

        for point in scene.points:
            if point.visible:
                self.draw_point(point)

        for text in scene.texts:
            if text.visible:
                self.draw_text(text)