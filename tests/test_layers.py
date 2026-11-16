"""Printability on a Prusa MK4: 0.4 mm nozzle, PrusaSlicer "0.20mm STRUCTURAL" profile."""

import numpy as np
import pytest
from build123d import GeomType
from conftest import CHARMS, NAMES, charm_id

from rh1charms import params as P
from rh1charms import relief, wear
from rh1charms.charms import DEFAULT_BANDS, VARIANTS


def off_grid_faces(part) -> list[float]:
    """Heights of flat horizontal faces that do not sit on a layer boundary."""
    heights = []
    for face in part.faces():
        if face.geom_type == GeomType.PLANE and abs(abs(face.normal_at().Z) - 1) < 1e-6:
            z = face.center().Z
            if not P.on_grid(z):
                heights.append(round(z, 3))
    return sorted(set(heights))


@pytest.mark.parametrize("name", NAMES)
def test_flat_faces_sit_on_layer_boundaries(parts, name):
    assert off_grid_faces(parts[name]) == []


def test_profile_assumptions():
    assert P.FIRST_LAYER == P.LAYER == 0.2
    assert P.LINE_W == 0.45 and P.NOZZLE == 0.4
    assert P.BASE_T == pytest.approx(1.2) and P.BAND_T == pytest.approx(0.8)
    assert P.POCKET_DEPTH == pytest.approx(2.2) and P.ROOF_T == pytest.approx(0.6)
    assert P.MAGNET_BODY_T == pytest.approx(2.8) and P.COUNTER_T == pytest.approx(3.0)
    assert P.CLIP_Z == pytest.approx(2.8) and P.COUNTER_FLOOR == pytest.approx(0.8)
    for value in (P.BASE_T, P.BAND_T, P.POCKET_DEPTH, P.ROOF_T, P.MAGNET_BODY_T, P.COUNTER_T,
                  P.COUNTER_FLOOR, P.BAR_T, P.RIBBON_GAP, P.CLIP_Z):
        assert P.on_grid(value)


@pytest.mark.parametrize("c", CHARMS, ids=charm_id)
def test_band_order(c):
    """White, then red, then green (then black): dark over white covers well, and red right
    above white gives the raised letters clean red walls."""
    assert c.bands == DEFAULT_BANDS[c.drawing]
    assert c.bands[:3] == ("white", "red", "green")
    assert [f for _, f in wear.colour_changes(c)] == list(c.bands[1:])


# the M600 heights of every default variant (print_z of the first layer of each band)
# (the moka that pours: a 1.2 mm red band)
M600 = {"eyelet": {"tag": [1.4, 2.2], "moka": [1.4, 2.2, 3.0], "moka_pour": [1.4, 2.6]},
        "magnet": {"tag": [3.0, 3.8], "moka": [3.0, 3.8, 4.6], "moka_pour": [3.0, 4.2]},
        "clip": {"tag": [4.2, 5.0], "moka_pour": [4.2, 5.4]}}


@pytest.mark.parametrize("c", CHARMS, ids=charm_id)
def test_colour_changes_come_before_each_band(c):
    for (z0, z1), (print_z, colour), name in zip(wear.band_z(c)[1:], wear.colour_changes(c),
                                                 c.bands[1:]):
        assert P.on_grid(z0) and P.on_grid(z1)
        assert print_z == pytest.approx(z0 + P.LAYER) and colour == name
    assert [z for z, _ in wear.colour_changes(c)] == pytest.approx(M600[c.wear][c.drawing])


@pytest.mark.parametrize("c", CHARMS, ids=charm_id)
def test_bands_are_nested(c):
    assert relief.is_nested(wear.layout(c).bands)


@pytest.mark.parametrize("c", CHARMS, ids=charm_id)
def test_every_band_shows(c):
    """Every band shows from the front: something of it is not covered by the next one."""
    bands = wear.layout(c).bands
    for k in range(len(bands) - 1):
        assert bands[k].difference(bands[k + 1]).area > 1.0, f"band {k} ({c.bands[k]})"
    assert bands[-1].area > 1.0


