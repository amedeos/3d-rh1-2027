"""The two drawings in 2D (mm, y up): colour regions and the body.

- The tag: a rounded rectangle with a green band at the left end and a red band at the
  right end (the Italian tricolour), and the raised red text in the white middle. Its size
  follows from the text: the font size is the smallest one that prints (text.py), and the
  margins are fixed.
- The moka pot: polygons with the origin at the bottom centre of the boiler, y up. Facet
  grooves 0.6 mm wide are cut down to white. The body is the union of everything, 0.9 mm
  larger, with its small holes filled.
- The moka that pours (layout `pour`) is mirrored (the spout on the right, so that the text
  reads away from it) and leans forward by POUR_TILT. A white stream leaves the spout along
  its axis and bends down; the text, in raised red letters, starts at the spout and runs
  along the stream (text.arc_text). It has no black: its knob and handle are red. It is too
  narrow for a clip's channel, so a clip puts a backing plate behind it (`Artwork.plate`,
  wear.py).

A region in bands[0] (white) is the body itself: it shows at the top of the body.
"""

import math
from dataclasses import dataclass, field
from functools import cache

import numpy as np
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from . import params as P
from .charms import Charm
from .relief import polygons
from .text import (
    arc_limits,
    arc_text,
    glyph,
    glyph_limits,
    limits,
    size_problems,
    split_lines,
    text_em,
    text_geometry,
)

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
WINDOW_MIN = 4.0  # mm2: smaller holes in the body are filled (margins that nearly meet)

# --- the stream of a moka with a text -----------------------------------------------------
POUR_TILT = 35.0  # degrees: the moka leans forward (clockwise, once mirrored) to pour
SPOUT_AXIS = ((-8.6, 25.0), (-12.6, 27.4))  # as drawn: the middle of its base, its tip
STREAM_MARGIN = 1.5  # the letters <-> the long edges of the stream
STREAM_END = 1.0  # the letters <-> the round ends of the stream
STREAM_CLEAR = 1.0  # the letters <-> every part of the moka (the spout and the lid are red)
# degrees: how far the stream may bend along its text, to stay readable. It sets the radius
# of the middle line for the lead and the text; the text lies on a smaller radius (its
# baseline), so the letters turn a few degrees more (64 for 'services')
STREAM_TURN = 60.0
STREAM_RADIUS = 18.0  # mm: the tightest bend of the stream (its middle line)
LEAD_STEP = 0.5  # mm: the text moves along the stream until it clears the moka
# the automatic font size of the moka that pours is at least this (mm): the owner's choice
# after a test print (2026-11-16), so that the letters fill the stream
POUR_FONT = 10.0


class TooSmall(ValueError):
    """A font size under the text's limits (wear.layout tries the next automatic size)."""


@dataclass(frozen=True)
class Artwork:
    regions: dict[str, BaseGeometry]  # filament -> visible area
    body: Polygon  # the whole charm seen from the front
    parts: dict[str, BaseGeometry] = field(default_factory=dict)  # named areas (see below)
    text: BaseGeometry | None = None  # the raw text (the tag), in this frame
    font_size: float | None = None
    lines: tuple[str, ...] = ()
    size_bound: str = ""  # what sets an automatic font size, e.g. "the gap in '@'"
    plate: bool = False  # too narrow for a clip's channel: a clip needs a backing plate


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
        raise TooSmall(f"{c.name}: font_size {size:g} mm is too small: {'; '.join(problems)}. "
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
    parts = {"middle": middle, "text_zone": middle.buffer(-0.5)}  # clear of the end bands
    return Artwork(regions, body, parts, txt, size, lines, "" if c.font_size else lim.bound)


def _knob() -> Polygon:
    w, h, r, (cx, cy) = KNOB
    return rounded_rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, r)


def _grooves() -> BaseGeometry:
    out = []
    for (a0, a1), y0, (b0, b1), y1 in GROOVES:
        for s in (1, -1):
            out.append(Polygon([(s * a0, y0), (s * a1, y0), (s * b1, y1), (s * b0, y1)]))
    return unary_union(out)


