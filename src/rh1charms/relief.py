"""From colour regions to printable colour bands, and from bands to build123d solids.

All the 2D work happens in shapely (fast and robust): the bands, the cleanup that makes
every band printable with 0.45 mm lines, the tab, the pockets and the channel. build123d
only extrudes the finished footprints. Most of this module comes from the owner's 3d-linux
project (relief.py), where it builds the standees.

Frame: x along the charm, y up (the charm as worn), front face up (+z) in the print pose,
z = 0 on the bed.
"""

import math

import shapely
from build123d import Face, Part, Pos, Wire, extrude
from shapely.geometry import LineString, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from . import params as P

CRUMB = 0.05  # mm2: smaller pieces of a band are left out
SPECK = 0.3  # mm2: thinner-than-a-line gaps this small are filled, not widened
HAIR = 0.025  # mm: cracks between two bands narrower than 2 * HAIR are boolean noise
SIMPLIFY = 0.01  # mm: polyline tolerance of the colour regions
# Corners a fraction of a micron apart give edges that short in the solid, and zero-area
# triangles in the STL. So every corner of a solid lies on a GRID (mm), and band k's solid
# is k * INSET (mm) inside the band's edge: a band's edge never touches the edge of the band
# below, and the boolean has no edges to intersect where the two meet.
GRID = 1e-3
INSET = 2 * GRID

Slab = tuple[BaseGeometry, float, float]  # footprint, z0, z1


def polygons(geom: BaseGeometry) -> list[Polygon]:
    """Every polygon inside a geometry (collections included)."""
    if geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    return [p for g in getattr(geom, "geoms", []) for p in polygons(g)]


def tidy(geom: BaseGeometry) -> BaseGeometry:
    """Remove zero-width spikes and cracks, and pieces and holes smaller than CRUMB: the
    leftovers of the booleans that give degenerate faces."""
    eps = 1e-3
    geom = geom.buffer(eps, join_style="mitre").buffer(-2 * eps, join_style="mitre").buffer(
        eps, join_style="mitre")
    keep = [Polygon(p.exterior, [h for h in p.interiors if Polygon(h).area >= CRUMB])
            for p in polygons(geom) if p.area >= CRUMB]
    return unary_union(keep) if keep else Polygon()


def _clean(geom: BaseGeometry) -> BaseGeometry:
    """`tidy`, then fewer points (the simplification moves edges by up to SIMPLIFY)."""
    return tidy(geom).simplify(SIMPLIFY)


def opening(geom: BaseGeometry, r: float) -> BaseGeometry:
    """Remove every part thinner than 2 r (morphological opening). GEOS can, rarely, return
    a buffer whose rings cross; such a result is repaired."""
    if geom.is_empty:
        return geom
    out = geom.buffer(-r, join_style="round").buffer(r, join_style="round")
    return out if out.is_valid else shapely.make_valid(out, method="structure",
                                                       keep_collapsed=False)


def _thin(geom: BaseGeometry, r: float) -> BaseGeometry:
    """The parts of a geometry narrower than 2 r."""
    return geom.difference(opening(geom, r)) if not geom.is_empty else geom


def chord(geom: BaseGeometry, y: float) -> list[tuple[float, float]]:
    """The x ranges where a horizontal line at height y crosses a geometry, left to right."""
    x0, _, x1, _ = geom.bounds
    cut = geom.intersection(LineString([(x0 - 1, y), (x1 + 1, y)]))
    found = [g for g in getattr(cut, "geoms", [cut]) if g.geom_type == "LineString"]
    return sorted((g.bounds[0], g.bounds[2]) for g in found if g.length > 0)


