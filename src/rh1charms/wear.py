"""The ways to wear a charm, and its solids: an eyelet, magnet pockets, or a lanyard clip.

- `eyelet`: a tab with a hole on top, straight above the centre of mass, so the charm hangs
  upright (like the ornament tab of 3d-linux). Band 0 only: the drawing keeps its colours.
- `magnet`: the body is 2.8 mm thick, with blind pockets on the bed side for 8 x 2 mm
  discs, under a 0.6 mm bridged roof. The tag gets two, a quarter of its width from each
  end, so it cannot turn; the moka one, in the upper chamber, above the centre of mass. The
  moka that pours gets two, in the upper chamber and in the boiler: its centre of mass lies
  on the stream, too narrow for a pocket.
- `clip`: a bar on the bed, a gap for the ribbon, then the charm from z = 2.8 mm. Outside
  the channel, the body is solid down to the bed: its walls beside the channel are the
  risers, and the only bridge is the ceiling of the channel. The bar joins the left wall and
  stops SLIT short of the right one: the ribbon slides in through the slit. The plain moka
  is too narrow for the channel. The moka that pours gets a backing plate, exactly the
  channel and its walls wide, and two bars on it with their slits on opposite sides. On
  moka_pour_rh1_clip the plate carries two texts too, top right and bottom centre, and
  grows downwards to make room for the bottom one.

Print pose: front face up, z = 0 on the bed. Band 0 is a stack of slabs (`slabs0`): the
pockets or the channel are cut from the lower ones.
"""

import math
from dataclasses import dataclass, replace
from functools import cache

from build123d import CenterOf, Part, Rot
from shapely import affinity
from shapely.geometry import Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from . import artwork, relief
from . import params as P
from .artwork import rounded_rect
from .charms import PLATE_COLOURS, TEXTS, Charm
from .relief import Slab, polygons
from .text import limits, same_features, size_problems, text_geometry

# The band cleanup (relief.colour_bands) repairs silently: it opens every band by
# MIN_STROKE / 2 and fills specks. The letters must come through it unchanged but for their
# corners, for any text: same pieces and holes, no piece lost larger than a rounded corner,
# no gap filled larger than a speck, and only a sliver of the area lost.
LOST_MAX = 0.15  # mm2: the largest piece of a letter the cleanup may take (a corner)
LOST_SHARE = 0.015  # the most of the letters' area it may take in all
# a lost piece thinner than twice this everywhere is a sliver shaved off an outline (long
# bent outlines at a large size give one), not a stroke: only LOST_SHARE counts it
SLIVER = 0.05


@dataclass(frozen=True)
class Clip:
    channel: tuple[float, float]  # x range of the channel
    bars: tuple[tuple[float, float, float, float], ...]  # x0, x1, y0, y1 of each bar, top first
    walls: BaseGeometry  # the footprint under the charm outside the channel (the risers)
    plate: BaseGeometry | None = None  # the backing plate, if the charm needs one
    # the texts on the plate, top first: (text, filament, its raw letters where they lie),
    # and their font size
    letters: tuple[tuple[str, str, BaseGeometry], ...] = ()
    font: float = 0.0


@dataclass(frozen=True)
class CharmLayout:
    """A charm in 2D (mm) with the z range of every band."""

    art: artwork.Artwork
    bands: list[BaseGeometry]  # printable footprint of every band; bands[0] has the tab
    z: list[tuple[float, float]]  # (z0, z1) of every band in the print pose
    slabs0: tuple[Slab, ...]  # band 0 as stacked slabs (pockets, channel, bar cut out)
    hole: tuple[float, float, float] | None  # eyelet: x, y and radius of the hole
    pockets: tuple[tuple[float, float], ...]  # magnet: pocket centres
    clip: Clip | None
    centre: tuple[float, float]  # centre of mass (x, y), from the slabs

    @property
    def slabs(self) -> list[Slab]:
        return [*self.slabs0, *((b, z0, z1) for b, (z0, z1) in zip(self.bands[1:], self.z[1:]))]

    @property
    def size(self) -> tuple[float, float, float]:
        """Width, height (the tab included) and thickness."""
        x0, y0, x1, y1 = self.bands[0].bounds
        return x1 - x0, y1 - y0, self.z[-1][1]

    @property
    def pivot(self) -> tuple[float, float, float] | None:
        """Where the charm hangs from: the top of the eyelet hole, or the middle of a lone
        magnet (x, y, and 0 for a magnet). None for two magnets or a clip."""
        if self.hole is not None:
            return self.hole
        if len(self.pockets) == 1:
            return (*self.pockets[0], 0.0)
        return None

    @property
    def tilt(self) -> float | None:
        """How far the charm hangs off upright (degrees), or None if it does not hang."""
        return None if self.pivot is None else hang_angle(self.pivot, self.centre)