def pour_pose(geom: BaseGeometry, tilt: float = POUR_TILT) -> BaseGeometry:
    """The moka's drawing as it pours: mirrored (the spout on the right) and leant clockwise
    by `tilt` degrees about the bottom centre of the boiler."""
    return affinity.rotate(affinity.scale(geom, -1, 1, origin=(0, 0)), -tilt, origin=(0, 0))


@dataclass(frozen=True)
class Stream:
    """Where the stream and its text go, for one text and font size. Angles in degrees,
    around `centre`; the stream bends clockwise, so the text reads left to right on it."""

    size: float  # the font size
    centre: tuple[float, float]
    middle: float  # radius of the middle line of the stream
    half: float  # half the width of the stream
    base: float  # radius of the baseline of the text
    start: float  # the spout end of the stream (the centre of its round end)
    end: float  # the other end
    mid: float  # the middle of the text

    @property
    def ratio(self) -> float:
        """The baseline radius over the font size (text.arc_limits)."""
        return self.base / self.size


def stream_layout(line: str, size: float, lead: float = 0.0, tilt: float = POUR_TILT) -> Stream:
    """The stream leaves the tip of the spout along the spout's axis and bends down along a
    circle: STREAM_RADIUS at least, and large enough that an arc of the middle line as long
    as the lead and the text turns STREAM_TURN at most (the text, on its baseline, turns a
    little more). The text starts `lead` mm plus STREAM_END from the tip of the spout, and
    the stream goes on STREAM_END after its last letter, then ends round (its ends are
    half-discs, centred on `start` and `end`)."""
    root, tip = (pour_pose(Point(p), tilt) for p in SPOUT_AXIS)
    phi = math.atan2(tip.y - root.y, tip.x - root.x)  # where the coffee goes
    _, y0, _, y1 = text_em((line,)).bounds
    half = (y1 - y0) * size / 2 + STREAM_MARGIN
    length = len(line) * glyph(line[0])[1] * size
    lead = lead + STREAM_END
    middle = max(STREAM_RADIUS, (lead + length) / math.radians(STREAM_TURN))
    # the centre lies to the right of the way the coffee goes: the stream bends clockwise
    centre = (tip.x + middle * math.sin(phi), tip.y - middle * math.cos(phi))
    base = middle - (y0 + y1) / 2 * size  # the text in the middle of the stream
    start = math.degrees(phi) + 90
    first = start - math.degrees(lead / middle)
    mid = first - math.degrees(length / 2 / base)
    end = first - math.degrees(length / base) - math.degrees(STREAM_END / middle)
    return Stream(size, centre, middle, half, base, start, end, mid)


@cache
def smallest_size(c: Charm) -> tuple[float, str]:
    """The smallest font size of the charm's text, and what sets it. The moka's text is bent:
    the tops of its glyphs spread and their bottoms draw together, so only the bent line
    counts (arc_limits). The search starts from its glyphs' own limits, which the bend does
    not change. The bent text is measured on the stream before the text moves along it
    (lead 0); moving on makes the stream gentler, so this size is on the safe side."""
    if c.subject == "tag":
        lim = limits(split_lines(c.text, c.layout))
        return lim.size, lim.bound
    lim = glyph_limits(c.text)
    size = lim.size
    for k in range(P.SIZE_STEPS):
        size = round(lim.size + 0.1 * k, 1)
        bent = arc_limits(c.text, stream_layout(c.text, size).ratio)
        if not size_problems((c.text,), size, bent):
            return size, lim.bound if k == 0 else f"the bent text: {bent.bound}"
    raise ValueError(f"{c.name}: no font size up to {size:g} mm prints the bent text")


def auto_size(c: Charm) -> tuple[float, str]:
    """The automatic font size and what sets it: the smallest that prints, and on the moka
    that pours at least POUR_FONT."""
    size, bound = smallest_size(c)
    if c.drawing == "moka_pour" and size < POUR_FONT:
        return POUR_FONT, f"{size:g} mm, {bound}; the stream takes {POUR_FONT:g} mm"
    return size, bound


def _arc(centre, radius: float, a0: float, a1: float) -> LineString:
    angles = np.radians(np.linspace(a0, a1, max(16, int(abs(a0 - a1)) + 1)))
    return LineString(np.column_stack([centre[0] + radius * np.cos(angles),
                                       centre[1] + radius * np.sin(angles)]))


