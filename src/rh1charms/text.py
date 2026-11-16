"""Raised text in Red Hat Mono Bold: glyph outlines, line layout and the smallest font size.

The glyphs come straight from the bundled TTF (fontTools): their curves become polylines,
and the fill uses the TrueType rule (nonzero winding), evaluated exactly. All the work is
in shapely; build123d only extrudes the finished bands (relief.py).

Font size = the em size in mm: at 8.3 mm, one em is 8.3 mm, and every character of this
monospaced font is 0.6 em wide.

The smallest font size: glyphs scale linearly, so the text is measured once, at one em.
The narrowest gap is the largest closing radius (times 2) that keeps the topology of the
text (the number of pieces and of holes): a wider closing would join two strokes or close a
counter. The thinnest stroke is the same with an opening: a wider one would break a stroke
or make a piece vanish. Neither changes at a crotch or at the tip of a stroke, which every
size has and the printer only rounds. `limits().size` is then the smallest size, rounded up
to 0.1 mm, at which the gap is at least MIN_GAP and the stroke at least MIN_STROKE.

That size is a lower bound: a stroke that vanishes without changing the topology (the foot
of an L, the bar of a 7) does not show here. wear._artwork_and_bands checks the letters
after the band cleanup and raises the size until they come through it (wear.text_damage).
"""

import math
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import numpy as np
import shapely
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from shapely import affinity
from shapely.geometry import LinearRing, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import polygonize, unary_union

from . import params as P

FONT = Path(__file__).resolve().parent / "fonts" / "RedHatMono-Bold.ttf"
if not FONT.is_file():  # never fall back to another font silently
    raise FileNotFoundError(f"bundled font missing: {FONT}")
LINE_PITCH = 1.1  # em, from one baseline to the next (two_lines)
FLAT_STEP = 0.005  # em: the longest segment of a flattened curve (0.04 mm at 8.3 mm)
TOPO_CRUMB = 1e-5  # em2: smaller pieces and holes do not count for the topology
# em: the radius scan of narrowest, before the bisection. A change can come and go between
# two radii (a new hole that fills again, a stroke that splits and then vanishes), so the
# step must stay under that range: the outer ring of '@' splits at r = 0.0274 em and is gone
# by 0.030 em, and 0.005 missed it (tests/test_text.py checks that stroke)
SCAN_STEP = 0.0025
SCAN_TOP = 0.3  # em: no stroke or gap of a text is wider than 2 * this
LAYOUTS = ("one_line", "two_lines")


class _Flatten(BasePen):
    """Collects the closed contours of a glyph as polylines (font units)."""

    def __init__(self, glyph_set):
        super().__init__(glyph_set)
        self.rings: list[np.ndarray] = []
        self._cur: list[tuple[float, float]] = []

    def _moveTo(self, pt):
        self._cur = [pt]

    def _lineTo(self, pt):
        self._cur.append(pt)

    def _bezier(self, pts: np.ndarray):
        length = float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())
        n = max(2, math.ceil(length / (FLAT_STEP * self._upm)))
        t = np.linspace(0, 1, n + 1)[1:, None]
        k = len(pts) - 1
        curve = sum(math.comb(k, i) * (1 - t) ** (k - i) * t ** i * pts[i] for i in range(k + 1))
        self._cur.extend(map(tuple, curve))

    def _qCurveToOne(self, pt1, pt2):
        self._bezier(np.array([self._cur[-1], pt1, pt2], dtype=float))

    def _curveToOne(self, pt1, pt2, pt3):
        self._bezier(np.array([self._cur[-1], pt1, pt2, pt3], dtype=float))

    def _closePath(self):
        if len(self._cur) > 2:
            self.rings.append(np.array(self._cur, dtype=float))
        self._cur = []

    _endPath = _closePath


def _winding(point: tuple[float, float], ring: np.ndarray) -> int:
    """Winding number of a closed polyline around a point (any ring, even self-crossing)."""
    x, y = point
    a = ring
    b = np.roll(ring, -1, axis=0)
    cross = (b[:, 0] - a[:, 0]) * (y - a[:, 1]) - (x - a[:, 0]) * (b[:, 1] - a[:, 1])
    up = (a[:, 1] <= y) & (b[:, 1] > y) & (cross > 0)
    down = (a[:, 1] > y) & (b[:, 1] <= y) & (cross < 0)
    return int(up.sum() - down.sum())