def hang_angle(pivot: tuple[float, float, float], centre: tuple[float, float]) -> float:
    """How far a charm hangs off upright (degrees). An eyelet hangs from the top of its hole
    (x, y, r); a magnet turns about its middle (r = 0)."""
    x, y, r = pivot
    return math.degrees(math.atan2(abs(centre[0] - x), y + r - centre[1]))


def band_z(c: Charm) -> list[tuple[float, float]]:
    """(z0, z1) of every band in the print pose."""
    z = [(0.0, c.base_t)]
    for t in c.band_ts:
        z.append((z[-1][1], round(z[-1][1] + t, 6)))
    return z


def colour_changes(c: Charm) -> list[tuple[float, str]]:
    """The M600s: (print_z of the first layer of the band, new filament)."""
    return [(P.layer_top(z0), f) for (z0, _), f in zip(band_z(c)[1:], c.bands[1:])]


def bridges(c: Charm) -> list[float]:
    """print_z of the first layer over every ceiling the slicer must bridge: the roof of
    the pockets, or the underside of the tag over the channel."""
    if c.wear == "magnet":
        return [P.layer_top(P.POCKET_DEPTH)]
    if c.wear == "clip":
        return [P.layer_top(P.CLIP_Z)]
    return []


def _settle(name: str, what: str, x: float, place, clamp=lambda x: x, tol: float = 0.005):
    """Find where something placed at x lies over the centre of mass, although it moves the
    centre of mass itself. place(x) gives (slabs, extra). The secant method on
    g(x) = clamp(centre of mass) - x: the centre of mass moves nearly linearly with x, but
    it can move the other way, as much as x (a wide clip channel), and a plain repetition
    of x = centre of mass then swings from side to side. Returns x, the slabs, the centre of
    mass and extra."""
    def g(x: float):
        slabs, extra = place(x)
        cx, cy = relief.centre(slabs)
        return clamp(cx) - x, (x, slabs, (cx, cy), extra)

    g0, found = g(x)
    if abs(g0) < tol:
        return found
    x0, (x1, (g1, found)) = x, (x + g0, g(x + g0))
    for _ in range(20):
        if abs(g1) < tol:
            return found
        if g1 == g0:
            break
        x0, x1, g0 = x1, x1 - g1 * (x1 - x0) / (g1 - g0), g1
        g1, found = g(x1)
    raise ValueError(f"{name}: {what} does not settle over the centre of mass")


def _tab(c: Charm, body: BaseGeometry, x: float) -> tuple[BaseGeometry, Polygon, float]:
    """The tab (hole not yet cut), the hole and the height of the hole, above x. The ring
    sits on the highest point of the body under it; a neck joins it to the body."""
    outer = c.tab_r
    strip = body.intersection(box(x - outer, -1e4, x + outer, 1e4))
    if strip.is_empty:
        raise ValueError(f"{c.name}: nothing of the charm lies under the eyelet")
    top = strip.bounds[3]
    y = top + outer
    ring = Point(x, y).buffer(outer, quad_segs=32)
    neck = body.intersection(box(x - outer, top - outer, x + outer, top))
    return unary_union([ring, neck]).convex_hull, Point(x, y).buffer(c.hole_d / 2,
                                                                     quad_segs=32), y


def _eyelet(c: Charm, art, bands, z, upper) -> CharmLayout:
    def place(x: float):
        tab, hole, y = _tab(c, art.body, x)
        joined = polygons(unary_union([bands[0], tab]))
        if len(joined) != 1:
            raise ValueError(f"{c.name}: the eyelet does not join the body")
        b0 = relief.tidy(joined[0].difference(hole))
        return [(b0, *z[0]), *upper], (b0, (x, y, c.hole_d / 2))

    start = relief.centre([(bands[0], *z[0]), *upper])[0]
    _, _, com, (b0, hole) = _settle(c.name, "the eyelet", start, place)
    return CharmLayout(art, [b0, *bands[1:]], z, ((b0, *z[0]),), hole, (), None, com)


