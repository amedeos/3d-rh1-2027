"""The moka that pours: its variants and defaults, the stream and its text, the colours, the
two magnets, the clip on a backing plate, and RH1 and 2027 on that plate."""

import re
from dataclasses import replace

import numpy as np
import pytest
from conftest import section
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from rh1charms import artwork, magnets, relief, wear
from rh1charms import params as P
from rh1charms.charms import VARIANTS, charm, parse_value
from rh1charms.text import arc_text, glyph_limits, limits, same_features, text_geometry, topology

POUR = [c for c in VARIANTS.values() if c.layout == "pour"]
EYELET, MAGNET, CLIP = (VARIANTS[f"moka_pour_{w}"] for w in ("eyelet", "magnet", "clip"))
RH1 = VARIANTS["moka_pour_rh1_clip"]
NEED = P.LANYARD_W + P.CHANNEL_EXTRA + 2 * P.RISER_W  # the plate's width


def test_variants_and_their_defaults():
    assert POUR == [EYELET, MAGNET, CLIP]
    for c in POUR:
        assert c.text == "consulting" and c.bands == ("white", "red", "green")
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


@pytest.mark.parametrize("t", ["espresso", ""])
def test_plain_moka_ignores_a_text(t):
    """So that a --set text for every charm works, as before the moka that pours: an empty
    one too."""
    plain = wear.layout(VARIANTS["moka_eyelet"])
    with_text = wear.layout(charm("moka_eyelet", text=t))
    assert with_text.art.text is None
    assert [b.equals(p) for b, p in zip(with_text.bands, plain.bands)] == [True] * 4
    with pytest.raises(ValueError, match="the text is empty"):
        charm("moka_pour_eyelet", text=" ").validate()


def test_a_new_layout_brings_its_own_defaults():
    c = charm("moka_eyelet", layout="pour")
    assert c == EYELET
    assert charm("moka_pour_eyelet", layout="").bands == VARIANTS["moka_eyelet"].bands


def test_a_smaller_font_size_can_be_forced_down_to_the_texts_limit():
    """Only the bent line is printed, so only its limits count: 'services' prints from its
    glyphs' own limit (the gap in 'e', 6.8 mm), although the same text straight would need
    7.9 mm (the gap between two characters)."""
    assert glyph_limits("services").size == 6.8
    c = charm("moka_pour_eyelet", text="services", font_size=6.8)
    assert wear.layout(c).art.font_size == 6.8
    with pytest.raises(ValueError, match="font_size 6 mm is too small"):
        wear.layout(charm("moka_pour_eyelet", text="services", font_size=6.0))


def test_a_size_too_small_for_the_bent_line_is_skipped(monkeypatch):
    """A short stream bends tighter as the letters grow: if an automatic size is too small
    for the bent line, the next one is tried, and size_bound says why."""
    make = artwork.make

    def first_too_small(c, size=None):
        if size == artwork.POUR_FONT:
            raise artwork.TooSmall(f"{c.name}: font_size {size:g} mm is too small: (test)",
                                   "(test)")
        return make(c, size)

    monkeypatch.setattr(artwork, "make", first_too_small)
    # past the cache of layout: the fake must not stay there for other tests
    lay = wear.layout.__wrapped__(charm("moka_pour_eyelet", text="servizi"))
    assert lay.art.font_size == artwork.POUR_FONT + 0.1
    assert lay.art.size_bound == "the bent text on its stream, too small at 10 mm"


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


@pytest.mark.parametrize("c", [CLIP, RH1], ids=lambda c: c.name)
def test_plate_walls_hold_the_ceiling(parts, c):
    """Wherever the charm bridges the channel, a wall stands beside it on both sides:
    RISER_W wide, but in the rounded corners of the plate, where it narrows by less than
    PLATE_CORNER."""
    lay = wear.layout(c)
    x0, x1 = lay.clip.channel
    _, py0, _, py1 = lay.clip.plate.bounds
    walls, ceiling = section(parts[c.name], 2.0), section(parts[c.name], 3.4)
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


@pytest.mark.parametrize(("t", "size"), [("consulting", (92.6, 60.3, 6.0)),
                                         ("services", (82.4, 54.0, 6.0))])
def test_clip_is_the_printed_test(t, size):
    """The owner printed these and approved them: 'services' (2026-11-16, v3) and the
    default, 'consulting' (2026-11-17)."""
    c = charm("moka_pour_clip", text=t)
    assert wear.layout(c).size == pytest.approx(size, abs=0.05)
    assert [z for z, _ in wear.colour_changes(c)] == pytest.approx([4.2, 5.4])


