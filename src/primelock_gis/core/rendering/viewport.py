"""World-to-terminal viewport transforms."""

from dataclasses import dataclass

from ..geometry import Point


@dataclass
class Viewport:
    """A reversible mapping between world and terminal coordinates."""

    world_min_x: float
    world_min_y: float
    world_max_x: float
    world_max_y: float
    view_width: int
    view_height: int

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        """Validate viewport dimensions and world bounds."""
        if self.world_max_x <= self.world_min_x:
            raise ValueError("world_max_x must be greater than world_min_x")
        if self.world_max_y <= self.world_min_y:
            raise ValueError("world_max_y must be greater than world_min_y")
        if self.view_width <= 0:
            raise ValueError("view_width must be positive")
        if self.view_height <= 0:
            raise ValueError("view_height must be positive")

    def world_to_view(self, x: float, y: float) -> Point:
        """Convert world coordinates into terminal view coordinates.

        Terminal rows grow downward, so y is flipped during the transform.
        """
        view_x = (
            (x - self.world_min_x)
            / (self.world_max_x - self.world_min_x)
            * self.view_width
        )

        view_y = self.view_height - (
            (y - self.world_min_y)
            / (self.world_max_y - self.world_min_y)
            * self.view_height
        )

        return Point(view_x, view_y)

    def view_to_world(self, x: float, y: float) -> Point:
        """Convert terminal view coordinates back into world coordinates."""
        world_x = (
            x / self.view_width * (self.world_max_x - self.world_min_x)
            + self.world_min_x
        )

        world_y = (self.view_height - y) / self.view_height * (
            self.world_max_y - self.world_min_y
        ) + self.world_min_y

        return Point(world_x, world_y)

    def pan(self, dx_world: float, dy_world: float) -> "Viewport":
        """Return a viewport shifted by the given world-coordinate delta."""
        return Viewport(
            world_min_x=self.world_min_x + dx_world,
            world_min_y=self.world_min_y + dy_world,
            world_max_x=self.world_max_x + dx_world,
            world_max_y=self.world_max_y + dy_world,
            view_width=self.view_width,
            view_height=self.view_height,
        )

    def zoom(
        self,
        factor: float,
        center_world_x: float,
        center_world_y: float,
    ) -> "Viewport":
        """Return a viewport zoomed around a world-coordinate anchor.

        factor > 1 zooms in. factor < 1 zooms out.
        """
        if factor <= 0:
            raise ValueError("Zoom factor must be positive")

        return Viewport(
            world_min_x=center_world_x - (center_world_x - self.world_min_x) / factor,
            world_min_y=center_world_y - (center_world_y - self.world_min_y) / factor,
            world_max_x=center_world_x + (self.world_max_x - center_world_x) / factor,
            world_max_y=center_world_y + (self.world_max_y - center_world_y) / factor,
            view_width=self.view_width,
            view_height=self.view_height,
        )

    def resize_viewport(self, new_width: int, new_height: int) -> "Viewport":
        """Return a resized viewport that preserves map proportions.

        Rendering maps world x and y ranges independently into terminal columns
        and rows. If the screen aspect ratio changes but the world bounds stay
        fixed, geometry appears stretched. Preserve one world-units-per-cell
        scale around the same world center so resizing only reveals more or less
        area.
        """
        world_center_x = (self.world_min_x + self.world_max_x) / 2
        world_center_y = (self.world_min_y + self.world_max_y) / 2
        x_units_per_cell = (self.world_max_x - self.world_min_x) / self.view_width
        y_units_per_cell = (self.world_max_y - self.world_min_y) / self.view_height
        units_per_cell = max(x_units_per_cell, y_units_per_cell)
        new_world_width = units_per_cell * new_width
        new_world_height = units_per_cell * new_height

        return Viewport(
            world_min_x=world_center_x - new_world_width / 2,
            world_min_y=world_center_y - new_world_height / 2,
            world_max_x=world_center_x + new_world_width / 2,
            world_max_y=world_center_y + new_world_height / 2,
            view_width=new_width,
            view_height=new_height,
        )
