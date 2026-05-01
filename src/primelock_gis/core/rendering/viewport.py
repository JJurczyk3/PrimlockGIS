from dataclasses import dataclass
from ..geometry import Point


@dataclass
class Viewport:
    world_min_x: float
    world_min_y: float
    world_max_x: float
    world_max_y: float
    view_width: int
    view_height: int

    def __post_init__(self) -> None:
        self._validate()

    # Validate viewport parameters
    def _validate(self) -> None:
        if self.world_max_x <= self.world_min_x:
            raise ValueError("world_max_x must be greater than world_min_x")
        if self.world_max_y <= self.world_min_y:
            raise ValueError("world_max_y must be greater than world_min_y")
        if self.view_width <= 0:
            raise ValueError("view_width must be positive")
        if self.view_height <= 0:
            raise ValueError("view_height must be positive")
        
    
    def world_to_view(self, x: float, y: float) -> Point:
        view_x = (
            (x - self.world_min_x)
            / (self.world_max_x - self.world_min_x)
            * self.view_width
        )

        # Note the flip of the y coordinate
        view_y = self.view_height - (
            (y - self.world_min_y)
            / (self.world_max_y - self.world_min_y)
            * self.view_height
        )

        return Point(view_x, view_y)


    def view_to_world(self, x: float, y: float) -> Point:
        world_x = (
            x / self.view_width
            * (self.world_max_x - self.world_min_x)
            + self.world_min_x
        )
        
        # Note the flip of the y coordinate
        world_y = (
            (self.view_height - y)
            / self.view_height
            * (self.world_max_y - self.world_min_y)
            + self.world_min_y
        )

        return Point(world_x, world_y)
    

    # Support for resizing the viewport while keeping the same world coordinates
    def resize_viewport(self, new_width: int, new_height: int) -> "Viewport":
        return Viewport(
            world_min_x=self.world_min_x,
            world_min_y=self.world_min_y,
            world_max_x=self.world_max_x,
            world_max_y=self.world_max_y,
            view_width=new_width,
            view_height=new_height
        )


