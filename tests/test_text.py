"""The raised text: the bundled font, the fill rule, and the smallest font size that prints."""

import numpy as np
import pytest
from scipy import ndimage

from rh1charms import params as P
from rh1charms import relief, text, wear
from rh1charms.charms import DEFAULT_TEXT, VARIANTS, charm
from rh1charms.render import mask
from rh1charms.text import LAYOUTS, glyph, limits, size_problems, split_lines, topology

LINES = {layout: split_lines(DEFAULT_TEXT, layout) for layout in LAYOUTS}


def test_font_is_bundled_with_its_license():
    fonts = text.FONT.parent
    assert text.FONT.name == "RedHatMono-Bold.ttf" and text.FONT.is_file()
    assert "SIL Open Font License" in (fonts / "OFL.txt").read_text(encoding="utf-8")
    assert "6bb1048a6402b0076ea04f42951ec66263cd1437" in (fonts / "README.md").read_text(
        encoding="utf-8")


def test_font_is_monospaced():
    widths = {glyph(chr(code))[1] for code in range(33, 127)}
    assert widths == {0.6}


@pytest.mark.parametrize("ch, pieces, holes", [("o", 1, 1), ("i", 2, 0), (":", 2, 0),
                                               ("B", 1, 2), ("@", 1, 1), ("$", 1, 2)])
def test_glyphs_keep_their_counters(ch, pieces, holes):
    """The nonzero fill rule gives every counter its hole and every dot its own piece. (The
    bar of Red Hat Mono's '$' runs right through: two counters.)"""
    assert topology(glyph(ch)[0]) == (pieces, holes)


def test_two_lines_split_before_the_at_sign_or_at_a_line_break():
    assert LINES["two_lines"] == ("consulting", "@italy:~$")
    assert LINES["one_line"] == (DEFAULT_TEXT,)
    assert split_lines("red\nhat", "two_lines") == ("red", "hat")
    with pytest.raises(ValueError, match="line break"):
        split_lines("no-at-sign", "two_lines")
    with pytest.raises(ValueError, match="one_line"):
        split_lines("a\nb", "one_line")


def test_missing_glyph_is_an_error():
    with pytest.raises(ValueError, match="no glyph"):
        glyph("☕")  # a coffee cup


@pytest.mark.parametrize("layout", LAYOUTS)
def test_smallest_font_size_is_set_by_the_gap_in_the_at_sign(layout):
    """Measured on the font, not tuned: the slot between the 'a' stem and the ring of '@' is
    0.055 em wide, so MIN_GAP needs 8.3 mm. Both layouts give the same size: the line pitch
    is not what limits it."""
    lim = limits(LINES[layout])
    assert lim.size == 8.3
    assert lim.bound == "the gap in '@'"
    assert lim.gap == pytest.approx(0.0547, abs=5e-4)
    assert lim.stroke * lim.size > P.MIN_STROKE  # the strokes are fine at that size


@pytest.mark.parametrize("layout", LAYOUTS)
def test_one_step_smaller_breaks_the_limits(layout):
    lim = limits(LINES[layout])
    assert size_problems(LINES[layout], lim.size) == []
    problems = size_problems(LINES[layout], round(lim.size - 0.1, 1))
    assert len(problems) == 1 and "gap (in '@')" in problems[0]


def _disk(r_px: int) -> np.ndarray:
    yy, xx = np.mgrid[-r_px:r_px + 1, -r_px:r_px + 1]
    return xx ** 2 + yy ** 2 <= r_px ** 2


def _raster_topology(img: np.ndarray) -> tuple[int, int]:
    """Pieces of a 1-bit image and pieces of its background (the holes plus the outside),
    leaving out specks of a few pixels."""
    return tuple(int((np.bincount(ndimage.label(x)[0].ravel())[1:] > 9).sum())
                 for x in (img, ~img))


