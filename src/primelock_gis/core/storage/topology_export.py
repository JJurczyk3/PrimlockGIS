"""Export topology relationships as simple table-like records."""

from primelock_gis.core.models.vector import TopologyModel


def topology_to_tables(topology: TopologyModel) -> dict[str, list[dict]]:
    """Return node, arc, and polygon relationship tables."""
    return {
        "nodes": [
            {
                "id": node.id,
                "x": node.x,
                "y": node.y,
                "z": node.z,
                "arc_ids": list(node.arc_ids),
            }
            for node in topology.nodes
        ],
        "arcs": [
            {
                "id": arc.id,
                "start_node": arc.start_node,
                "end_node": arc.end_node,
                "intermediate_points": list(arc.intermediate_points),
                "left_polygon": arc.left_polygon,
                "right_polygon": arc.right_polygon,
            }
            for arc in topology.arcs
        ],
        "polygons": [
            {
                "id": polygon.id,
                "arc_ids": list(polygon.arc_ids),
                "outer_polygon": polygon.outer_polygon,
            }
            for polygon in topology.polygons
        ],
    }
