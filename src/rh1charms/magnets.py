"""The magnet parts that are not a charm: the counter plates and the pocket gauge.

- A counter plate is worn inside the shirt and holds the charm through the fabric. It is
  3.0 mm thick, with the pockets open on top and a 0.8 mm floor towards the shirt. Its
  pockets lie where the charm's do once the two face each other across the fabric (the
  mirror image), so it fits any magnet charm of its subject and layout.
- The pocket gauge (about 8 min) has four pockets of 8.0, 8.1, 8.2 and 8.3 mm, marked with 1
  to 4 dots. They print like the charm's: on the bed side, under the same 0.6 mm roof, so
  they show the squish of the first layer that the real pockets get. Push a magnet into
  each one and set `magnet_clr` to (the pocket that holds it) - 8.0.

Both print in one colour (`plate_colour`, white by default).
"""

from collections.abc import Callable
from functools import cache, partial

from build123d import Part
from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from . import params as P
from . import relief
from .artwork import rounded_rect
from .charms import Charm
from .wear import layout

GAUGE = "pocket_gauge"
GAUGE_PITCH = 13.0  # mm between the pockets of the gauge
GAUGE_EDGE = 3.0  # plastic around the pockets of the gauge
DOT_R, DOT_PITCH, DOT_H = 0.7, 2.0, P.layers(2)  # the raised dots that number the pockets


def counter_layout(c: Charm) -> tuple[BaseGeometry, tuple[tuple[float, float], ...]]:
    """The outline of the counter plate and its pocket centres, in its print pose (pockets
    open on top). It faces the charm back to back, so its pockets are the mirror image of
    the charm's (x -> -x) around their middle."""
    pts = layout(c).pockets
    if not pts:
        raise ValueError(f"{c.name}: only a magnet charm has a counter plate")
    mx = sum(x for x, _ in pts) / len(pts)
    my = sum(y for _, y in pts) / len(pts)
    pts = tuple((round(mx - x, 6), round(y - my, 6)) for x, y in pts)
    reach = c.pocket_d / 2 + P.COUNTER_WALL
    outline = (LineString(pts).buffer(reach, quad_segs=32) if len(pts) > 1
               else Point(pts[0]).buffer(reach, quad_segs=64))
    return outline, pts


@cache
def make_counter(c: Charm) -> Part:
    """The counter plate on the bed: the floor, then the walls around the open pockets."""
    outline, pts = counter_layout(c)
    holes = unary_union([Point(p).buffer(c.pocket_d / 2, quad_segs=64) for p in pts])
    return relief.stack([(outline, 0.0, P.COUNTER_FLOOR),
                         (outline.difference(holes), P.COUNTER_FLOOR, P.COUNTER_T)])


def gauge_layout() -> tuple[BaseGeometry, list[tuple[float, float, float]], BaseGeometry]:
    """The block, the pockets (x, y, diameter) and the dots, in the print pose."""
    n, r = len(P.GAUGE_D), max(P.GAUGE_D) / 2
    xs = [(k - (n - 1) / 2) * GAUGE_PITCH for k in range(n)]
    half = (n - 1) / 2 * GAUGE_PITCH + r + GAUGE_EDGE
    y_dots = -(r + GAUGE_EDGE / 2 + DOT_R)
    block = rounded_rect(-half, y_dots - DOT_R - GAUGE_EDGE / 2, half, r + GAUGE_EDGE, 2.0)
    pockets = [(x, 0.0, d) for x, d in zip(xs, P.GAUGE_D)]
    dots = unary_union([Point(x + (j - k / 2) * DOT_PITCH, y_dots).buffer(DOT_R, quad_segs=16)
                        for k, x in enumerate(xs) for j in range(k + 1)])
    return block, pockets, dots


@cache
def make_gauge() -> Part:
    """The pocket gauge on the bed: pockets on the bed side, the roof, and the dots on top."""
    block, pockets, dots = gauge_layout()
    holes = unary_union([Point(x, y).buffer(d / 2, quad_segs=64) for x, y, d in pockets])
    return relief.fuse([
        relief.slab(block.difference(holes), 0.0, P.POCKET_DEPTH),
        relief.slab(block, P.POCKET_DEPTH, P.MAGNET_BODY_T),
        relief.slab(dots, P.MAGNET_BODY_T, round(P.MAGNET_BODY_T + DOT_H, 6))])


def extras(charms: list[Charm]) -> list[tuple[str, str, Callable[[], Part]]]:
    """(part name, filament, builder) of the single-colour parts that the charms need: the
    counter plate of every magnet charm (once per name: the first charm's), and the pocket
    gauge once, in the first magnet charm's plate colour. export and render both use it."""
    magnets = [c for c in charms if c.wear == "magnet"]
    out, seen = [], set()
    for c in magnets:
        if c.counter_name not in seen:
            seen.add(c.counter_name)
            out.append((c.counter_name, c.plate_colour, partial(make_counter, c)))
    if magnets:
        out.append((GAUGE, magnets[0].plate_colour, make_gauge))
    return out