def _wall(body: BaseGeometry, x: float, y: float, r: float) -> float:
    """The plastic between a pocket and the edge of the body (negative: it breaks out)."""
    p = Point(x, y)
    return body.boundary.distance(p) - r if body.contains(p) else -r


def _pocket_slabs(c: Charm, b0: BaseGeometry, pts) -> list[Slab]:
    holes = unary_union([Point(p).buffer(c.pocket_d / 2, quad_segs=64) for p in pts])
    return [(relief.tidy(b0.difference(holes)), 0.0, P.POCKET_DEPTH),
            (b0, P.POCKET_DEPTH, c.base_t)]


def _magnet(c: Charm, art, bands, z, upper) -> CharmLayout:
    r = c.pocket_d / 2
    b0 = bands[0]
    if c.subject == "tag":  # two, a quarter of the width from each end
        x0, y0, x1, y1 = b0.bounds
        w, ym = x1 - x0, (y0 + y1) / 2
        pts = ((x0 + w / 4, ym), (x1 - w / 4, ym))
        slabs = _pocket_slabs(c, b0, pts) + upper
        com = relief.centre(slabs)
    elif c.drawing == "moka_pour":  # two, in the middle of the upper chamber and the boiler
        where = [art.parts[k] for k in ("chamber", "boiler")]
        pts = tuple((p.centroid.x, p.centroid.y) for p in where)
        for part, name, pt in zip(where, ("upper chamber", "boiler"), pts):
            if not part.contains(Point(pt).buffer(r)):
                raise ValueError(f"{c.name}: the {c.pocket_d:g} mm pocket does not fit inside "
                                 f"the {name}")
        slabs = _pocket_slabs(c, b0, pts) + upper
        com = relief.centre(slabs)
    else:  # one, in the upper chamber, over the centre of mass
        chamber = art.parts["chamber"]
        y = chamber.centroid.y

        def place(x: float):
            pts = ((x, y),)
            return _pocket_slabs(c, b0, pts) + upper, pts

        start = relief.centre([(b0, *z[0]), *upper])[0]
        _, slabs, com, pts = _settle(c.name, "the magnet", start, place)
        if not chamber.contains(Point(pts[0]).buffer(r)):
            raise ValueError(f"{c.name}: the {c.pocket_d:g} mm pocket does not fit inside the "
                             "upper chamber")
        if pts[0][1] <= com[1]:
            raise ValueError(f"{c.name}: the magnet does not lie above the centre of mass")
    for x, y in pts:
        wall = _wall(b0, x, y, r)
        if wall < P.MIN_POCKET_WALL - 1e-9:
            raise ValueError(f"{c.name}: the {c.pocket_d:g} mm pocket at x {x:.1f} leaves a wall "
                             f"of {max(wall, 0):.2f} mm, under {P.MIN_POCKET_WALL:.2f} mm: the "
                             f"{c.subject} is too small for the magnets (a tag grows with its "
                             "text and font_size)")
    if len(pts) == 2 and math.dist(*pts) < c.pocket_d + P.MIN_POCKET_WALL:
        raise ValueError(f"{c.name}: the two pockets are too close together")
    return CharmLayout(art, bands, z, tuple(slabs[:2]), None, tuple(pts), None, com)


def _strips(body: BaseGeometry, height: float, step: float = 0.2):
    """For every height of a horizontal strip `height` tall: (middle y, the x ranges that
    lie inside the body over the whole strip), from chords across the strip."""
    _, y0, _, y1 = body.bounds
    out = []
    ym = y0 + height / 2
    while ym <= y1 - height / 2 + 1e-9:
        ranges = None
        for t in range(9):
            y = ym - height / 2 + 1e-3 + t * (height - 2e-3) / 8
            seg = relief.chord(body, y)
            ranges = seg if ranges is None else [
                (max(a, c), min(b, d)) for a, b in ranges for c, d in seg
                if min(b, d) > max(a, c)]
        out.append((ym, ranges or []))
        ym = round(ym + step, 6)
    return out


Bar = tuple[float, float, str]  # (middle y, slit, the wall it joins: "left" | "right")


