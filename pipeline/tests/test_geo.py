from shapely.geometry import LineString, Point, Polygon, box

from milmap.geo.diff import control_diff
from milmap.geo.frontline import chaikin, front_lines, nearest_on_lines, orient_left
from milmap.geo.temporal import encode_intervals

COUNTRY = box(0, 0, 10, 10)  # a square "Ukraine"; its boundary = border + coast


def test_front_excludes_border_and_keeps_interior_edge():
    occupied = box(6, 0, 10, 10)  # eastern strip touching the border on 3 sides
    lines = front_lines(occupied, COUNTRY.boundary, min_length_m=0)
    assert len(lines) == 1
    xs = {round(x, 6) for x, _ in lines[0].coords}
    assert xs == {6.0}, "only the x=6 edge faces the enemy"


def test_front_is_oriented_with_controller_on_left():
    occupied = box(6, 0, 10, 10)
    (line,) = front_lines(occupied, COUNTRY.boundary, min_length_m=0)
    (_, y0), (_, y1) = line.coords[0], line.coords[-1]
    # occupied is to the east (x > 6); travelling south (y decreasing) puts east on the left
    assert y1 < y0


def test_orient_left_flips():
    area = box(0, 0, 1, 1)
    ln = LineString([(1, 0.1), (1, 0.9)])  # area is on the left when moving north at x=1
    assert orient_left(ln, area).coords[0] == (1, 0.1)
    assert orient_left(LineString(ln.coords[::-1]), area).coords[0] == (1, 0.1)


def test_chaikin_preserves_endpoints():
    ln = LineString([(0, 0), (1, 1), (2, 0)])
    sm = chaikin(ln, 3)
    assert sm.coords[0] == (0, 0) and sm.coords[-1] == (2, 0)
    assert len(sm.coords) > len(ln.coords)


def test_nearest_on_lines():
    p = nearest_on_lines(Point(0, 5), [LineString([(1, 0), (1, 10)])])
    assert p is not None and p.x == 1 and p.y == 5


def test_diff_gain_loss_and_slivers():
    prev = Polygon([(36, 48), (37, 48), (37, 49), (36, 49)])
    curr = Polygon([(36, 48), (37.05, 48), (37.05, 49), (36, 49)])  # ~0.05° gained
    d = control_diff(prev, curr)
    assert d.gained_km2 > 300 and d.lost_km2 == 0
    # 1e-5° jitter (a redraw) must not register as change
    jitter = Polygon([(36, 48), (37.00001, 48), (37.00001, 49), (36, 49)])
    assert control_diff(prev, jitter).gained_km2 == 0


def test_temporal_intervals_collapse_unchanged_cells():
    a = box(0, 0, 1, 1)  # 4 cells of 0.5°
    b = box(0, 0, 1, 0.9)  # top row changes
    pieces = list(encode_intervals([(10, a), (11, a), (12, b), (13, b)], cell_deg=0.5))
    bottom = [p for p in pieces if p.cell[1] == 0]
    top = [p for p in pieces if p.cell[1] == 1]
    assert {(p.vf, p.vt) for p in bottom} == {(10, 14)}  # unchanged for all 4 days
    assert sorted((p.vf, p.vt) for p in top) == [(10, 12), (10, 12), (12, 14), (12, 14)]


def test_temporal_requires_ascending():
    import pytest

    with pytest.raises(ValueError):
        list(encode_intervals([(2, box(0, 0, 1, 1)), (1, box(0, 0, 1, 1))]))