def filled_area(rings: list[np.ndarray]) -> BaseGeometry:
    """The area the contours fill with the nonzero rule (TrueType), evaluated exactly on the
    faces of the noded outline: overlapping contours and either direction are fine."""
    rings = [r for r in rings if len(r) > 2]
    if not rings:
        return Polygon()
    faces = list(polygonize(unary_union([LinearRing(r) for r in rings])))
    keep = []
    for face in faces:
        p = face.representative_point()
        if sum(_winding((p.x, p.y), r) for r in rings) != 0:
            keep.append(face)
    return shapely.make_valid(unary_union(keep)) if keep else Polygon()


@cache
def _font() -> TTFont:
    return TTFont(FONT)


@cache
def glyph(ch: str) -> tuple[BaseGeometry, float]:
    """The filled outline of one character and its advance width, in em (baseline y = 0)."""
    font = _font()
    name = font.getBestCmap().get(ord(ch))
    if name is None:
        raise ValueError(f"Red Hat Mono Bold has no glyph for {ch!r}")
    upm = font["head"].unitsPerEm
    pen = _Flatten(font.getGlyphSet())
    pen._upm = upm
    font.getGlyphSet()[name].draw(pen)
    return filled_area([r / upm for r in pen.rings]), font["hmtx"][name][0] / upm


def split_lines(text: str, layout: str) -> tuple[str, ...]:
    """The lines of a layout: one_line is the text; two_lines splits at a line break (`\\n`)
    or else before the last '@' (consulting / @italy:~$)."""
    if layout not in LAYOUTS:
        raise ValueError(f"unknown layout {layout!r}; choose from {', '.join(LAYOUTS)}")
    if not text.strip():
        raise ValueError("the text is empty")
    if layout == "one_line":
        if "\n" in text:
            raise ValueError("a one_line text has no line break; use layout two_lines")
        return (text,)
    if "\n" in text:
        first, _, second = text.partition("\n")
        if "\n" in second:
            raise ValueError("a two_lines text has one line break, not more")
    else:
        at = text.rfind("@")
        if at <= 0:
            raise ValueError(f"cannot split {text!r} in two lines: put a line break (\\n) where "
                             "the second line starts")
        first, second = text[:at], text[at:]
    if not first.strip() or not second.strip():
        raise ValueError(f"both lines of {text!r} must have some text")
    return (first, second)


@cache
def text_em(lines: tuple[str, ...]) -> BaseGeometry:
    """The filled text in em: the lines left-aligned, LINE_PITCH apart, the first baseline at
    y = 0. The font is monospaced (checked), so the characters sit on a grid."""
    advances = {glyph(ch)[1] for line in lines for ch in line}
    if len(advances) != 1:
        raise ValueError(f"the characters of {lines} have different widths {sorted(advances)}: "
                         "the layout needs a monospaced font")
    adv = advances.pop()
    pieces = [affinity.translate(glyph(ch)[0], j * adv, -i * LINE_PITCH)
              for i, line in enumerate(lines) for j, ch in enumerate(line)]
    return unary_union([p for p in pieces if not p.is_empty])


def text_geometry(lines: tuple[str, ...], size: float) -> BaseGeometry:
    """The filled text in mm, at font size `size`."""
    return affinity.scale(text_em(lines), size, size, origin=(0, 0))


def _features(geom: BaseGeometry, crumb: float = TOPO_CRUMB) -> tuple[list, list]:
    """The pieces of a geometry and its holes (as polygons), leaving out crumbs."""
    pieces = [p for p in getattr(geom, "geoms", [geom])
              if isinstance(p, Polygon) and p.area > crumb]
    holes = [Polygon(h) for p in pieces for h in p.interiors if Polygon(h).area > crumb]
    return pieces, holes


def topology(geom: BaseGeometry, crumb: float = TOPO_CRUMB) -> tuple[int, int]:
    """(number of pieces, number of holes), leaving out crumbs."""
    pieces, holes = _features(geom, crumb)
    return len(pieces), len(holes)