def colour_bands(name: str, bands: tuple[str, ...], body: BaseGeometry,
                 regions: dict[str, BaseGeometry]) -> list[BaseGeometry]:
    """The printable footprint of every band over a body: nested, with raised parts at least
    MIN_STROKE wide and grooves at least MIN_GAP wide (as in 3d-linux)."""
    out = [opening(body, P.MIN_STROKE / 2)]
    for k in range(1, len(bands)):
        wanted = unary_union([regions[f] for f in bands[k:] if f in regions])
        fk = opening(wanted.intersection(out[k - 1]), P.MIN_STROKE / 2)
        # widen grooves that would close up; only the lower colours count
        thin = _thin(out[k - 1].difference(wanted), P.MIN_GAP / 2)
        # slivers between neighbouring regions: fill them, but only where they touch the
        # band (a lone speck would become a raised sliver of its own)
        specks = [p for p in polygons(thin) if p.area < SPECK and p.distance(fk) < 1e-6]
        grooves = [p for p in polygons(thin) if p.area >= SPECK]
        if specks:
            fk = unary_union([fk, *specks]).intersection(out[k - 1])
        if grooves:
            fk = fk.difference(unary_union(grooves).buffer(P.MIN_GAP / 2))
        fk = _clean(opening(fk, P.MIN_STROKE / 2)).intersection(out[k - 1])
        # opening and simplifying move shared edges by a hair: fill the cracks of the lower
        # colour narrower than 2 * HAIR, or they show as thin rings
        cracks = _thin(out[k - 1].difference(fk), HAIR)
        fk = tidy(unary_union([fk, cracks]).intersection(out[k - 1]))
        if fk.is_empty:
            raise ValueError(f"{name}: band {k} ({bands[k]}) is empty")
        out.append(fk)
    return out


def is_nested(bands: list[BaseGeometry]) -> bool:
    """Every band rests on the band below it (no part of a band hangs in the air)."""
    return all(bands[k].difference(bands[k - 1]).area < 1e-3 for k in range(1, len(bands)))


def centre(slabs: list[Slab]) -> tuple[float, float]:
    """x and y of the centre of mass of stacked slabs (area times thickness)."""
    weights = [(g.area * (z1 - z0), g.centroid) for g, z0, z1 in slabs if not g.is_empty]
    total = sum(w for w, _ in weights)
    return (sum(w * c.x for w, c in weights) / total, sum(w * c.y for w, c in weights) / total)


def _wire(coords) -> Wire | None:
    """A closed polygon wire, without the repeated points OCCT cannot join (on the GRID,
    two different points are at least GRID apart)."""
    pts = []
    for x, y in list(coords)[:-1]:
        if not pts or math.dist((x, y), pts[-1]) > GRID / 2:
            pts.append((x, y))
    while len(pts) > 1 and math.dist(pts[0], pts[-1]) <= GRID / 2:
        pts.pop()
    if len(pts) < 3 or Polygon(pts).area < 1e-4:
        return None
    return Wire.make_polygon([(x, y, 0) for x, y in pts], close=True)


def _faces(geom: BaseGeometry) -> list[Face]:
    """The faces of a footprint, with every corner on the GRID and every outline turned
    counter-clockwise (holes clockwise): build123d extrudes a clockwise face downwards.
    Some input polygons come clockwise (the moka's handle)."""
    faces = []
    snapped = shapely.orient_polygons(shapely.set_precision(geom, GRID), exterior_cw=False)
    for p in polygons(snapped):
        outer = _wire(p.exterior.coords)
        if outer is None:
            continue
        holes = [w for w in (_wire(h.coords) for h in p.interiors) if w is not None]
        faces.append(Face(outer, holes))
    return faces


def inset(band: BaseGeometry, k: int) -> BaseGeometry:
    """The footprint of band k's solid: k * INSET inside the band's edge (see INSET)."""
    return band.buffer(-k * INSET, join_style="mitre") if k else band


def slab(geom: BaseGeometry, z0: float, z1: float) -> Part:
    """A footprint extruded from z0 to z1: one solid per polygon, not joined (the polygons
    of a footprint never overlap; `fuse` joins everything in one go)."""
    # the faces are counter-clockwise, and the direction is given anyway (3d-linux gotcha)
    solids = [Pos(0, 0, z0) * extrude(f, z1 - z0, dir=(0, 0, 1)) for f in _faces(geom)]
    if not solids:
        raise ValueError(f"nothing to extrude between z {z0} and {z1}")
    return solids[0] if len(solids) == 1 else Part(solids)


def stack(slabs: list[Slab]) -> Part:
    """Slabs of one colour, one on top of the other (band 0 with its pockets or channel)."""
    parts = [slab(g, z0, z1) for g, z0, z1 in slabs]
    return parts[0] if len(parts) == 1 else fuse(parts)


def fuse(parts) -> Part:
    """One solid from stacked parts, in a single boolean. The parts may be cached: they are
    not changed."""
    part = Pos() * parts[0]  # a copy: clean() works in place
    return (part + list(parts[1:])).clean()