def clip_slabs(b0: BaseGeometry, x: float, cw: float, bars: tuple[Bar, ...],
               top: float) -> tuple[list[Slab], Clip]:
    """Band 0 of a clip, from the bed up: the floor (the walls and the bars), the walls
    beside the channel, then the whole body up to `top`. The channel is `cw` wide, centred
    on x, and runs across the whole body. Each bar is BAR_W high: it joins one wall and
    stops its slit short of the other. The clip gauge uses it too."""
    _, y0, _, y1 = b0.bounds
    x0, x1 = x - cw / 2, x + cw / 2
    channel = box(x0, y0 - 1, x1, y1 + 1)
    walls = relief.tidy(b0.difference(channel))
    rects = tuple((x0 - P.OVERLAP, x1 - slit) if side == "left" else (x0 + slit, x1 + P.OVERLAP)
                  for _, slit, side in bars)
    rects = tuple((a, b, ym - P.BAR_W / 2, ym + P.BAR_W / 2)
                  for (a, b), (ym, _, _) in zip(rects, bars))
    floor = relief.tidy(unary_union([walls, *(box(a, c, b, d) for a, b, c, d in rects)]))
    slabs = [(floor, 0.0, P.BAR_T), (walls, P.BAR_T, P.CLIP_Z), (b0, P.CLIP_Z, top)]
    return slabs, Clip((x0, x1), rects, walls)


# the shortest backing plate: its two bars PLATE_EDGE from its edges, and BAR_W between
# them, where the ribbon turns flat again
PLATE_MIN_H = 2 * (P.PLATE_EDGE + P.BAR_W) + P.BAR_W


def plate_for(body: BaseGeometry, x: float, need: float, above: float = 0.0,
              below: float = 0.0) -> Polygon:
    """The backing plate of a clip over x: `need` wide, PLATE_MARGIN above and below the body
    where it crosses that strip, and at least PLATE_MIN_H tall (centred on the strip); then
    `above` and `below` mm longer at the top and the bottom (room for its texts)."""
    strip = body.intersection(box(x - need / 2, -1e4, x + need / 2, 1e4))
    if strip.is_empty:
        raise ValueError("nothing of the charm lies under the backing plate")
    _, y0, _, y1 = strip.bounds
    y0, y1 = y0 - P.PLATE_MARGIN, y1 + P.PLATE_MARGIN
    grow = max(0.0, PLATE_MIN_H - (y1 - y0)) / 2
    return rounded_rect(x - need / 2, y0 - grow - below, x + need / 2, y1 + grow + above,
                        P.PLATE_CORNER)


# --- texts on the backing plate (moka_pour_rh1_clip) --------------------------------------
GROW_MAX = 20.0  # mm: the most the texts may lengthen the plate, at the top or the bottom
PLATE_ROUNDS = 6  # settle, fit the texts again where the plate went, settle again...


@dataclass(frozen=True)
class PlateText:
    """A text of the plate at the origin: its raw letters, and the bands it raises (bands 1
    up to its colour's), after the band cleanup."""

    pos: str  # top | bottom
    text: str
    colour: str
    raw: BaseGeometry
    raised: tuple[BaseGeometry, ...]


@cache
def _plate_letters(name: str, bands: tuple[str, ...], pos: str, text: str, colour: str,
                   size: float, forced: bool) -> PlateText:
    """A text of the plate through the band cleanup on its own: up to its colour's band (a
    green text raises the red band too). The cleanup does not depend on where the plate
    goes, so the settling only moves the result. The letters must come through it as the
    stream's do (letters_damage), on every band they raise."""
    at = f"plate_font {size:g} mm" if forced else f"{size:g} mm (the largest that fits the plate)"
    problems = size_problems((text,), size)
    if problems:  # before colour_bands, which would quietly repair the letters
        raise ValueError(f"{name}: at {at} {text!r} is too small: {'; '.join(problems)}. It "
                         f"prints from {limits((text,)).size:g} mm")
    raw = text_geometry((text,), size)
    x0, y0, x1, y1 = raw.bounds
    k = bands.index(colour)  # validate(): not 0, the body
    body = box(x0 - 2, y0 - 2, x1 + 2, y1 + 2)
    out = relief.colour_bands(name, bands[:k + 1], body, {colour: raw})
    for j in range(1, k + 1):
        why = letters_damage(out[j], raw)
        if why is not None:
            raise ValueError(f"{name}: at {at} the band cleanup changes {text!r}: {why}")
    return PlateText(pos, text, colour, raw, tuple(out[1:]))


