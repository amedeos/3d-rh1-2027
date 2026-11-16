"""The ways to wear a charm, measured on the solids (cross-sections), not on the constants."""

import math
from itertools import pairwise

import pytest
from conftest import MAGNETS, section
from shapely.geometry import Point, Polygon, box

from rh1charms import magnets, relief, wear
from rh1charms import params as P
from rh1charms.charms import VARIANTS, charm
from rh1charms.export import check, plates
from rh1charms.relief import polygons

EYELETS = [c for c in VARIANTS.values() if c.wear == "eyelet"]
CLIPS = [c for c in VARIANTS.values() if c.wear == "clip"]


def holes(geom) -> list:
    return [h for p in polygons(geom) for h in p.interiors]


def diameter(ring) -> float:
    """The diameter of a circle with the area of this ring."""
    return math.sqrt(4 * Polygon(ring).area / math.pi)


# --- eyelet -------------------------------------------------------------------------------
@pytest.mark.parametrize("c", EYELETS, ids=lambda c: c.name)
def test_eyelet_hangs_upright(c):
    """The centre of mass of the solids lies under the top of the hole (the tab was placed
    with the 2D centre of the slabs: this checks it)."""
    lay = wear.layout(c)
    assert wear.hang_angle(lay.hole, wear.mass_centre(c)) < 0.1


@pytest.mark.parametrize("c", EYELETS, ids=lambda c: c.name)
def test_eyelet_has_a_4_mm_hole_in_a_2_mm_ring_above_the_charm(parts, c):
    cut = section(parts[c.name], P.BASE_T / 2)
    (hole,) = holes(cut)
    assert diameter(hole) == pytest.approx(4.0, abs=0.02)
    x, y, r = wear.layout(c).hole
    ring = cut.intersection(Point(x, y).buffer(c.tab_r + 0.5))
    # the ring is 2.0 mm all round: the hole's edge to the outside of the tab
    assert ring.exterior.distance(Point(x, y)) == pytest.approx(c.tab_r, abs=0.02)
    assert c.tab_r - r == pytest.approx(2.0)
    # the hole lies above the body under the tab
    under = wear.layout(c).art.body.intersection(box(x - c.tab_r, -1e3, x + c.tab_r, 1e3))
    assert y - r >= under.bounds[3] - 1e-6


# --- magnets ------------------------------------------------------------------------------
@pytest.mark.parametrize("c", MAGNETS, ids=lambda c: c.name)
def test_pockets_are_blind_under_a_bridged_roof(parts, c):
    """8.2 mm pockets for 8 x 2 mm magnets, 2.2 mm deep from the bed, under 0.6 mm of roof."""
    part = parts[c.name]
    n = len(wear.layout(c).pockets)
    for z in (0.1, 1.1, 2.1):  # inside the pocket
        cut = holes(section(part, z))
        assert len(cut) == n and all(diameter(h) == pytest.approx(8.2, abs=0.02) for h in cut)
    for z in (2.3, 2.7):  # the roof
        assert holes(section(part, z)) == []
    assert P.MAGNET_BODY_T - P.POCKET_DEPTH == pytest.approx(0.6)
    assert wear.layout(c).z[0] == (0.0, pytest.approx(2.8))


@pytest.mark.parametrize("c", MAGNETS, ids=lambda c: c.name)
def test_pocket_walls_are_thick_enough(parts, c):
    cut = section(parts[c.name], 1.1)
    for p in polygons(cut):
        for h in p.interiors:
            assert p.exterior.distance(h) >= P.MIN_POCKET_WALL - 0.01


@pytest.mark.parametrize("layout", ["one_line", "two_lines"])
def test_tag_pockets_lie_a_quarter_of_the_width_from_each_end(parts, layout):
    c = VARIANTS[f"tag_{layout}_magnet"]
    cut = section(parts[c.name], 1.1)
    x0, y0, x1, y1 = cut.bounds
    w = x1 - x0
    centres = sorted((Polygon(h).centroid.x, Polygon(h).centroid.y) for h in holes(cut))
    assert centres[0][0] == pytest.approx(x0 + w / 4, abs=0.05)
    assert centres[1][0] == pytest.approx(x1 - w / 4, abs=0.05)
    assert centres[0][1] == pytest.approx((y0 + y1) / 2, abs=0.05) == centres[1][1]