def _morph(geom: BaseGeometry, r: float, op: str) -> BaseGeometry:
    if op == "open":
        return geom.buffer(-r, quad_segs=16).buffer(r, quad_segs=16)
    return geom.buffer(r, quad_segs=16).buffer(-r, quad_segs=16)


def _inside(parts: list, regions: list) -> tuple[int, ...]:
    """How many of `parts` lie in each of `regions`, and (last) in none of them. A part goes
    to the first region that contains it: list nested regions smallest first."""
    counts = [0] * (len(regions) + 1)
    for part in parts:
        point = part.representative_point()
        counts[next((i for i, g in enumerate(regions) if g.contains(point)), -1)] += 1
    return tuple(counts)


def _signature(morphed: BaseGeometry, original: tuple[list, list], op: str) -> tuple:
    """The topology of a closing or an opening, counted so that two changes cannot cancel
    out. A closing only adds material: its holes lie in the original holes or, when a gap
    closes, outside all of them (a new hole); so it counts the pieces, the holes in each
    original hole and the new holes. A plain count missed a gap: in '~$ espresso', the two
    'e' gaps close (+2 holes) where the two counters of '$' fill (-2). An opening only takes
    material away: it counts the pieces in each original piece, and the holes."""
    pieces, holes = _features(morphed)
    if op == "close":
        return len(pieces), _inside(holes, original[1])
    return _inside(pieces, original[0]), len(holes)


def same_features(geom: BaseGeometry, reference: BaseGeometry, crumb: float = TOPO_CRUMB) -> bool:
    """geom has the pieces and holes of `reference`, one for one: each piece of the reference
    holds one piece of geom, each hole one hole, and nothing lies anywhere else. Plain counts
    can cancel out (a counter that fills and a gap that closes into a new hole)."""
    ref = tuple(sorted(f, key=lambda g: g.area) for f in _features(reference, crumb))
    pieces, holes = _features(geom, crumb)
    return all(_inside(mine, theirs) == (1,) * len(theirs) + (0,)
               for mine, theirs in zip((pieces, holes), ref))


def narrowest(geom: BaseGeometry, op: str) -> float:
    """The width of the narrowest gap (op 'close') or the thinnest stroke (op 'open'): twice
    the largest radius that keeps the topology (_signature). A scan from 0 finds the first
    radius that changes it, then a bisection between the last good radius and that one."""
    # smallest first, so that a hole inside a piece inside another hole (as in '®') counts
    # under its own hole, not under the outer one (_inside)
    original = tuple(sorted(f, key=lambda g: g.area) for f in _features(geom))
    start = _signature(geom, original, op)

    def keeps(r: float) -> bool:
        return _signature(_morph(geom, r, op), original, op) == start

    lo, r = 0.0, SCAN_STEP
    while r <= SCAN_TOP + 1e-12:
        if not keeps(r):
            break
        lo, r = r, r + SCAN_STEP
    else:
        return 2 * SCAN_TOP
    hi = r
    for _ in range(24):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if keeps(mid) else (lo, mid)
    return 2 * lo


@cache
def _glyph_limits(ch: str) -> tuple[float, float]:
    """(thinnest stroke, narrowest gap) of one character, in em."""
    g = glyph(ch)[0]
    return narrowest(g, "open"), narrowest(g, "close")


@dataclass(frozen=True)
class Limits:
    """The thinnest stroke and the narrowest gap of a text, in em, and where they are."""

    stroke: float
    gap: float
    stroke_at: str  # "'@'", or "between two characters"
    gap_at: str

    @property
    def size(self) -> float:
        """The smallest font size (mm, rounded up to 0.1 mm) that prints every stroke and
        keeps every gap open."""
        need = max(P.MIN_STROKE / self.stroke, P.MIN_GAP / self.gap)
        return math.ceil(need * 10 - 1e-9) / 10

    @property
    def bound(self) -> str:
        """What sets the size, e.g. "the gap in '@'"."""
        if P.MIN_GAP / self.gap >= P.MIN_STROKE / self.stroke:
            return f"the gap {self.gap_at}"
        return f"the stroke {self.stroke_at}"


