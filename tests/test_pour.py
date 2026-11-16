"""The moka that pours: its variants and defaults, the stream and its text, the colours, the
two magnets and the clip on a backing plate."""

import numpy as np
import pytest
from conftest import section
from shapely.geometry import Point, Polygon, box

from rh1charms import artwork, magnets, relief, wear
from rh1charms import params as P
from rh1charms.charms import VARIANTS, charm
from rh1charms.text import arc_text, glyph_limits, same_features, text_geometry, topology

POUR = [c for c in VARIANTS.values() if c.drawing == "moka_pour"]
EYELET, MAGNET, CLIP = (VARIANTS[f"moka_pour_{w}"] for w in ("eyelet", "magnet", "clip"))


def test_variants_and_their_defaults():
    assert POUR == [EYELET, MAGNET, CLIP]
    for c in POUR:
        assert c.text == "services" and c.bands == ("white", "red", "green")
        assert c.band_ts == (P.POUR_RED_T, P.BAND_T) == pytest.approx((1.2, 0.8))
        assert wear.layout(c).art.font_size == artwork.POUR_FONT == 10.0
    assert MAGNET.counter_name == "moka_pour_counter"


def test_red_t_changes_only_the_red_band():
    assert charm("moka_pour_eyelet", red_t=1.6).band_ts == pytest.approx((1.6, 0.8))
    assert charm("moka_pour_eyelet", band_t=1.0).band_ts == pytest.approx((1.2, 1.0))
    assert VARIANTS["tag_one_line_eyelet"].band_ts == pytest.approx((0.8, 0.8))  # 0: band_t
    assert charm("tag_one_line_eyelet", band_t=1.0).band_ts == pytest.approx((1.0, 1.0))
    assert charm("tag_one_line_eyelet", red_t=1.2).band_ts == pytest.approx((1.2, 0.8))
    assert VARIANTS["moka_eyelet"].band_ts == pytest.approx((0.8, 0.8, 0.8))


def test_plain_moka_ignores_a_text():
    """So that a --set text for every charm works, as before the moka that pours."""
    plain = wear.layout(VARIANTS["moka_eyelet"])
    with_text = wear.layout(charm("moka_eyelet", text="espresso"))
    assert with_text.art.text is None
    assert [b.equals(p) for b, p in zip(with_text.bands, plain.bands)] == [True] * 4


def test_a_new_layout_brings_its_own_defaults():
    c = charm("moka_eyelet", layout="pour")
    assert c == EYELET
    assert charm("moka_pour_eyelet", layout="").bands == VARIANTS["moka_eyelet"].bands


def test_a_smaller_font_size_can_be_forced_down_to_the_texts_limit():
    """Only the bent line is printed, so only its limits count: 'services' prints from its
    glyphs' own limit (the gap in 'e', 6.8 mm), although the same text straight would need
    7.9 mm (the gap between two characters)."""
    assert glyph_limits("services").size == 6.8
    assert wear.layout(charm("moka_pour_eyelet", font_size=6.8)).art.font_size == 6.8
    with pytest.raises(ValueError, match="font_size 6 mm is too small"):
        wear.layout(charm("moka_pour_eyelet", font_size=6.0))


def test_a_size_too_small_for_the_bent_line_is_skipped(monkeypatch):
    """A short stream bends tighter as the letters grow: if an automatic size is too small
    for the bent line, the next one is tried."""
    make = artwork.make

    def first_too_small(c, size=None):
        if size == artwork.POUR_FONT:
            raise artwork.TooSmall(f"{c.name}: font_size {size:g} mm is too small: (test)")
        return make(c, size)

    monkeypatch.setattr(artwork, "make", first_too_small)
    lay = wear.layout(charm("moka_pour_eyelet", text="servizi"))
    assert lay.art.font_size == artwork.POUR_FONT + 0.1


def test_only_a_band_left_empty_is_refused():
    """A band covers its colour and every one above it: a colour the drawing does not use is
    empty only at the top of the stack."""
    charm("tag_one_line_eyelet", bands=("white", "black", "red", "green"))  # no error
    with pytest.raises(ValueError, match="does not use black, so its band would be empty"):
        charm("moka_pour_eyelet", bands=("white", "red", "green", "black"))


