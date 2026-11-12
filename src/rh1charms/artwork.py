"""The two drawings in 2D (mm, y up): colour regions and the body.

- The tag: a rounded rectangle with a green band at the left end and a red band at the
  right end (the Italian tricolour), and the raised red text in the white middle. Its size
  follows from the text: the font size is the smallest one that prints (text.py), and the
  margins are fixed.
- The moka pot: polygons with the origin at the bottom centre of the boiler, y up. Facet
  grooves 0.6 mm wide are cut down to white. The body is the union of everything, 0.9 mm
  larger, with its holes filled.

A region in bands[0] (white) is the body itself: it shows at the top of the body.
"""

from dataclasses import dataclass, field

from shapely import affinity
from shapely.geometry import Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from .charms import Charm
from .relief import polygons
from .text import limits, size_problems, split_lines, text_geometry

# --- the tag ----------------------------------------------------------------------------
END_BAND = 5.0  # the green and the red band at the ends
TEXT_MARGIN = 2.5  # text <-> end bands, and text <-> the long edges
CORNER = 3.0  # corner radius of the tag

# --- the moka pot (mm, origin at the bottom centre, y up) ---------------------------------
BOILER = ((-10, 0), (10, 0), (6.6, 13), (-6.6, 13))
WAIST = ((-7.1, 13), (7.1, 13), (7.1, 15.6), (-7.1, 15.6))
CHAMBER = ((-6.4, 15.6), (6.4, 15.6), (9.4, 27.4), (-9.4, 27.4))
SPOUT = ((-9, 27.4), (-12.6, 27.4), (-8.2, 22.6))
LID = ((-9.8, 28), (9.8, 28), (5.8, 30.6), (-5.8, 30.6))
KNOB = (4.4, 3.4, 1.0, (0.0, 32.3))  # rounded rectangle: width, height, radius, centre
# clockwise, as given: relief._faces turns every outline counter-clockwise before extruding
HANDLE = ((9, 26.6), (15.6, 26.6), (17, 25), (16.2, 12.6), (13.4, 12.6), (14, 23.6), (8.3, 23.6))
# facet grooves, cut down to white: (x0, x1) at the bottom and at the top of a part
GROOVES = (((3.0, 3.6), 0.0, (2.0, 2.6), 13.0),  # on the boiler
           ((1.9, 2.5), 15.6, (2.9, 3.5), 27.4))  # on the upper chamber
BODY_MARGIN = 0.9


@dataclass(frozen=True)
class Artwork:
    regions: dict[str, BaseGeometry]  # filament -> visible area
    body: Polygon  # the whole charm seen from the front
    parts: dict[str, BaseGeometry] = field(default_factory=dict)  # named areas (see below)
    text: BaseGeometry | None = None  # the raw text (the tag), in this frame
    font_size: float | None = None
    lines: tuple[str, ...] = ()
    size_bound: str = ""  # what sets an automatic font size, e.g. "the gap in '@'"


def rounded_rect(x0: float, y0: float, x1: float, y1: float, r: float) -> Polygon:
    r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
    return box(x0 + r, y0 + r, x1 - r, y1 - r).buffer(r, quad_segs=32)


def tag(c: Charm, size: float | None = None) -> Artwork:
    """The tag in its frame: x centred, the bottom edge at y = 0. `size`: the font size to
    try (wear.layout steps it up if the band cleanup would change the letters); None: the
    charm's font_size, or the smallest one that the text's own limits allow."""
    lines = split_lines(c.text, c.layout)
    lim = limits(lines)
    size = size or c.font_size or lim.size
    problems = size_problems(lines, size)
    if problems:  # before colour_bands, which would quietly repair the letters
        raise ValueError(f"{c.name}: font_size {size:g} mm is too small: {'; '.join(problems)}. "
                         f"The smallest font size for this text is {lim.size:g} mm")
    txt = text_geometry(lines, size)
    x0, y0, x1, y1 = txt.bounds
    w = 2 * END_BAND + 2 * TEXT_MARGIN + (x1 - x0)
    h = 2 * TEXT_MARGIN + (y1 - y0)
    txt = affinity.translate(txt, -(x0 + x1) / 2, TEXT_MARGIN - y0)
    body = rounded_rect(-w / 2, 0, w / 2, h, CORNER)
    green = body.intersection(box(-w / 2 - 1, -1, -w / 2 + END_BAND, h + 1))
    red = body.intersection(box(w / 2 - END_BAND, -1, w / 2 + 1, h + 1))
    middle = body.difference(green).difference(red)
    regions = {"green": green, "red": unary_union([red, txt]), "white": middle.difference(txt)}
    return Artwork(regions, body, {"middle": middle}, txt, size, lines,
                   "" if c.font_size else lim.bound)


def _knob() -> Polygon:
    w, h, r, (cx, cy) = KNOB
    return rounded_rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, r)


def _grooves() -> BaseGeometry:
    out = []
    for (a0, a1), y0, (b0, b1), y1 in GROOVES:
        for s in (1, -1):
            out.append(Polygon([(s * a0, y0), (s * a1, y0), (s * b1, y1), (s * b0, y1)]))
    return unary_union(out)


def moka(c: Charm) -> Artwork:
    """The moka pot, painted in order: a later part covers an earlier one."""
    painted = [("green", Polygon(BOILER)), ("white", Polygon(WAIST)), ("red", Polygon(CHAMBER)),
               ("red", Polygon(SPOUT)), ("red", Polygon(LID)), ("black", _knob()),
               ("black", Polygon(HANDLE))]
    visible: dict[str, list] = {}
    covered = Polygon()
    for colour, geom in reversed(painted):
        visible.setdefault(colour, []).append(geom.difference(covered))
        covered = unary_union([covered, geom])
    grooves = _grooves().intersection(unary_union([Polygon(BOILER), Polygon(CHAMBER)]))
    regions = {}
    for colour, geoms in visible.items():
        g = unary_union(geoms)
        regions[colour] = (unary_union([g, grooves]) if colour == "white"
                           else g.difference(grooves))
    grown = polygons(covered.buffer(BODY_MARGIN, quad_segs=16))
    filled = unary_union([Polygon(p.exterior) for p in grown])
    if len(polygons(filled)) != 1:
        raise ValueError(f"{c.name}: the body falls apart into {len(polygons(filled))} pieces")
    return Artwork(regions, polygons(filled)[0],
                   {"chamber": Polygon(CHAMBER), "grooves": grooves})


def make(c: Charm) -> Artwork:
    return tag(c) if c.subject == "tag" else moka(c)