def _where(value: float, per_char: dict[str, float]) -> str:
    """The characters whose own narrowest feature is the text's (else: between two)."""
    found = [ch for ch, v in per_char.items() if v <= value * (1 + 1e-6)]
    return "in " + ", ".join(repr(ch) for ch in found) if found else "between two characters"


def _limits_of(geom: BaseGeometry, text: str) -> Limits:
    """The limits of a text drawn at one em (straight or bent), and where they are."""
    chars = sorted({ch for ch in text if not glyph(ch)[0].is_empty})
    stroke, gap = narrowest(geom, "open"), narrowest(geom, "close")
    return Limits(stroke, gap, _where(stroke, {c: _glyph_limits(c)[0] for c in chars}),
                  _where(gap, {c: _glyph_limits(c)[1] for c in chars}))


@cache
def limits(lines: tuple[str, ...]) -> Limits:
    return _limits_of(text_em(lines), "".join(lines))


@cache
def glyph_limits(text: str) -> Limits:
    """The limits of the text's characters each on its own: a bent line keeps every glyph's
    shape, so its limits are never wider than these (the gaps between glyphs aside)."""
    chars = sorted({ch for ch in text if not glyph(ch)[0].is_empty})
    strokes = {c: _glyph_limits(c)[0] for c in chars}
    gaps = {c: _glyph_limits(c)[1] for c in chars}
    stroke, gap = min(strokes.values()), min(gaps.values())
    return Limits(stroke, gap, _where(stroke, strokes), _where(gap, gaps))


def arc_text(line: str, size: float, radius: float, mid: float = 90.0,
             centre: tuple[float, float] = (0.0, 0.0)) -> BaseGeometry:
    """One line of text along a circle (mm), reading clockwise: left to right over the top.
    Every glyph keeps its shape. The middle of its baseline lies on the circle of `radius`
    around `centre`, one advance (0.6 em) from the next one along the circle, and the glyph
    turns so that its baseline is tangent there. The middle of the text is at the angle
    `mid` (degrees). On the outside of a circle the tops of the glyphs spread and the
    descenders draw together: arc_limits() measures the gaps of the text as it is bent."""
    text_em((line,))  # every character the same width
    adv = glyph(line[0])[1]
    pieces = []
    for j, ch in enumerate(line):
        g = glyph(ch)[0]
        if g.is_empty:
            continue
        along = ((j + 0.5) - len(line) / 2) * adv * size  # from the middle of the text
        p = affinity.scale(affinity.translate(g, -adv / 2, 0), size, size, origin=(0, 0))
        p = affinity.rotate(affinity.translate(p, 0, radius),
                            mid - math.degrees(along / radius) - 90, origin=(0, 0))
        pieces.append(affinity.translate(p, *centre))
    return unary_union(pieces)


@cache
def arc_limits(line: str, ratio: float) -> Limits:
    """The limits of one line bent along a circle whose radius is `ratio` times the font
    size (arc_text): the text is measured in em, as limits() does for a straight one."""
    return _limits_of(arc_text(line, 1.0, ratio), line)


def size_problems(lines: tuple[str, ...], size: float, lim: Limits | None = None) -> list[str]:
    """What breaks the limits at a given font size (empty list: it prints). `lim`: the
    limits to use (arc_limits for a bent line); by default those of the straight lines."""
    lim = lim or limits(lines)

    def under(value: float, limit: float) -> str:
        # the value rounded down and the limit up, so that the two never look the same
        return f"{math.floor(value * 1000) / 1000:.3f} mm, under {math.ceil(limit * 1000) / 1000:.3f} mm"

    problems = []
    if lim.stroke * size < P.MIN_STROKE - 1e-9:
        problems.append(f"the thinnest stroke ({lim.stroke_at}) is "
                        f"{under(lim.stroke * size, P.MIN_STROKE)}")
    if lim.gap * size < P.MIN_GAP - 1e-9:
        problems.append(f"the narrowest gap ({lim.gap_at}) is {under(lim.gap * size, P.MIN_GAP)}")
    return problems