def test_same_features_does_not_let_two_changes_cancel_out():
    ring = Point(0, 0).buffer(3).difference(Point(0, 0).buffer(1))  # one piece, one hole
    gap = box(5, -2, 9, 2).difference(box(6.9, -2.5, 7.1, 1.5))  # a slot open at the bottom
    raw = ring.union(gap)
    # the counter fills and the slot closes into a hole: 2 pieces and 1 hole, as before
    changed = Point(0, 0).buffer(3).union(box(5, -2, 9, 2).difference(box(6.9, -1.5, 7.1, 1.5)))
    assert topology(changed) == topology(raw)
    assert not same_features(changed, raw)
    assert same_features(raw.buffer(0.01), raw)


@pytest.mark.parametrize("t", ["services", "consulting", "sudo espresso", "kill -9 sleep"])
def test_bent_text_keeps_its_letters(t):
    straight, bent = text_geometry((t,), 10.0), arc_text(t, 10.0, 40.0)
    assert topology(bent, 1e-3) == topology(straight, 1e-3)
    assert bent.area == pytest.approx(straight.area, rel=1e-6)


def test_text_runs_along_the_stream_from_the_spout():
    """The letters start next to the tip of the spout, clear of the pot, inside the stream;
    the stream goes on STREAM_END after the last letter (its side bearing aside), then ends
    round."""
    art = wear.layout(EYELET).art
    band, pot, letters = art.parts["stream"], art.parts["pot"], art.text
    tip = artwork.pour_pose(Point(artwork.SPOUT_AXIS[1]))
    assert letters.distance(tip) < artwork.STREAM_CLEAR + 1.5
    assert letters.distance(pot) >= artwork.STREAM_CLEAR - 1e-6
    assert band.buffer(0.05 - artwork.STREAM_END).contains(letters)
    half = artwork.stream_layout(EYELET.text, art.font_size).half
    beyond = band.difference(pot.buffer(0.5)).difference(
        letters.buffer(half + artwork.STREAM_END + 0.1 * art.font_size))
    assert beyond.area < 0.1
    assert band.intersection(pot).area > 5  # the stream leaves the spout


@pytest.mark.parametrize("t", ["services", "sudo espresso"])
def test_raised_text_is_the_text_as_drawn(t):
    """As for the tag (test_text.py), measured apart from text_damage: inside the stream and
    clear of the pot, band 1 (red) is the raw text but for the corners of the letters."""
    lay = wear.layout(charm("moka_pour_eyelet", text=t))
    art = lay.art
    inner = art.parts["stream"].buffer(-0.5).difference(
        art.parts["pot"].buffer(artwork.STREAM_CLEAR - 0.1))
    raised, raw = lay.bands[1].intersection(inner), art.text
    assert raw.within(inner)
    assert topology(raised, 1e-3) == topology(raw, 1e-3)
    assert max(p.area for p in relief.polygons(raw.difference(raised))) < wear.LOST_MAX
    assert raw.difference(raised).area < wear.LOST_SHARE * raw.area
    assert max(p.area for p in relief.polygons(raised.difference(raw))) < relief.SPECK
    assert art.regions["white"].intersection(art.regions["red"]).area < 1e-6


def test_slivers_of_long_bent_outlines_are_not_lost_strokes():
    """At a large size, the band cleanup shaves long thin slivers off the bent outlines
    (0.155 mm2 for 'gjpqy' at 25 mm, over LOST_MAX): they are not strokes (wear.SLIVER)."""
    assert wear.layout(charm("moka_pour_eyelet", text="gjpqy", font_size=25.0)).art.font_size == 25


def test_a_longer_text_makes_a_longer_stream():
    short, long = (wear.layout(charm("moka_pour_eyelet", text=t)).art
                   for t in ("services", "sudo espresso"))
    assert long.parts["stream"].area > short.parts["stream"].area * 1.3
    assert long.font_size == artwork.POUR_FONT


def test_knob_and_handle_are_red():
    art = wear.layout(EYELET).art
    assert "black" not in art.regions
    for part in (artwork._knob(), Polygon(artwork.HANDLE)):
        assert artwork.pour_pose(part).difference(art.regions["red"]).area < 1e-6


def test_two_magnets_in_the_upper_chamber_and_the_boiler():
    """Its centre of mass lies on the stream, too narrow for a pocket: two pockets hold it,
    so it does not hang from one point."""
    lay = wear.layout(MAGNET)
    assert len(lay.pockets) == 2 and lay.pivot is None
    for pt, part in zip(lay.pockets, ("chamber", "boiler")):
        assert lay.art.parts[part].contains(Point(pt).buffer(MAGNET.pocket_d / 2))
    _, pts = magnets.counter_layout(MAGNET)
    assert len(pts) == 2


