"""Plates: bed fit, copies, colour changes in the 3MF, and plan.json."""

import json
import re
import zipfile
from itertools import combinations

import pytest
from conftest import CHARMS, MAGNETS

from rh1charms import wear
from rh1charms.charms import VARIANTS
from rh1charms.export import (
    BED,
    PLAN,
    charm_plate_name,
    counter_plate_name,
    export_all,
    gauge_plate_name,
    m600_metadata,
    max_copies,
    plate_plan,
    plates,
    write_3mf,
)
from rh1charms.magnets import GAUGE
from rh1charms.slicer import M600_ENTRY

PLATES = {1: plates(CHARMS), 6: plates(CHARMS, copies=6)}
ALL = [(n, name) for n in PLATES for name in PLATES[n]]


@pytest.mark.parametrize("n, name", ALL, ids=[f"{name}-x{n}" for n, name in ALL])
def test_plate_fits_the_bed_without_overlaps(n, name):
    objects, _, _ = PLATES[n][name]
    boxes = [part.bounding_box() for _, part, _ in objects]
    for bb in boxes:
        assert bb.min.X >= 0 and bb.min.Y >= 0 and abs(bb.min.Z) < 1e-3
        assert bb.max.X <= BED[0] and bb.max.Y <= BED[1] and bb.max.Z <= BED[2]
    for a, b in combinations(boxes, 2):
        assert a.max.X < b.min.X or b.max.X < a.min.X or a.max.Y < b.min.Y or b.max.Y < a.min.Y


@pytest.mark.parametrize("n, name", ALL, ids=[f"{name}-x{n}" for n, name in ALL])
def test_plate_is_centred_on_the_bed(n, name):
    # PrusaSlicer arranges around the middle of the bed; the plates start there too
    objects, _, _ = PLATES[n][name]
    boxes = [part.bounding_box() for _, part, _ in objects]
    x0, x1 = min(b.min.X for b in boxes), max(b.max.X for b in boxes)
    y0, y1 = min(b.min.Y for b in boxes), max(b.max.Y for b in boxes)
    assert (x0 + x1) / 2 == pytest.approx(BED[0] / 2, abs=0.5)
    assert (y0 + y1) / 2 == pytest.approx(BED[1] / 2, abs=0.5)


def test_copies_of_one_variant_share_a_plate():
    """One M600 serves the whole plate: N copies of one charm, the same N counter plates,
    one gauge. Every variant has its own plate (different band heights)."""
    six = PLATES[6]
    for c in CHARMS:
        objects, changes, _ = six[charm_plate_name(c)]
        assert [name for name, _, _ in objects] == [f"{c.name} {k}" for k in range(1, 7)]
        assert changes == wear.colour_changes(c)
    for c in MAGNETS:
        objects, changes, _ = six[counter_plate_name(c)]
        assert len(objects) == 6 and changes == []
    objects, changes, _ = six[gauge_plate_name("white")]
    assert [name for name, _, _ in objects] == [GAUGE] and changes == []
    assert len(six) == len(CHARMS) + len(MAGNETS) + 1


def test_too_many_copies_is_an_error_with_the_largest_number():
    c = VARIANTS["tag_one_line_eyelet"]
    w, h, _ = wear.layout(c).size
    most = max_copies(w, h)
    plates([c], copies=most)
    with pytest.raises(ValueError, match=f"do not fit .* at most {most}"):
        plates([c], copies=most + 1)


def test_export_stops_before_writing_when_the_copies_do_not_fit(tmp_path):
    with pytest.raises(ValueError, match="do not fit"):
        export_all(tmp_path, [VARIANTS["moka_magnet"], VARIANTS["tag_one_line_eyelet"]],
                   copies=99)
    assert not any(tmp_path.iterdir())


def test_plan_gives_start_filament_colour_changes_and_bridges():
    """The start filament goes into the project's filament colour; the bridges are the
    first layer over the pocket roofs (2.40) and over the clip channel (3.00)."""
    plan = plate_plan(PLATES[1])
    for c in CHARMS:
        entry = plan[charm_plate_name(c)]
        assert entry["start"] == c.bands[0] == "white"
        assert entry["changes"] == [[round(z, 2), f] for z, f in wear.colour_changes(c)]
        assert entry["bridges"] == {"eyelet": [], "magnet": [2.4], "clip": [3.0]}[c.wear]
    for c in MAGNETS:
        assert plan[counter_plate_name(c)] == {"start": "white", "changes": [], "bridges": []}
    assert plan[gauge_plate_name("white")] == {"start": "white", "changes": [],
                                               "bridges": [2.4]}


def test_plate_without_one_start_filament_is_refused():
    with pytest.raises(ValueError, match="must start in one filament, not red, white"):
        plate_plan({"p": ([("a", None, "white"), ("b", None, "red")], [], [])})
    with pytest.raises(ValueError, match="has no objects"):
        plate_plan({"p": ([], [], [])})


def test_m600_metadata_lists_every_change():
    xml = m600_metadata([(1.4, "red"), (2.2, "green")])
    assert re.findall(r'print_z="([\d.]+)"', xml) == ["1.40", "2.20"]
    assert xml.count('gcode="M600"') == 2
    # the PrusaSlicer 2.9 GUI ignores colour changes without a bed index
    assert xml.count('bed_idx="0"') == 3 and xml.count("<mode ") == 1


@pytest.mark.parametrize("name", ["moka_magnet_white-red-green-black",
                                  "tag_two_lines_clip_white-red-green",
                                  "tag_one_line_counter_white", "pocket_gauge_white"])
def test_3mf_content(tmp_path, name):
    objects, changes, _ = PLATES[6][name]
    path = tmp_path / f"{name}.3mf"
    write_3mf(path, objects, changes)
    z = zipfile.ZipFile(path)
    model = z.read("3D/3dmodel.model").decode()
    assert 'unit="millimeter"' in model
    assert re.findall(r'<object [^>]*name="([^"]*)"', model) == [n for n, _, _ in objects]
    if not changes:
        assert M600_ENTRY not in z.namelist()
    else:
        xml = z.read(M600_ENTRY).decode()
        assert re.findall(r'print_z="([\d.]+)"', xml) == [f"{zz:.2f}" for zz, _ in changes]


def test_plan_is_merged_across_exports(tmp_path):
    """Exporting one charm keeps the plates of the charms exported before."""
    plan_path = tmp_path / "3mf" / PLAN
    plan_path.parent.mkdir(parents=True)
    earlier = {"start": "white", "changes": [[1.4, "red"]], "bridges": []}
    plan_path.write_text(json.dumps({"earlier_plate": earlier}), encoding="utf-8")
    c = VARIANTS["moka_magnet"]
    report = export_all(tmp_path, [c], copies=2)
    assert not any(report.values())
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["earlier_plate"] == earlier
    for name, entry in plate_plan(plates([c], copies=2)).items():
        assert plan[name] == entry
        assert (tmp_path / "3mf" / f"{name}.3mf").is_file()
    assert {p.name for p in (tmp_path / "stl").iterdir()} == {
        "moka_magnet.stl", "moka_counter.stl", "pocket_gauge.stl"}
