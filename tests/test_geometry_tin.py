from primelock_gis.core.geometry import Point, circumcircle_contains


def test_circumcircle_contains_point_inside():
    a = Point(0, 0)
    b = Point(2, 0)
    c = Point(0, 2)
    p = Point(0.5, 0.5)

    assert circumcircle_contains(a, b, c, p)


def test_circumcircle_contains_point_outside():
    a = Point(0, 0)
    b = Point(2, 0)
    c = Point(0, 2)
    p = Point(3, 3)

    assert not circumcircle_contains(a, b, c, p)


def test_circumcircle_contains_works_with_clockwise_triangle():
    a = Point(0, 0)
    b = Point(0, 2)
    c = Point(2, 0)
    p = Point(0.5, 0.5)

    assert circumcircle_contains(a, b, c, p)


def test_circumcircle_contains_collinear_triangle_returns_false():
    a = Point(0, 0)
    b = Point(1, 0)
    c = Point(2, 0)
    p = Point(1, 1)

    assert not circumcircle_contains(a, b, c, p)