"""The rh1charms command: README examples, the selection of charms, and clear errors."""

import re
import shlex
from pathlib import Path

import pytest

import rh1charms
from rh1charms import wear
from rh1charms.charms import VARIANTS

README = Path(__file__).resolve().parents[1] / "README.md"


def readme_commands() -> list[list[str]]:
    """Every `uv run rh1charms list|export|render ...` line in the README's code blocks and
    in the command's own help text."""
    blocks = re.findall(r"```sh\n(.*?)```", README.read_text(encoding="utf-8"), re.DOTALL)
    lines = [re.sub(r"\s#\s.*$", "", line).strip()
             for b in [*blocks, rh1charms.USAGE] for line in b.splitlines()]
    return [shlex.split(line)[3:] for line in lines
            if re.match(r"uv run rh1charms (list|export|render)\b", line)]


@pytest.fixture
def captured(monkeypatch, tmp_path):
    """Run the command up to the geometry (no files written), in a scratch folder."""
    monkeypatch.chdir(tmp_path)
    seen = []
    monkeypatch.setattr("rh1charms.export.export_all",
                        lambda out, charms, copies: seen.extend(charms) or {})
    monkeypatch.setattr("rh1charms.render.all_images", lambda charms: seen.extend(charms) or [])
    return seen


def _run(argv) -> int:
    with pytest.raises(SystemExit) as e:
        rh1charms.main(argv)
        raise SystemExit(0)
    return e.value.code


@pytest.mark.parametrize("argv", readme_commands(), ids=" ".join)
def test_readme_examples_work(argv, captured):
    assert _run(argv) == 0
    for c in captured:
        wear.layout(c)


def test_readme_has_examples():
    assert len(readme_commands()) >= 6


def test_list_shows_every_variant_with_its_font_size(capsys):
    assert _run(["list"]) == 0
    lines = {line.split()[0]: line for line in capsys.readouterr().out.splitlines()}
    assert set(lines) == set(VARIANTS)
    assert "font 8.3 mm (smallest: the gap in '@')" in lines["tag_one_line_eyelet"]
    assert "M600 at 4.20 red, 5.00 green" in lines["tag_two_lines_clip"]
    assert "counter plate moka_counter" in lines["moka_magnet"]
    assert ("font 10 mm (smallest: 6.4 mm, the gap in 's'; the stream takes 10 mm)"
            in lines["moka_pour_eyelet"])
    assert "2 x 8.2 mm pocket, counter plate moka_pour_counter" in lines["moka_pour_magnet"]
    assert "M600 at 4.20 red, 5.40 green" in lines["moka_pour_clip"]
    assert "RH1 (red) and 2027 (green) on it at" in lines["moka_pour_rh1_clip"]
    assert "backing plate 26.8 x" in lines["moka_pour_clip"]


def test_an_override_that_makes_two_charms_one_lists_it_once(capsys):
    """--set layout=pour turns moka_eyelet into moka_pour_eyelet, which `moka` names too."""
    assert _run(["list", "moka", "--set", "layout=pour"]) == 0
    names = [line.split()[0] for line in capsys.readouterr().out.splitlines()]
    assert names == ["moka_pour_eyelet", "moka_pour_magnet", "moka_pour_clip"]


@pytest.mark.parametrize("names, wear_, layout, expected", [
    ([], None, None, list(VARIANTS)),
    (["moka"], None, None, ["moka_eyelet", "moka_magnet", "moka_pour_eyelet",
                            "moka_pour_magnet", "moka_pour_clip", "moka_pour_rh1_clip"]),
    ([], "clip", None, ["tag_one_line_clip", "tag_two_lines_clip", "moka_pour_clip",
                        "moka_pour_rh1_clip"]),
    (["moka"], "clip", None, ["moka_pour_clip", "moka_pour_rh1_clip"]),  # the layouts with it
    (["moka"], "eyelet", "pour_rh1", ["moka_pour_rh1_eyelet"]),  # none has it: it fails later
    ([], None, "pour_rh1", ["moka_pour_rh1_clip"]),
    (["moka_clip"], None, None, ["moka_clip"]),  # asked for by name: it fails with the reason
    (["tag"], None, "two_lines", ["tag_two_lines_eyelet", "tag_two_lines_magnet",
                                  "tag_two_lines_clip"]),
    ([], None, "pour", ["moka_pour_eyelet", "moka_pour_magnet", "moka_pour_clip"]),
    (["tag_one_line_magnet", "moka", "tag"], "magnet", None,
     ["tag_one_line_magnet", "moka_magnet", "moka_pour_magnet", "tag_two_lines_magnet"]),
])
def test_selection(names, wear_, layout, expected):
    assert rh1charms.select(names, wear_, layout) == expected


