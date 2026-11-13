"""Previews: the image set of every part, the 2D colour check and the plumb line."""

import numpy as np
from conftest import CHARMS
from PIL import Image, ImageColor
from shapely.geometry import MultiPolygon, Polygon, box

from rh1charms import render, wear
from rh1charms.charms import VARIANTS
from rh1charms.render import PLUMB


def test_mask_keeps_an_island_inside_a_hole():
    frame = box(0, 0, 10, 10).difference(box(2, 2, 8, 8))
    island = box(4, 4, 6, 6)
    m = np.array(render.mask(MultiPolygon([island, frame]), (0, 0, 10, 10), 10, pad=0),
                 dtype=bool)
    assert m[50, 50] and not m[30, 30] and m[5, 5]


def test_mask_keeps_holes():
    ring = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)], [[(3, 3), (7, 3), (7, 7), (3, 7)]])
    m = np.array(render.mask(ring, (0, 0, 10, 10), 10, pad=0), dtype=bool)
    assert m[5, 5] and not m[50, 50]


def test_every_part_gets_front_back_and_edge_images(tmp_path, monkeypatch):
    """Every charm (both tag layouts), every counter plate and the gauges: front, back and
    edge profile; a charm also its 2D bands, and a plumb line if it hangs from one point."""
    rendered = []

    def fake(items, path, **kw):
        rendered.append(path.name)
        Image.new("RGB", (4, 4)).save(path)

    monkeypatch.setattr(render, "render", fake)
    paths = {p.name for p in render.all_images(CHARMS, tmp_path)}
    for c in CHARMS:
        views = {"front", "back", "edge", "flat"} | ({"hang"} if wear.layout(c).pivot else set())
        assert {f"{c.name}_{v}.png" for v in views} <= paths
        assert (f"{c.name}_hang.png" in paths) == (c.wear == "eyelet" or c.name == "moka_magnet")
    for name in ("tag_one_line_counter", "tag_two_lines_counter", "moka_counter",
                 "pocket_gauge", "clip_gauge"):
        assert {f"{name}_{v}.png" for v in ("front", "back", "edge")} <= paths
    assert all((tmp_path / "render" / p).is_file() for p in paths)
    assert len(rendered) == 3 * (len(CHARMS) + 5)


def test_hang_preview_drops_the_plumb_line_from_where_it_hangs(tmp_path):
    """The line starts at the top of the eyelet hole (or the middle of the lone magnet) and
    passes through the mark of the centre of mass."""
    for name in ("tag_two_lines_eyelet", "moka_magnet"):
        c = VARIANTS[name]
        path = render.hang_preview(c, tmp_path / f"{name}.png")
        img = np.array(Image.open(path).convert("RGB"))
        plumb = np.all(img == ImageColor.getrgb(PLUMB), axis=2)
        lay = wear.layout(c)
        x, y, r = lay.pivot
        to_px = render._to_px(lay.bands[0].bounds, 12.0)
        col = round(to_px(x, y)[0])
        rows = np.nonzero(plumb[:, col])[0]
        # the line runs without a break down to the bottom (the magnet's circle, drawn
        # around its top, crosses the column apart from it)
        start = rows[-1]
        while start - 1 in rows:
            start -= 1
        assert rows[-1] - start > 100 and abs(start - round(to_px(x, y + r)[1])) <= 2
        cx, cy = wear.mass_centre(c)
        assert abs(round(to_px(cx, cy)[0]) - col) <= 1
