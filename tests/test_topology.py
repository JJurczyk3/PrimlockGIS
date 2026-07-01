from primelock_gis.core.algorithms.topology import (
    build_topology_from_contour_polylines,
    build_topology_from_point_sequences,
)
from primelock_gis.core.geometry import Point
from primelock_gis.core.models.contour import ContourPolyline
from primelock_gis.core.rendering.scene_builder import topology_to_scene
from primelock_gis.core.storage.topology_export import topology_to_tables


def test_topology_from_open_polyline_creates_nodes_and_arcs():
    topology = build_topology_from_point_sequences([
        [
            Point(0, 0),
            Point(5, 0),
            Point(10, 0),
        ]
    ])

    assert len(topology.nodes) == 3
    assert len(topology.arcs) == 2
    assert topology.arcs[0].start_node == 0
    assert topology.arcs[0].end_node == 1
    assert topology.arcs[1].start_node == 1
    assert topology.arcs[1].end_node == 2
    assert topology.polygons == []


def test_topology_reuses_shared_endpoint_node():
    topology = build_topology_from_point_sequences([
        [Point(0, 0), Point(10, 0)],
        [Point(10, 0), Point(10, 10)],
    ])

    assert len(topology.nodes) == 3

    shared_nodes = [
        node
        for node in topology.nodes
        if node.x == 10 and node.y == 0
    ]
    assert len(shared_nodes) == 1
    assert shared_nodes[0].arc_ids == [0, 1]


def test_topology_splits_crossing_segments_at_intersection_node():
    topology = build_topology_from_point_sequences([
        [Point(0, 0), Point(10, 0)],
        [Point(5, -5), Point(5, 5)],
    ])

    assert len(topology.nodes) == 5
    assert len(topology.arcs) == 4

    intersection_nodes = [
        node
        for node in topology.nodes
        if node.x == 5 and node.y == 0
    ]
    assert len(intersection_nodes) == 1
    assert intersection_nodes[0].arc_ids == [0, 1, 2, 3]


def test_topology_from_closed_ring_creates_polygon_candidate():
    topology = build_topology_from_point_sequences(
        [
            [
                Point(0, 0),
                Point(10, 0),
                Point(10, 10),
                Point(0, 10),
            ]
        ],
        closed_flags=[True],
    )

    assert len(topology.nodes) == 4
    assert len(topology.arcs) == 4
    assert len(topology.polygons) == 1
    assert topology.polygons[0].arc_ids == [0, 1, 2, 3]
    assert all(arc.left_polygon == 0 for arc in topology.arcs)
    assert all(arc.right_polygon == -1 for arc in topology.arcs)


def test_topology_from_clockwise_closed_ring_assigns_polygon_to_right_side():
    topology = build_topology_from_point_sequences(
        [
            [
                Point(0, 0),
                Point(0, 10),
                Point(10, 10),
                Point(10, 0),
            ]
        ],
        closed_flags=[True],
    )

    assert len(topology.polygons) == 1
    assert all(arc.left_polygon == -1 for arc in topology.arcs)
    assert all(arc.right_polygon == 0 for arc in topology.arcs)


def test_topology_from_contour_polylines_uses_contour_closed_flag():
    contours = [
        ContourPolyline(
            level=5,
            points=[
                Point(0, 0),
                Point(10, 0),
                Point(10, 10),
                Point(0, 10),
            ],
            closed=True,
        )
    ]

    topology = build_topology_from_contour_polylines(contours)

    assert len(topology.polygons) == 1


def test_topology_to_scene_draws_arcs_and_nodes():
    topology = build_topology_from_point_sequences([
        [Point(0, 0), Point(10, 0)],
    ])

    scene = topology_to_scene(topology)

    assert len(scene.polylines) == 1
    assert len(scene.points) == 2


def test_topology_to_tables_exports_relationship_records():
    topology = build_topology_from_point_sequences([
        [Point(0, 0), Point(10, 0)],
    ])

    tables = topology_to_tables(topology)

    assert set(tables) == {"nodes", "arcs", "polygons"}
    assert tables["nodes"][0]["arc_ids"] == [0]
    assert tables["arcs"][0]["start_node"] == 0
    assert tables["arcs"][0]["end_node"] == 1
