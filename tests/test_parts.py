"""Valid, watertight single solids (the clip gauge: one per piece), built the right way
up."""

import numpy as np
import pytest
from conftest import CHARMS, NAMES
from scipy.spatial import cKDTree
from shapely.geometry import LinearRing

from rh1charms import artwork, relief, wear
from rh1charms.charms import VARIANTS
from rh1charms.export import bodies, check, mesh_problems


@pytest.mark.parametrize("name", NAMES)
def test_part_is_printable(parts, name):
    assert check(parts[name], bodies(name)) == []


@pytest.mark.parametrize("name", NAMES)
def test_stl_mesh_is_watertight(parts, name):
    assert mesh_problems(parts[name]) == []


@pytest.mark.parametrize("name", [c.name for c in CHARMS])
def test_no_corners_a_fraction_of_a_micron_apart(parts, name):
    """Two corners closer than half the GRID make an edge that short, and zero-area
    triangles in the STL. The GRID and the INSET of the bands prevent them."""
    corners = np.array([tuple(v) for v in parts[name].vertices()])
    assert not cKDTree(corners).query_pairs(relief.GRID / 2)


@pytest.mark.parametrize("c", CHARMS, ids=lambda c: c.name)
def test_volume_matches_the_slabs(parts, c):
    """A boolean that fails silently can drop part of a solid without any error: the solid
    must have the volume of its 2D slabs (minus the hair of the band insets)."""
    planned = sum(g.area * (z1 - z0) for g, z0, z1 in wear.layout(c).slabs)
    assert parts[c.name].volume == pytest.approx(planned, rel=2e-3)


def test_clockwise_polygons_extrude_upwards():
    """The moka's handle comes clockwise, as given. build123d would extrude a clockwise face
    downwards: relief._faces turns it, so the black band lies above the green one with the
    volume of its footprint."""
    assert not LinearRing(artwork.HANDLE).is_ccw
    c = VARIANTS["moka_eyelet"]
    lay = wear.layout(c)
    black = wear.band_parts(c)[3]
    bb = black.bounding_box()
    assert bb.min.Z == pytest.approx(lay.z[3][0], abs=1e-6)
    assert bb.max.Z == pytest.approx(lay.z[3][1], abs=1e-6)
    assert black.volume == pytest.approx(relief.inset(lay.bands[3], 3).area * c.band_t, rel=1e-4)