def _thin_fraction(geom, min_width: float, px_per_mm: float = 20.0) -> float:
    """Share of the area in parts thinner than `min_width` (morphological opening)."""
    from scipy import ndimage

    from rh1charms.render import mask as raster

    if geom.is_empty:
        return 0.0
    m = np.array(raster(geom, geom.bounds, px_per_mm, pad=20), dtype=bool)
    if not m.any():
        return 0.0
    r = round(min_width / 2 * px_per_mm)
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    opened = ndimage.binary_opening(m, structure=xx**2 + yy**2 <= r * r)
    return 1 - opened.sum() / m.sum()


@pytest.mark.parametrize("c", CHARMS, ids=charm_id)
def test_no_lone_slivers(c):
    """Every piece of a raised band survives an opening by a line."""
    for k, band in enumerate(wear.layout(c).bands[1:], start=1):
        lone = [round(p.area, 3) for p in relief.polygons(band)
                if relief.opening(p, 0.95 * P.MIN_STROKE / 2).is_empty]
        assert lone == [], f"band {k} ({c.bands[k]})"


@pytest.mark.parametrize("c", CHARMS, ids=charm_id)
def test_raised_strokes_are_printable(c):
    # Arachne drops walls thinner than min_bead_width (85 % of a line). Corners always lose
    # a little in the opening, so allow 1.5 % of the area.
    for k, band in enumerate(wear.layout(c).bands[1:], start=1):
        assert _thin_fraction(band, P.MIN_STROKE) < 0.015, f"band {k} ({c.bands[k]})"


@pytest.mark.parametrize("c", CHARMS, ids=charm_id)
def test_grooves_stay_open(c):
    """What shows of a lower colour between raised areas is at least one line wide (the
    moka's facet grooves and the gap under its lid are 0.6 mm)."""
    bands = wear.layout(c).bands
    for k in range(1, len(bands)):
        lower = relief.opening(bands[k - 1].difference(bands[k]), relief.HAIR)
        assert _thin_fraction(lower, P.MIN_GAP) < 0.03, f"under band {k} ({c.bands[k]})"


def test_moka_facet_grooves_show_white():
    lay = wear.layout(VARIANTS["moka_eyelet"])
    grooves = lay.art.parts["grooves"]
    assert len(relief.polygons(grooves)) == 4
    # inside the grooves, nothing rises above the body: they show white
    assert lay.bands[1].intersection(grooves.buffer(-0.1)).area < 1e-3


def _layer_sections(part):
    """Cross-sections (shapely polygons) at the middle of every layer."""
    import trimesh

    verts, tris = part.tessellate(0.02, 0.2)
    mesh = trimesh.Trimesh([[v.X, v.Y, v.Z] for v in verts], tris)
    top = part.bounding_box().max.Z
    heights = np.arange(P.LAYER / 2, top, P.LAYER)
    paths = mesh.section_multiplane([0, 0, 0], [0, 0, 1], heights)
    return [list(p.polygons_full) if p is not None else [] for p in paths]


@pytest.mark.parametrize("name", NAMES)
def test_no_floating_islands(parts, name):
    """Every island of every layer rests on the layer below (nothing starts in mid-air: the
    pocket roofs and the clip's ceiling are bridges anchored on their walls)."""
    from shapely.ops import unary_union

    layers = _layer_sections(parts[name])
    for k in range(1, len(layers)):
        below = unary_union(layers[k - 1]) if layers[k - 1] else None
        for poly in layers[k]:
            if poly.area < 0.05:  # tessellation crumbs
                continue
            assert below is not None and poly.intersection(below).area > 0.01, (
                f"island of {poly.area:.2f} mm2 at z={(k + 0.5) * P.LAYER:.1f}")