@pytest.mark.parametrize("layout", LAYOUTS)
def test_raster_check_agrees_with_the_font_size(layout):
    """An independent measure, on pixels: at the chosen size, a closing a little under
    MIN_GAP and an opening a little under MIN_STROKE keep every piece and hole; at 0.9 times
    the size, the MIN_GAP closing joins something. (The rasteriser fills the edge pixels, so
    gaps look about a pixel narrower: 50 px/mm and the 10 % margins absorb that.)"""
    px = 50.0
    size = limits(LINES[layout]).size
    for s, r_gap, keeps in ((size, 0.9 * P.MIN_GAP / 2, True),
                            (0.9 * size, P.MIN_GAP / 2, False)):
        geom = text.text_geometry(LINES[layout], s)
        m = np.array(mask(geom, geom.bounds, px, pad=30), dtype=bool)
        start = _raster_topology(m)
        closed = ndimage.binary_closing(m, structure=_disk(round(r_gap * px)))
        assert (_raster_topology(closed) == start) is keeps, f"size {s:.2f}"
        if keeps:
            opened = ndimage.binary_opening(m, structure=_disk(round(0.9 * P.MIN_STROKE / 2 * px)))
            assert _raster_topology(opened) == start


def test_forced_font_size_below_the_limit_is_an_error():
    with pytest.raises(ValueError, match=r"too small.*'@'.*8\.3 mm"):
        wear.layout(charm("tag_one_line_eyelet", font_size=8.0))


def test_forced_font_size_is_used_as_given():
    """Not rounded to 0.1 mm: 8.25 mm keeps the 0.45 mm gap (0.0548 em) and prints at 8.25;
    8.21 mm does not, and the message names 8.21."""
    assert wear.layout(charm("tag_one_line_eyelet", font_size=8.25)).art.font_size == 8.25
    with pytest.raises(ValueError, match=r"font_size 8\.21 mm is too small"):
        wear.layout(charm("tag_one_line_eyelet", font_size=8.21))


def test_forced_larger_font_size_makes_a_larger_tag():
    big = wear.layout(charm("tag_one_line_eyelet", font_size=10.0))
    default = wear.layout(VARIANTS["tag_one_line_eyelet"])
    assert big.art.font_size == 10.0
    assert big.size[0] > default.size[0] and big.size[1] > default.size[1]


# the default text, and texts whose strokes can vanish without changing the topology (the
# foot of an L, the bar of a T or a 7): the text's own limits are not enough for them
TEXTS = [(n, {}) for n in VARIANTS if n.startswith("tag")] + [
    ("tag_one_line_eyelet", {"text": "LT"}), ("tag_one_line_clip", {"text": "17:17:17"}),
    ("tag_one_line_eyelet", {"text": "17"}),
    ("tag_one_line_eyelet", {"text": "7:17"}),
    ("tag_two_lines_clip", {"text": "consulting\n@roma:~$"})]


@pytest.mark.parametrize("name, changes", TEXTS,
                         ids=[f"{n}-{c.get('text', 'default')}" for n, c in TEXTS])
def test_raised_text_is_the_text_as_drawn(name, changes):
    """colour_bands() widens grooves and drops thin strokes. It must not change the letters,
    for any text: band 1 inside the white middle has every piece and hole of the raw text,
    and differs from it only at the corners (the opening rounds the outer ones, the specks
    fill the inner ones): no piece of the difference is larger than a corner."""
    lay = wear.layout(charm(name, **changes))
    inner = lay.art.parts["middle"].buffer(-0.5)  # clear of the edges of the end bands
    raised, raw = lay.bands[1].intersection(inner), lay.art.text
    assert raw.within(inner)
    assert topology(raised, 1e-3) == topology(raw, 1e-3)
    assert max(p.area for p in relief.polygons(raw.difference(raised))) < wear.LOST_MAX
    assert raw.difference(raised).area < wear.LOST_SHARE * raw.area
    assert max(p.area for p in relief.polygons(raised.difference(raw))) < relief.SPECK


@pytest.mark.parametrize("t", ["LT", "17"])
def test_strokes_that_vanish_quietly_raise_the_font_size(t):
    """The foot of an L or the bar of a 7 can vanish without changing the topology, so the
    text's own limits allow too small a size (2.1 mm for LT): the size goes up until the
    letters come through the cleanup, and the forced small size is an error."""
    lim = limits((t,))
    lay = wear.layout(charm("tag_one_line_eyelet", text=t))
    assert lay.art.font_size > lim.size + 1
    assert lay.art.size_bound.startswith("the band cleanup")
    with pytest.raises(ValueError, match="the band cleanup changes the letters"):
        wear.layout(charm("tag_one_line_eyelet", text=t, font_size=lim.size))