def test_no_clip_gauge_for_a_backing_plate():
    assert magnets.extras([CLIP]) == []
    with pytest.raises(ValueError, match="backing plate"):
        magnets.clip_gauge_layout(CLIP)
    assert P.SLIT_WIDE > P.SLIT > P.RIBBON_T


# --- RH1 and 2027 on the backing plate (moka_pour_rh1_clip) --------------------------------
def test_rh1_is_a_variant_with_a_clip_only():
    assert [n for n in VARIANTS if n.startswith("moka_pour_rh1")] == ["moka_pour_rh1_clip"]
    assert (RH1.plate_top, RH1.plate_bottom, RH1.plate_font) == ("RH1", "2027", 0.0)
    assert (RH1.text, RH1.bands, RH1.band_ts) == (CLIP.text, CLIP.bands, CLIP.band_ts)
    for w in ("eyelet", "magnet"):
        with pytest.raises(ValueError, match="backing plate of the clip"):
            charm(f"moka_pour_rh1_{w}")
    with pytest.raises(ValueError, match="one line"):  # \n typed on the command line
        charm("moka_pour_rh1_clip", plate_top=parse_value(RH1, "plate_top", "RH1\\n2027"))
    with pytest.raises(ValueError, match="plate_font must not be negative"):
        charm("moka_pour_rh1_clip", plate_font=-1.0)


def test_other_layouts_ignore_the_plate_texts():
    """So that a --set for every charm works: the same charm as without them."""
    assert charm("moka_pour_clip", plate_top="RH1", plate_bottom="2027", plate_font=8.0) == CLIP
    assert charm("tag_one_line_clip", plate_top="X") == VARIANTS["tag_one_line_clip"]
    assert wear.layout(CLIP).clip.letters == ()
    assert replace(CLIP, layout="pour_rh1") == RH1  # a new layout gets its own texts


def test_plate_texts_lie_where_the_owner_chose():
    """RH1 (red) in the top right corner and 2027 (green) in the middle of the bottom edge,
    PLATE_TEXT_MARGIN in, at one size that prints, STREAM_CLEAR from the moka and from each
    other."""
    lay = wear.layout(RH1)
    (t1, c1, top), (t2, c2, bottom) = lay.clip.letters
    assert (t1, c1, t2, c2) == ("RH1", "red", "2027", "green")
    px0, py0, px1, py1 = lay.clip.plate.bounds
    m = P.PLATE_TEXT_MARGIN
    assert top.bounds[2:] == pytest.approx((px1 - m, py1 - m), abs=1e-6)
    x0, y0, x1, _ = bottom.bounds
    assert ((x0 + x1) / 2, y0) == pytest.approx(((px0 + px1) / 2, py0 + m), abs=1e-6)
    size = lay.clip.font
    assert size >= max(limits((t,)).size for t in ("RH1", "2027"))
    for t, g in (("RH1", top), ("2027", bottom)):
        assert g.area == pytest.approx(text_geometry((t,), size).area)
    moka = unary_union([lay.art.parts["pot"], lay.art.parts["stream"]])
    assert min(top.distance(moka), bottom.distance(moka), top.distance(bottom)) >= (
        artwork.STREAM_CLEAR - 1e-6)


def test_plate_texts_rise_in_their_colours():
    """RH1 in the red band only; 2027 in the green band and in the red one under it. The
    letters come through the band cleanup on every band they raise: the bar of the 7 is a
    stroke the topology would not miss."""
    lay = wear.layout(RH1)
    (_, _, top), (_, _, bottom) = lay.clip.letters
    red, green = lay.bands[1], lay.bands[2]
    for g, raised_on in ((top, [red]), (bottom, [red, green])):
        for band in raised_on:
            assert wear.letters_damage(band.intersection(g.envelope.buffer(0.5)), g) is None
    assert green.intersection(top.envelope.buffer(0.5)).is_empty


def test_plate_grows_only_at_the_bottom():
    """The top edge is the plain plate's where the channel lies; the plate grows at the
    bottom for 2027, and the bars stay PLATE_EDGE from its edges."""
    lay = wear.layout(RH1)
    plain = wear.plate_for(lay.art.body, sum(lay.clip.channel) / 2, NEED).bounds
    _, py0, _, py1 = lay.clip.plate.bounds
    assert py1 == pytest.approx(plain[3], abs=1e-9)
    assert plain[1] - py0 > 1.0
    (_, _, _, t1), (_, _, b0, _) = lay.clip.bars
    assert (t1, b0) == pytest.approx((py1 - P.PLATE_EDGE, py0 + P.PLATE_EDGE))
    assert all(Polygon(h).area >= artwork.WINDOW_MIN
               for p in relief.polygons(lay.bands[0]) for h in p.interiors)


