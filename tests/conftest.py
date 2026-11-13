"""Shared fixtures: every part is built once per test session (about 30 s)."""

import numpy as np
import pytest
import trimesh
from shapely.geometry import Polygon
from shapely.ops import unary_union

from rh1charms.charms import VARIANTS
from rh1charms.export import jobs
from rh1charms.magnets import CLIP_GAUGE, GAUGE

CHARMS = list(VARIANTS.values())
MAGNETS = [c for c in CHARMS if c.wear == "magnet"]
# every printable part by name: the charms, the counter plates and the two gauges
NAMES = [c.name for c in CHARMS] + [c.counter_name for c in MAGNETS] + [GAUGE, CLIP_GAUGE]


def charm_id(c) -> str:
    return c.name


@pytest.fixture(scope="session")
def parts():
    """Every printable part on the bed, by name."""
    return {name: job[0] for name, (_, job) in jobs(CHARMS).items()}


def section(part, z: float):
    """The cross-section of a solid at height z, as shapely geometry in x, y."""
    verts, tris = part.tessellate(0.005, 0.1)
    mesh = trimesh.Trimesh([[v.X, v.Y, v.Z] for v in verts], tris)
    path = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if path is None:
        return Polygon()
    to_2d = np.eye(4)
    to_2d[2, 3] = -z  # keep x and y as they are
    planar, _ = path.to_planar(to_2D=to_2d, check=False)
    return unary_union(list(planar.polygons_full))