def _anchor(pos: str, bounds, plate_bounds) -> tuple[float, float]:
    """How far to move letters with these bounds onto the plate: the top text into its top
    right corner, the bottom one to the middle of its bottom edge, PLATE_TEXT_MARGIN in."""
    x0, y0, x1, y1 = bounds
    px0, py0, px1, py1 = plate_bounds
    m = P.PLATE_TEXT_MARGIN
    if pos == "top":
        return px1 - m - x1, py1 - m - y1
    return (px0 + px1) / 2 - (x0 + x1) / 2, py0 + m - y0


Fit = tuple[float, float, float]  # the texts' font size, the plate's growth above and below


def _plate_fit(c: Charm, art, x: float, need: float, texts, moka,
               size: float | None = None) -> Fit:
    """The font size of the plate's texts, and how far they lengthen the plate, for the plate
    over x. Each text's box lies inside the plate, PLATE_TEXT_MARGIN in, and STREAM_CLEAR
    from the moka and from the other text. The size: `size`, plate_font, or the largest, at
    0.1 mm steps, at which the top text fits its corner, at most POUR_FONT and as wide as
    the plate allows (that width without a top text). Only if the corner is too small even
    for the smallest size that prints both texts (a wide top text such as 'RH1RH1'), or for
    a forced size, the plate grows at the top, just enough for that size.
    Then it grows at the bottom, as little as the bottom text needs. All at 0.1 mm steps."""
    clear, m = artwork.STREAM_CLEAR - 1e-9, P.PLATE_TEXT_MARGIN
    px0, py0, px1, py1 = plate_for(art.body, x, need).bounds
    words = {pos: t for pos, t, _ in texts}
    em = {pos: text_geometry((t,), 1.0) for pos, t in words.items()}
    if any(g.is_empty for g in em.values()):
        raise ValueError(f"{c.name}: a text on the plate draws nothing: "
                         f"{[t for pos, t in words.items() if em[pos].is_empty]}")
    em = {pos: g.bounds for pos, g in em.items()}
    floor = {pos: limits((t,)).size for pos, t in words.items()}
    lowest = max(floor.values())  # one size for both
    sets_it = words[max(floor, key=floor.get)]
    inner_w = px1 - px0 - 2 * m
    widest = min(math.floor(inner_w / (e[2] - e[0]) * 10 + 1e-6) / 10 for e in em.values())

    def boxed(pos: str, s: float, above: float, below: float) -> Polygon:
        x0, y0, x1, y1 = (v * s for v in em[pos])
        dx, dy = _anchor(pos, (x0, y0, x1, y1), (px0, py0 - below, px1, py1 + above))
        return box(x0 + dx, y0 + dy, x1 + dx, y1 + dy)

    def fits(pos: str, s: float, above: float, below: float) -> bool:
        b = boxed(pos, s, above, below)
        bx0, by0, bx1, by1 = b.bounds
        inside = (bx0 >= px0 + m - 1e-9 and bx1 <= px1 - m + 1e-9
                  and by0 >= py0 - below + m - 1e-9 and by1 <= py1 + above - m + 1e-9)
        apart = pos == "top" or "top" not in em or b.distance(
            boxed("top", s, above, below)) >= clear
        return inside and apart and b.distance(moka) >= clear

    def grown(pos: str, s: float, above: float) -> float | None:
        steps = (k / 10 for k in range(int(GROW_MAX * 10) + 1))
        if pos == "top":
            return next((a for a in steps if fits("top", s, a, 0.0)), None)
        return next((b for b in steps if fits("bottom", s, above, b)), None)

    forced = size or c.plate_font
    if forced:
        if forced > widest:
            raise ValueError(f"{c.name}: at {forced:g} mm the texts on the plate are wider than "
                             f"its {inner_w:.1f} mm inside the margins: at most {widest:g} mm")
        sizes = [forced]
    else:
        cap = min(artwork.POUR_FONT, widest)
        if cap < lowest:
            raise ValueError(f"{c.name}: {sets_it!r} prints from {lowest:g} mm, but the plate "
                             f"has room for the texts only up to {widest:g} mm across its "
                             f"{inner_w:.1f} mm")
        sizes = [round(cap - 0.1 * k, 1) for k in range(round((cap - lowest) * 10) + 1)]
    above = 0.0
    if "top" in em:
        size = next((s for s in sizes if fits("top", s, 0.0, 0.0)), None)
        if size is None:  # too small a corner: the plate grows at the top
            size, above = sizes[-1], grown("top", sizes[-1], 0.0)
            if above is None:
                raise ValueError(f"{c.name}: {words['top']!r} does not fit the top right corner "
                                 f"of the backing plate at {size:g} mm, even {GROW_MAX:g} mm "
                                 "longer")
    else:
        size = sizes[0]
    below = 0.0
    if "bottom" in em:
        below = grown("bottom", size, above)
        if below is None:
            raise ValueError(f"{c.name}: {words['bottom']!r} does not fit at the bottom of the "
                             f"backing plate at {size:g} mm, even {GROW_MAX:g} mm longer")
    return size, above, below