def _stream(c: Charm, size: float, pot: BaseGeometry):
    """The stream and its letters: the text moves along the stream, LEAD_STEP at a time,
    until it is STREAM_CLEAR from every part of the moka."""
    lead = 0.0
    for _ in range(100):
        s = stream_layout(c.text, size, lead)
        letters = arc_text(c.text, size, s.base, s.mid, s.centre)
        if letters.distance(pot) >= STREAM_CLEAR - 1e-9:
            band = _arc(s.centre, s.middle, s.start, s.end).buffer(s.half, quad_segs=16)
            return s, band, letters
        lead += LEAD_STEP
    raise ValueError(f"{c.name}: the letters never clear the moka")


def moka(c: Charm, size: float | None = None) -> Artwork:
    """The moka pot, painted in order: a later part covers an earlier one. The moka that
    pours (pour_pose) has a red knob and handle, and its stream is painted first, under the
    pot. `size`: the font size to try (wear.layout steps it up if the band cleanup would
    change the letters); None: the charm's font_size, or the automatic one (auto_size)."""
    pour = c.drawing == "moka_pour"
    dark = "red" if pour else "black"
    boiler, chamber = Polygon(BOILER), Polygon(CHAMBER)
    painted = [("green", boiler), ("white", Polygon(WAIST)), ("red", chamber),
               ("red", Polygon(SPOUT)), ("red", Polygon(LID)), (dark, _knob()),
               (dark, Polygon(HANDLE))]
    grooves = _grooves()
    stream = bound = None
    if pour:
        # a forced size needs no automatic one (and no smallest_size, which can fail)
        bound = "" if c.font_size else auto_size(c)[1]
        size = size or c.font_size or auto_size(c)[0]
        painted = [(colour, pour_pose(g)) for colour, g in painted]
        boiler, chamber, grooves = (pour_pose(g) for g in (boiler, chamber, grooves))
        pot = unary_union([g for _, g in painted])
        stream, band, letters = _stream(c, size, pot)
        # the bent line as it lies on this stream: only it is printed
        problems = size_problems((c.text,), size, arc_limits(c.text, stream.ratio))
        if problems:  # before colour_bands, which would quietly repair the letters
            try:
                hint = f". The smallest font size for this text is {smallest_size(c)[0]:g} mm"
            except ValueError as e:
                hint = f" ({e})"
            raise TooSmall(f"{c.name}: font_size {size:g} mm is too small: "
                           f"{'; '.join(problems)}{hint}")
        painted.insert(0, ("white", band))
    visible: dict[str, list] = {}
    covered = Polygon()
    for colour, geom in reversed(painted):
        visible.setdefault(colour, []).append(geom.difference(covered))
        covered = unary_union([covered, geom])
    grooves = grooves.intersection(unary_union([boiler, chamber]))
    regions = {}
    for colour, geoms in visible.items():
        g = unary_union(geoms)
        regions[colour] = (unary_union([g, grooves]) if colour == "white"
                           else g.difference(grooves))
    parts = {"chamber": chamber, "boiler": boiler, "grooves": grooves}
    if stream is not None:  # the letters are red, on the white stream
        regions["red"] = unary_union([regions["red"], letters])
        regions["white"] = regions["white"].difference(letters)
        parts["stream"] = band
        parts["pot"] = pot
        parts["text_zone"] = band.buffer(-0.5).difference(pot.buffer(0.5))
    grown = polygons(covered.buffer(BODY_MARGIN, quad_segs=16))
    filled = unary_union([Polygon(p.exterior, [h for h in p.interiors
                                               if Polygon(h).area >= WINDOW_MIN])
                          for p in grown])
    if len(polygons(filled)) != 1:
        raise ValueError(f"{c.name}: the body falls apart into {len(polygons(filled))} pieces")
    if stream is None:
        return Artwork(regions, polygons(filled)[0], parts)
    return Artwork(regions, polygons(filled)[0], parts, letters, size, (c.text,), bound,
                   plate=True)


def make(c: Charm, size: float | None = None) -> Artwork:
    return tag(c, size) if c.subject == "tag" else moka(c, size)