def test_moka_magnet_lies_in_the_upper_chamber_over_the_centre_of_mass():
    c = VARIANTS["moka_magnet"]
    lay = wear.layout(c)
    (x, y), = lay.pockets
    cx, cy = wear.mass_centre(c)
    assert lay.art.parts["chamber"].contains(Point(x, y).buffer(c.pocket_d / 2))
    assert y > cy and abs(x - cx) < 0.05


def test_tag_too_small_for_its_magnets_is_an_error():
    with pytest.raises(ValueError, match="too small for the magnets"):
        wear.layout(charm("tag_one_line_magnet", text="17"))


def test_clearance_changes_only_the_pocket_diameter():
    c = charm("tag_two_lines_magnet", magnet_clr=0.3)
    part = wear.make_charm(c)
    assert all(diameter(h) == pytest.approx(8.3, abs=0.02) for h in holes(section(part, 1.1)))
    assert holes(section(part, 2.3)) == []  # still 2.2 mm deep
    assert part.bounding_box().max.Z == pytest.approx(wear.make_charm(
        VARIANTS["tag_two_lines_magnet"]).bounding_box().max.Z)


@pytest.mark.parametrize("c", MAGNETS, ids=lambda c: c.name)
def test_counter_plate_matches_the_charm(parts, c):
    """3.0 mm thick, a 0.8 mm floor towards the shirt, pockets open on top, where the
    charm's lie once the two face each other."""
    plate = parts[c.counter_name]
    assert plate.bounding_box().max.Z == pytest.approx(3.0)
    assert holes(section(plate, 0.4)) == []
    open_top = section(plate, 2.0)
    found = sorted(Polygon(h).centroid.x for h in holes(open_top))
    expected = len(wear.layout(c).pockets)
    assert len(found) == expected
    assert all(diameter(h) == pytest.approx(8.2, abs=0.02) for h in holes(open_top))
    if expected == 2:
        pts = wear.layout(c).pockets
        assert found[1] - found[0] == pytest.approx(abs(pts[1][0] - pts[0][0]), abs=0.05)


def test_pocket_gauge_has_four_pockets_like_the_charms(parts):
    gauge = parts[magnets.GAUGE]
    found = sorted(diameter(h) for h in holes(section(gauge, 1.1)))
    assert found == pytest.approx(list(P.GAUGE_D), abs=0.02)
    assert holes(section(gauge, 2.5)) == []  # the same 0.6 mm roof
    assert gauge.bounding_box().max.Z == pytest.approx(P.MAGNET_BODY_T + magnets.DOT_H)
    dots = polygons(section(gauge, P.MAGNET_BODY_T + magnets.DOT_H / 2))
    assert len(dots) == 1 + 2 + 3 + 4


# --- the lanyard clip ---------------------------------------------------------------------
def _gaps_x(geom, y: float) -> list[float]:
    """The widths of the empty stretches between the pieces along a line at height y."""
    ranges = relief.chord(geom, y)
    return [b[0] - a[1] for a, b in pairwise(ranges)]