def _plate_clip(c: Charm, art, bands, z, upper) -> CharmLayout:
    """A clip on a backing plate (plate_for). The plate and the channel move together: the
    plate is exactly the channel and its walls wide. Two bars, PLATE_EDGE from the top and
    the bottom of the plate: the top one joins the left wall (SLIT), the bottom one the right
    wall (SLIT_WIDE). The ribbon goes into the top bar first. The plate's texts (plate_top,
    plate_bottom) rise in their colours' bands (_plate_fit, _plate_letters)."""
    cw = c.lanyard_w + P.CHANNEL_EXTRA
    need = cw + 2 * P.RISER_W

    def placing(fit: Fit, letters: list[PlateText]):
        _, above, below = fit

        def place(x: float):
            try:
                plate = plate_for(art.body, x, need, above, below)
            except ValueError as e:
                raise ValueError(f"{c.name}: {e}") from None
            # band 0 as colour_bands makes it, of the body with the plate, and as moka() fills
            # the body: the holes under WINDOW_MIN where the plate meets the outline go
            joined = polygons(relief.opening(unary_union([art.body, plate]), P.MIN_STROKE / 2))
            if len(joined) != 1:
                raise ValueError(f"{c.name}: the backing plate does not join the body")
            b0 = Polygon(joined[0].exterior, [h for h in joined[0].interiors
                                              if Polygon(h).area >= artwork.WINDOW_MIN])
            _, py0, _, py1 = plate.bounds
            bars = ((py1 - P.PLATE_EDGE - P.BAR_W / 2, P.SLIT, "left"),
                    (py0 + P.PLATE_EDGE + P.BAR_W / 2, P.SLIT_WIDE, "right"))
            slabs0, clip = clip_slabs(b0, x, cw, bars, c.base_t)
            # the letters lie STREAM_CLEAR from the moka: as slabs of their own they weigh the
            # same as joined to the bands, which happens once, after the settling
            moved = [(t, *_anchor(t.pos, t.raw.bounds, plate.bounds)) for t in letters]
            extra = [(affinity.translate(g, dx, dy), *z[j + 1])
                     for t, dx, dy in moved for j, g in enumerate(t.raised)]
            return slabs0 + upper + extra, (b0, replace(clip, plate=plate), moved)
        return place

    x = relief.centre([(bands[0], *z[0]), *upper])[0]
    texts = [(pos, t, colour) for pos, t, colour in
             zip(("top", "bottom"), (c.plate_top, c.plate_bottom), PLATE_COLOURS) if t]
    if not texts:
        _, slabs, com, (b0, clip, _) = _settle(c.name, "the clip", x, placing((0, 0, 0), []))
        return CharmLayout(art, [b0, *bands[1:]], z, tuple(slabs[:3]), None, (), clip, com)
    # the size and the growth stay fixed while the plate settles (steps would make the centre
    # of mass jump); then they are fitted again where the plate went, until they hold there.
    # If they swing between two, the smaller size, fitted where the plate is, ends it.
    moka = unary_union([art.parts["pot"], art.parts["stream"]])
    fit = _plate_fit(c, art, x, need, texts, moka)
    tried = set()
    for _ in range(PLATE_ROUNDS):
        tried.add(fit)
        letters = [_plate_letters(c.name, c.bands, pos, t, colour, fit[0], bool(c.plate_font))
                   for pos, t, colour in texts]
        x, slabs, com, (b0, clip, moved) = _settle(c.name, "the clip", x,
                                                   placing(fit, letters))
        again = _plate_fit(c, art, x, need, texts, moka)
        if again != fit and again in tried:
            again = _plate_fit(c, art, x, need, texts, moka, min(fit[0], again[0]))
        if again == fit:
            break
        fit = again
    else:
        raise ValueError(f"{c.name}: the texts on the backing plate do not settle")
    ups, placed = list(bands[1:]), []
    for t, dx, dy in moved:
        for j, g in enumerate(t.raised):  # its colour's band and those below it
            ups[j] = unary_union([ups[j], affinity.translate(g, dx, dy)])
        placed.append((t.text, t.colour, affinity.translate(t.raw, dx, dy)))
    clip = replace(clip, letters=tuple(placed), font=fit[0])
    _check_plate_texts(c, clip, moka)
    return CharmLayout(art, [b0, *ups], z, tuple(slabs[:3]), None, (), clip, com)