def test_clip_sits_on_a_backing_plate():
    """The plate is exactly the channel and its walls wide, with the channel in its middle,
    and reaches PLATE_MARGIN past the charm above and below; its bars lie PLATE_EDGE from
    its top and bottom edges, with room between them for the ribbon to turn flat."""
    lay = wear.layout(CLIP)
    (x0, x1), plate = lay.clip.channel, lay.clip.plate
    px0, py0, px1, py1 = plate.bounds
    assert px1 - px0 == pytest.approx(CLIP.lanyard_w + P.CHANNEL_EXTRA + 2 * P.RISER_W)
    assert (px0 + px1) / 2 == pytest.approx((x0 + x1) / 2)
    _, sy0, _, sy1 = lay.art.body.intersection(box(px0, -1e3, px1, 1e3)).bounds
    assert (sy0 - py0, py1 - sy1) == pytest.approx((P.PLATE_MARGIN, P.PLATE_MARGIN))
    (_, _, t0, t1), (_, _, b0, b1) = lay.clip.bars
    assert (t1, b0) == pytest.approx((py1 - P.PLATE_EDGE, py0 + P.PLATE_EDGE))
    assert t0 - b1 >= P.BAR_W
    assert lay.bands[0].contains(plate.buffer(-1e-3))


@pytest.mark.parametrize("changes", [{"text": "espresso"}, {"text": "sudo espresso"},
                                     {"text": "kill -9 sleep"}, {"lanyard_w": 15.0}])
def test_short_plates_grow_to_hold_two_bars(changes):
    """Where the moka crosses the channel over less height, the plate grows (around that
    height) to PLATE_MIN_H, so the two bars always fit with BAR_W between them."""
    lay = wear.layout(charm("moka_pour_clip", **changes))
    _, py0, _, py1 = lay.clip.plate.bounds
    assert py1 - py0 >= wear.PLATE_MIN_H - 1e-6
    (_, _, t0, _), (_, _, _, b1) = lay.clip.bars
    assert t0 - b1 >= P.BAR_W - 1e-6
    assert sum(lay.clip.channel) / 2 == pytest.approx(lay.centre[0], abs=0.01)


@pytest.mark.parametrize("t", ["services", "consulting", "sudo espresso"])
def test_plate_leaves_no_pinhole(t):
    """Where the plate meets the moka's outline, a small pocket can close into a hole: band 0
    keeps no hole under WINDOW_MIN, as the body does (it would go through the whole clip)."""
    lay = wear.layout(charm("moka_pour_clip", text=t))
    assert all(Polygon(h).area >= artwork.WINDOW_MIN
               for p in relief.polygons(lay.bands[0]) for h in p.interiors)


def test_plate_walls_hold_the_ceiling(parts):
    """Wherever the charm bridges the channel, a wall stands beside it on both sides:
    RISER_W wide, but in the rounded corners of the plate, where it narrows by less than
    PLATE_CORNER."""
    lay = wear.layout(CLIP)
    x0, x1 = lay.clip.channel
    _, py0, _, py1 = lay.clip.plate.bounds
    walls, ceiling = section(parts[CLIP.name], 2.0), section(parts[CLIP.name], 3.4)
    checked = 0
    for y in np.arange(py0 + 0.02, py1, 0.1):
        if not any(a < x0 + 0.01 and b > x1 - 0.01 for a, b in relief.chord(ceiling, y)):
            continue
        segs = relief.chord(walls, y)
        left = max((b - a for a, b in segs if abs(b - x0) < 0.02), default=0.0)
        right = max((b - a for a, b in segs if abs(a - x1) < 0.02), default=0.0)
        corner = y < py0 + P.PLATE_CORNER or y > py1 - P.PLATE_CORNER
        assert min(left, right) > (P.RISER_W - P.PLATE_CORNER if corner else P.RISER_W - 0.02)
        checked += 1
    assert checked > 200  # the whole height of the plate


def test_clip_is_the_printed_test():
    """The owner printed this one (2026-11-16, 'services', v3) and approved it."""
    assert wear.layout(CLIP).size == pytest.approx((82.4, 54.0, 6.0), abs=0.05)
    assert [z for z, _ in wear.colour_changes(CLIP)] == pytest.approx([4.2, 5.4])


def test_no_clip_gauge_for_a_backing_plate():
    assert magnets.extras([CLIP]) == []
    with pytest.raises(ValueError, match="backing plate"):
        magnets.clip_gauge_layout(CLIP)
    assert P.SLIT_WIDE > P.SLIT > P.RIBBON_T