@pytest.mark.parametrize("c", CLIPS, ids=lambda c: c.name)
def test_clip_clearances(parts, c):
    """The tag has one bar, joined to the left wall; the moka that pours two, on its backing
    plate: the top one joined to the left wall (SLIT), the bottom one to the right wall
    (SLIT_WIDE)."""
    part = parts[c.name]
    lay = wear.layout(c)
    x0, x1 = lay.clip.channel
    slits = [P.SLIT] if lay.clip.plate is None else [P.SLIT, P.SLIT_WIDE]
    assert len(lay.clip.bars) == len(slits)
    floor = section(part, P.BAR_T / 2)
    assert len(polygons(floor)) == 2  # each bar is joined to one wall only
    near = box(x0 - P.RISER_W, -1e3, x1 + P.RISER_W, 1e3)  # the channel and its walls
    for (bx0, bx1, ym0, ym1), slit, side in zip(lay.clip.bars, slits, ("left", "right")):
        ym = (ym0 + ym1) / 2
        # the bar on the bed: joined to one wall, a slit before the other
        assert _gaps_x(floor.intersection(near), ym) == pytest.approx([slit], abs=0.01)
        bar = floor.intersection(box(x0 + 0.5, ym0 - 0.5, x1 - 0.5, ym1 + 0.5))
        _, by0, _, by1 = bar.bounds
        assert by1 - by0 == pytest.approx(P.BAR_W, abs=0.01)
        assert (bx1 == pytest.approx(x1 - slit)) if side == "left" else (
            bx0 == pytest.approx(x0 + slit))
        # the ribbon gap: nothing over the bar up to the underside of the charm at 2.8 mm
        for z in (1.3, 2.0, 2.7):
            cut = section(part, z)
            assert len(polygons(cut)) == 2  # the two walls (the risers)
            (channel,) = _gaps_x(cut.intersection(near), ym)
            assert channel == pytest.approx(c.lanyard_w + 2, abs=0.01)
            assert min(p.bounds[2] - p.bounds[0] for p in polygons(cut)) >= P.RISER_W
            # the channel runs through the whole height of the charm: the ribbon goes in and out
            assert cut.intersection(box(x0 + 0.01, -1e3, x1 - 0.01, 1e3)).area < 1e-6
    assert len(polygons(section(part, 2.9))) == 1  # the charm bridges the channel
    assert P.CLIP_Z - P.BAR_T == pytest.approx(1.6)


def test_clip_takes_the_ribbon():
    """The measured ribbon goes through the slit on its edge and lies flat under the bar,
    on the tag and on every piece of the gauge. SLIT is one of the gauge's slits: the
    owner chooses it from the gauge."""
    assert P.SLIT > P.RIBBON_T
    assert min(P.CLIP_GAUGE_SLITS) > P.RIBBON_T
    assert any(abs(P.SLIT - s) < 1e-6 for s in P.CLIP_GAUGE_SLITS)
    assert P.RIBBON_GAP > P.RIBBON_T


def test_clip_gauge_has_the_tag_clip_with_four_slits(parts):
    """Four pieces, left to right, each one the back of the first clip tag: the same channel,
    bar, ribbon gap and ceiling, as tall as the tag. Only the slit differs, with 1 to 4
    dots on top."""
    c = CLIPS[0]
    lay = wear.layout(c)
    (_, _, ym0, ym1), = lay.clip.bars  # x0, x1, y0, y1
    ym = (ym0 + ym1) / 2
    _, ty0, _, ty1 = lay.bands[0].bounds
    gauge = parts[magnets.CLIP_GAUGE]
    pieces = sorted(gauge.solids(), key=lambda s: s.bounding_box().min.X)
    assert len(pieces) == len(P.CLIP_GAUGE_SLITS) == 4
    for k, (piece, slit) in enumerate(zip(pieces, P.CLIP_GAUGE_SLITS)):
        bb = piece.bounding_box()
        assert (bb.min.Y, bb.max.Y) == pytest.approx((ty0, ty1), abs=0.01)
        floor = section(piece, P.BAR_T / 2)
        assert len(polygons(floor)) == 2
        assert _gaps_x(floor, ym) == pytest.approx([slit], abs=0.01)
        x0, x1 = bb.min.X + magnets.CLIP_GAUGE_WALL, bb.max.X - magnets.CLIP_GAUGE_WALL
        _, by0, _, by1 = floor.intersection(box(x0 + 0.5, -1e3, x1 - 0.5, 1e3)).bounds
        assert (by0, by1) == pytest.approx((ym0, ym1), abs=0.01)  # where the tag has its bar
        for z in (1.3, 2.0, 2.7):
            cut = section(piece, z)
            assert len(polygons(cut)) == 2
            assert _gaps_x(cut, ym) == pytest.approx([c.lanyard_w + P.CHANNEL_EXTRA], abs=0.01)
            assert min(p.bounds[2] - p.bounds[0] for p in polygons(cut)) >= P.RISER_W
        assert len(polygons(section(piece, P.CLIP_Z + 0.1))) == 1  # the ceiling
        assert bb.max.Z == pytest.approx(c.base_t + magnets.DOT_H)
        assert len(polygons(section(piece, c.base_t + magnets.DOT_H / 2))) == k + 1
    planned = sum(g.area * (z1 - z0) for slabs, _ in magnets.clip_gauge_layout(c)
                  for g, z0, z1 in slabs)
    planned += sum(d.area for _, d in magnets.clip_gauge_layout(c)) * magnets.DOT_H
    assert gauge.volume == pytest.approx(planned, rel=2e-3)