def _check_plate_texts(c: Charm, clip: Clip, moka: BaseGeometry) -> None:
    """The placed letters lie on the plate, PLATE_TEXT_MARGIN in, STREAM_CLEAR from the moka
    and from each other (_plate_fit fits their boxes: this checks the result)."""
    inner = clip.plate.buffer(-P.PLATE_TEXT_MARGIN + 1e-6, join_style="mitre")
    clear = artwork.STREAM_CLEAR - 1e-6
    for k, (t, _, g) in enumerate(clip.letters):
        if not inner.contains(g) or g.distance(moka) < clear or any(
                g.distance(o) < clear for _, _, o in clip.letters[k + 1:]):
            raise ValueError(f"{c.name}: {t!r} does not lie clear on the backing plate")


def _clip(c: Charm, art, bands, z, upper) -> CharmLayout:
    if art.plate:
        return _plate_clip(c, art, bands, z, upper)
    cw = c.lanyard_w + P.CHANNEL_EXTRA
    need = cw + 2 * P.RISER_W
    b0 = bands[0]
    _, y0, _, y1 = b0.bounds
    middle = (y0 + y1) / 2
    strips = _strips(b0, P.BAR_W)
    widest = max((b - a for _, rs in strips for a, b in rs), default=0.0)
    fits = [(ym, a, b) for ym, rs in strips for a, b in rs if b - a >= need - 1e-9]
    if not fits:
        raise ValueError(
            f"{c.name}: too narrow for a lanyard clip. The {cw:g} mm channel (a {c.lanyard_w:g} "
            f"mm lanyard) and its two {P.RISER_W:g} mm walls need {need:g} mm across the "
            f"{P.BAR_W:g} mm bar, but the {c.subject} is at most {widest:.1f} mm wide there: "
            "wear it with an eyelet or a magnet")
    ym, lo, hi = min(fits, key=lambda f: abs(f[0] - middle))  # the bar near the middle

    def clamp(x: float) -> float:
        return min(max(x, lo + need / 2), hi - need / 2)

    def place(x: float):
        slabs0, clip = clip_slabs(b0, x, cw, ((ym, P.SLIT, "left"),), c.base_t)
        return slabs0 + upper, clip

    start = clamp(relief.centre([(b0, *z[0]), *upper])[0])
    x, slabs, com, clip = _settle(c.name, "the clip", start, place, clamp)
    if abs(x - com[0]) > 0.05:  # the clamp held it: the tag would hang crooked
        raise ValueError(f"{c.name}: the {cw:g} mm channel cannot lie over the centre of mass "
                         f"(it would be {abs(x - com[0]):.1f} mm beside it, with its walls at "
                         "the ends of the tag): make lanyard_w smaller")
    return CharmLayout(art, bands, z, tuple(slabs[:3]), None, (), clip, com)


def text_damage(art: artwork.Artwork, band: BaseGeometry) -> str | None:
    """How the band cleanup changed the letters (None: only their corners). `band` is the
    band of the text's colour."""
    # where only the letters are: the tag's white middle clear of the end bands, the moka's
    # stream clear of the pot (the spout, the lid, the knob and the handle are red too)
    return letters_damage(band.intersection(art.parts["text_zone"]), art.text)