def test_plate_texts_can_be_left_out():
    """No top text: 2027 at POUR_FONT. No bottom text: the plate keeps its height. None: the
    plain moka_pour_clip."""
    no_top = wear.layout(charm("moka_pour_rh1_clip", plate_top=""))
    assert [t for t, _, _ in no_top.clip.letters] == ["2027"]
    assert no_top.clip.font == artwork.POUR_FONT
    no_bottom = wear.layout(charm("moka_pour_rh1_clip", plate_bottom=""))
    assert [t for t, _, _ in no_bottom.clip.letters] == ["RH1"]
    x = sum(no_bottom.clip.channel) / 2
    assert no_bottom.clip.plate.bounds == pytest.approx(
        wear.plate_for(no_bottom.art.body, x, NEED).bounds, abs=1e-9)
    none = wear.layout(charm("moka_pour_rh1_clip", plate_top="", plate_bottom=""))
    assert none.clip.letters == ()
    assert all(b.equals(p) for b, p in zip(none.bands, wear.layout(CLIP).bands, strict=True))


def _plain_plate(lay, need=NEED):
    return wear.plate_for(lay.art.body, sum(lay.clip.channel) / 2, need).bounds


def test_plate_fit_holds_where_the_plate_settles():
    """Where the plate went, the texts' size is the largest that fits, and the plate grew by
    the least the texts need at that size."""
    lay = wear.layout(RH1)
    x = sum(lay.clip.channel) / 2
    texts = [("top", "RH1", "red"), ("bottom", "2027", "green")]
    moka = unary_union([lay.art.parts["pot"], lay.art.parts["stream"]])
    fit = wear._plate_fit(RH1, lay.art, x, NEED, texts, moka)
    assert fit == wear._plate_fit(RH1, lay.art, x, NEED, texts, moka, lay.clip.font)
    plain, (_, py0, _, py1) = _plain_plate(lay), lay.clip.plate.bounds
    assert fit == pytest.approx((lay.clip.font, py1 - plain[3], plain[1] - py0), abs=1e-9)


def test_plate_font_can_be_forced():
    """Smaller: a shorter plate. Larger than the corner: the plate grows at the top too."""
    small = wear.layout(charm("moka_pour_rh1_clip", plate_font=7.0))
    assert small.clip.font == 7.0 and len(small.clip.letters) == 2
    assert small.clip.plate.bounds[1] > wear.layout(RH1).clip.plate.bounds[1]
    large = wear.layout(charm("moka_pour_rh1_clip", plate_font=9.5))
    assert large.clip.font == 9.5
    assert large.clip.plate.bounds[3] > _plain_plate(large)[3] + 1.0


@pytest.mark.parametrize("lw", [18.0, 15.0])
def test_a_narrower_lanyard_grows_the_plate_at_the_top(lw):
    """A narrower plate no longer reaches up to the knob, and its corner is too small for
    RH1: the plate grows at the top, just enough for the smallest size that prints both
    texts (so a --set lanyard_w for every charm still works)."""
    lay = wear.layout(charm("moka_pour_rh1_clip", lanyard_w=lw))
    need = lw + P.CHANNEL_EXTRA + 2 * P.RISER_W
    assert lay.clip.plate.bounds[3] > _plain_plate(lay, need)[3] + 1.0
    assert lay.clip.font == max(limits((t,)).size for t in ("RH1", "2027"))


def test_a_wide_bottom_text_alone_gets_the_size_the_plate_allows():
    lay = wear.layout(charm("moka_pour_rh1_clip", plate_top="", plate_bottom="ITALY"))
    ((t, _, g),) = lay.clip.letters
    px0, _, px1, _ = lay.clip.plate.bounds
    assert t == "ITALY" and lay.clip.font < artwork.POUR_FONT
    assert g.bounds[2] - g.bounds[0] <= px1 - px0 - 2 * P.PLATE_TEXT_MARGIN + 1e-6


@pytest.mark.parametrize(("changes", "message"), [
    ({"plate_font": 12.0}, "wider than its 24.4 mm inside the margins"),
    ({"plate_font": 6.0}, "'RH1' is too small"),
    ({"plate_bottom": "ITALIA"}, "'ITALIA' prints from 8.2 mm"),
    ({"bands": ("green", "white", "red")}, "green cannot print the body"),
    ({"plate_top": " "}, "has no letters"),
    ({"plate_top": "\u200b"}, "draws nothing"),
])
def test_plate_texts_that_cannot_print_are_clear_errors(changes, message):
    with pytest.raises(ValueError, match=re.escape(message)):
        wear.layout(charm("moka_pour_rh1_clip", **changes))