@pytest.mark.parametrize("argv, message", [
    (["export", "moka_clip"], "too narrow for a lanyard clip"),
    (["render", "moka_clip"], "too narrow for a lanyard clip"),
    (["export", "tag_one_line_eyelet", "--set", "font_size=8"],
     "font_size 8 mm is too small: the narrowest gap (in '@') is 0.438 mm"),
    (["export", "tag_one_line_eyelet", "--copies", "99"], "at most 14"),
    (["export", "tag", "--copies", "two"], "--copies needs a whole number"),
    (["export", "tag", "--set", "band_t=0.7"], "layers"),
    (["export", "--wear", "hook"], "unknown wear"),
    (["export", "moka", "--layout", "two_lines"], "--layout two_lines is not a layout of the moka"),
    (["export", "tag", "--layout", "pour"], "--layout pour is not a layout of the tag"),
    (["list", "moka_pour_eyelet", "--bands", "white,red,green,black"], "does not use black"),
    (["export", "moka_pour_eyelet", "--set", "text=one\\ntwo"], "one line"),
    (["export", "moka_pour_eyelet", "--set", "text="], "the text is empty"),
    (["list", "moka_pour", "--set", "red_t=1.1"], "unknown charm"),
    (["list", "moka_pour_clip", "--set", "red_t=1.1"], "red_t = 1.1 is not a whole number"),
    (["list", "moka_pour_clip", "--bands", "red,white,green"], "red cannot print the body"),
    (["export", "tag", "--set", "text=caffè ☕"], "no glyph"),
    (["export", "tag", "--set", "nope=1"], "unknown parameter"),
    (["export", "teapot"], "unknown charm"),
    (["export", "tag", "--set", "tab_r=2.5"], "leaves a ring of 0.50 mm"),
    (["export", "tag", "--set", "magnet_clr=-0.1"], "magnet_clr"),
    (["export", "tag", "--set", "bands=white,red"], "uses green"),
    (["export", "tag", "--set"], "--set needs a value"),
    (["export", "tag", "--bands", ","], "bands needs at least one filament"),
    (["list", "tag", "--bands", "red,white,green"], "red cannot print the body"),
    (["list", "tag", "--set", "band_t=inf"], "band_t must be a number, not inf"),
    (["list", "tag", "--set", "font_size=nan"], "font_size must be a number, not nan"),
    (["list", "tag", "--set", "band_t=0.4004"], "is not a whole number of 0.2 mm layers"),
    (["export", "tag_two_lines_clip", "--set", "lanyard_w=57"], "cannot lie over the centre"),
    (["slice", "tag", "--copies", "3"], "slice takes no CHARM and no options"),
    (["frobnicate"], "unknown command"),
])
def test_clear_errors(argv, message, capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # nothing may be written into the real out/
    assert _run(argv) == 2
    assert message in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_slice_without_prusaslicer_is_a_clear_error(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PRUSA_SLICER", raising=False)
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert _run(["slice"]) == 2
    assert "PrusaSlicer not found" in capsys.readouterr().err


def test_damaged_plan_stops_the_export_before_it_writes(capsys, monkeypatch, tmp_path):
    """export merges into plan.json: a damaged one would be merged into and trusted by
    slice, so it stops the export first."""
    monkeypatch.chdir(tmp_path)
    plan = tmp_path / "out" / "3mf" / "plan.json"
    plan.parent.mkdir(parents=True)
    plan.write_text("{not json", encoding="utf-8")
    assert _run(["export", "moka_eyelet"]) == 2
    assert "plan.json is damaged" in capsys.readouterr().err
    assert sorted(p.name for p in plan.parent.iterdir()) == ["plan.json"]
    assert not (tmp_path / "out" / "stl").exists()


# runpy warns that it runs a module that is imported already: here that is the point
@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_render_module_takes_the_commands_arguments(captured, monkeypatch):
    """`python -m rh1charms.render tag --wear clip` selects like `rh1charms render`."""
    import runpy
    import sys

    monkeypatch.setattr(sys, "argv", ["render", "tag", "--wear", "clip"])
    runpy.run_module("rh1charms.render", run_name="__main__")
    assert [c.name for c in captured] == ["tag_one_line_clip", "tag_two_lines_clip"]