def test_clip_gauge_follows_the_charm_and_fits_the_bed():
    """The two-line tag's gauge is as tall as that tag; a wide lanyard puts the pieces in
    rows, so the gauge never stops an export of a clip charm that fits."""
    c = VARIANTS["tag_two_lines_clip"]
    gauge = magnets.make_clip_gauge(c)
    assert len(gauge.solids()) == len(P.CLIP_GAUGE_SLITS)
    _, y0, _, y1 = wear.layout(c).bands[0].bounds
    assert {round(s.bounding_box().size.Y, 2) for s in gauge.solids()} == {round(y1 - y0, 2)}
    wide = charm("tag_one_line_clip", lanyard_w=55.0)
    plates([wide])  # does not raise
    wide_gauge = magnets.make_clip_gauge(wide)
    assert check(wide_gauge, len(P.CLIP_GAUGE_SLITS)) == []
    bb = wide_gauge.bounding_box()
    assert bb.size.X <= P.BED[0] and bb.size.Y <= P.BED[1]


def test_clip_gauge_comes_once_with_a_clip_charm():
    names = [name for name, _, _ in magnets.extras(CLIPS)]
    assert names == [magnets.CLIP_GAUGE]
    assert magnets.CLIP_GAUGE not in [n for n, _, _ in magnets.extras(EYELETS + MAGNETS)]
    with pytest.raises(ValueError, match="only a clip charm"):
        magnets.clip_gauge_layout(EYELETS[0])


def test_clip_channel_follows_the_lanyard_width():
    c = charm("tag_two_lines_clip", lanyard_w=30.0)
    cut = section(wear.make_charm(c), 2.0)
    lay = wear.layout(c)
    (_, _, ym0, ym1), = lay.clip.bars
    assert _gaps_x(cut, (ym0 + ym1) / 2) == pytest.approx([32.0], abs=0.01)


def test_clip_lies_over_the_centre_of_mass():
    for c in CLIPS:
        x0, x1 = wear.layout(c).clip.channel
        assert (x0 + x1) / 2 == pytest.approx(wear.mass_centre(c)[0], abs=0.05)


def test_wide_channel_settles_or_refuses():
    """A wide channel moves the centre of mass the other way, about as far as it moves:
    the placement still converges (56 mm on the two-line tag), and where the walls at the
    ends of the tag stop the channel short of the centre of mass (57 mm), it is an error,
    not a tag that hangs crooked."""
    lay = wear.layout(charm("tag_two_lines_clip", lanyard_w=56.0))
    assert sum(lay.clip.channel) / 2 == pytest.approx(lay.centre[0], abs=0.01)
    with pytest.raises(ValueError, match="cannot lie over the centre of mass"):
        wear.layout(charm("tag_two_lines_clip", lanyard_w=57.0))


def test_moka_is_too_narrow_for_a_clip():
    with pytest.raises(ValueError, match=r"too narrow.*26\.8 mm.*at most 18\.\d mm"):
        wear.layout(charm("moka_clip"))


def test_lanyard_wider_than_the_tag_is_an_error():
    with pytest.raises(ValueError, match="too narrow"):
        wear.layout(charm("tag_two_lines_clip", lanyard_w=60.0))


def test_tag_hangs_level_on_its_magnets_and_clip():
    """Two magnets or a clip do not hang the charm: no plumb line, no tilt."""
    for name in ("tag_one_line_magnet", "tag_two_lines_clip"):
        assert wear.layout(VARIANTS[name]).tilt is None