def letters_damage(raised: BaseGeometry, raw: BaseGeometry) -> str | None:
    """How the raised letters differ from the raw ones (None: only at their corners)."""
    if not same_features(raised, raw, 1e-3):
        return "it changes the pieces or holes of the letters"
    lost = raw.difference(raised)
    largest = max((p.area for p in polygons(lost) if not p.buffer(-SLIVER).is_empty),
                  default=0.0)
    if largest > LOST_MAX:
        return f"it removes {largest:.2f} mm2 of a letter (a stroke thinner than a line)"
    if lost.area > LOST_SHARE * raw.area:
        return f"it removes {lost.area / raw.area:.1%} of the letters"
    filled = max((p.area for p in polygons(raised.difference(raw))), default=0.0)
    if filled > relief.SPECK:
        return f"it fills {filled:.2f} mm2 between the letters"
    return None


def _artwork_and_bands(c: Charm) -> tuple[artwork.Artwork, list[BaseGeometry]]:
    """The drawing and its printable bands. With a text (the tag, the moka that pours), the
    letters must come through the band cleanup (text_damage): an automatic font size goes up
    0.1 mm at a time until they do (a stroke that keeps the topology when it vanishes, such
    as the foot of an L, can need more than the text's own limits), past a size too small for
    a bent line (a short stream bends tighter as the letters grow); a forced font_size that
    fails is an error."""
    if c.drawing not in TEXTS:  # the plain moka (it ignores a text)
        art = artwork.make(c)
        return art, relief.colour_bands(c.name, c.bands, art.body, art.regions)
    text_band = c.bands.index("red")
    start = c.font_size or artwork.auto_size(c)[0]
    cause = ""  # why the size before did not print, for size_bound
    for k in range(1 if c.font_size else P.SIZE_STEPS):
        size = c.font_size or round(start + 0.1 * k, 1)  # a forced size stays as it is
        try:
            art = artwork.make(c, size)
        except artwork.TooSmall as e:
            if c.font_size:
                raise
            why, cause = e.reason, f"the bent text on its stream, too small at {size:g} mm"
            continue
        bands = relief.colour_bands(c.name, c.bands, art.body, art.regions)
        why = text_damage(art, bands[text_band])
        if why is None:
            if k:
                art = replace(art, size_bound=cause)
            return art, bands
        cause = f"the band cleanup, which changes the letters at {size:g} mm"
        if c.font_size:
            raise ValueError(f"{c.name}: at font_size {size:g} mm the band cleanup changes the "
                             f"letters: {why}. Make font_size larger")
    raise ValueError(f"{c.name}: no automatic font size from {start:g} to {size:g} mm prints the "
                     f"letters (at {size:g} mm: {why}); try another text or force a font_size")


@cache
def layout(c: Charm) -> CharmLayout:
    c.validate()
    art, bands = _artwork_and_bands(c)
    z = band_z(c)
    upper = [(b, z0, z1) for b, (z0, z1) in zip(bands[1:], z[1:])]
    return {"eyelet": _eyelet, "magnet": _magnet, "clip": _clip}[c.wear](c, art, bands, z, upper)


# --- solids ---------------------------------------------------------------------------------
@cache
def band_parts(c: Charm) -> tuple[Part, ...]:
    """One solid per band, in the print pose (lying, front face up)."""
    lay = layout(c)
    body = relief.stack(list(lay.slabs0))
    return (body, *(relief.slab(relief.inset(g, k), z0, z1)
                    for k, (g, (z0, z1)) in enumerate(zip(lay.bands[1:], lay.z[1:]), start=1)))


@cache
def make_charm(c: Charm) -> Part:
    """The whole charm in the print pose, as one solid."""
    return relief.fuse(band_parts(c))


def standing(part: Part) -> Part:
    """Print pose -> worn: the front faces -y, the charm's y points up (+z)."""
    return Rot(90, 0, 0) * part


def coloured(c: Charm, stand: bool = True) -> list[tuple[Part, str]]:
    """(band solid, filament) pairs: what each band looks like once printed."""
    return [(standing(p) if stand else p, f) for p, f in zip(band_parts(c), c.bands)]


def mass_centre(c: Charm) -> tuple[float, float]:
    """x and y of the centre of mass, measured on the solids (layout() places the eyelet and
    the pockets with the 2D centre of the slabs; this checks it)."""
    total = mx = my = 0.0
    for part in band_parts(c):
        v, m = part.volume, part.center(CenterOf.MASS)
        total, mx, my = total + v, mx + v * m.X, my + v * m.Y
    return mx / total, my / total
