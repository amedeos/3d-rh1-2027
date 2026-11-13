"""Export the printable parts: STL files and ready-made 3MF plates.

    out/stl/             one STL per part, already in its print position
    out/3mf/             one 3MF per print job ("plate"), centred on the Prusa MK4 bed
    out/3mf/plan.json    each plate's start filament, colour changes and bridges
    out/3mf/projects/    PrusaSlicer projects (written by slicer.py)

One M600 serves the whole plate, so a plate holds `copies` of one charm with one way of
wearing it: different variants have different band heights. A magnet charm brings its
counter plate (the same number of copies) and the pocket gauge (once), a clip charm the
clip gauge (once): they are plates in one colour. A charm plate carries all its colour
changes as PrusaSlicer metadata, so they are already set when you open the file.

plan.json is written from the design: slicer.py checks the real G-code and the projects
against it, not against the 3MF it is checking. "bridges" lists the print_z of the first
layer over every ceiling (pocket roofs, the clip channel): the slice must print it as a
bridge there.

Exits with status 1 if any part fails a check, so scripts and CI can rely on it.
"""

import json
import math
import tempfile
import zipfile
from pathlib import Path

import trimesh
from build123d import Color, Mesher, Part, Pos, export_stl

from . import params as P
from .charms import Charm
from .filaments import FILAMENTS
from .magnets import CLIP_GAUGE, GAUGE, extras
from .wear import bridges, colour_changes, layout, make_charm

BED = P.BED
STL_TOLERANCE = (0.01, 0.1)  # linear (mm), angular (rad)
PLAN = "plan.json"
GAP = 6.0  # mm between the copies on a plate

# a print job before it is laid out: (part, start filament, colour changes, bridges)
Job = tuple[Part, str, list[tuple[float, str]], list[float]]
# a plate: ([(object name, part on the bed, colour)], colour changes, bridges)
Plate = tuple[list[tuple[str, Part, str]], list[tuple[float, str]], list[float]]


def charm_plate_name(c: Charm) -> str:
    return f"{c.name}_{'-'.join(c.bands)}"


def single_plate_name(name: str, colour: str) -> str:
    """The plate of a part in one colour: a counter plate or a gauge."""
    return f"{name}_{colour}"


def counter_plate_name(c: Charm) -> str:
    return single_plate_name(c.counter_name, c.plate_colour)


def gauge_plate_name(colour: str) -> str:
    return single_plate_name(GAUGE, colour)


# the parts that come once on their plate, whatever the copies: (bridges, bodies)
GAUGES = {GAUGE: ([P.layer_top(P.POCKET_DEPTH)], 1),
          CLIP_GAUGE: ([P.layer_top(P.CLIP_Z)], len(P.CLIP_GAUGE_SLITS))}


def bodies(name: str) -> int:
    """How many separate bodies a part has: the clip gauge one per piece, the rest one."""
    return GAUGES[name][1] if name in GAUGES else 1


def jobs(charms: list[Charm]) -> dict[str, tuple[str, Job]]:
    """part name -> (plate name, job): every charm, the counter plate of every magnet charm,
    the pocket gauge once if any charm has magnets, the clip gauge once if any has a clip."""
    out = {}
    for c in charms:
        out[c.name] = (charm_plate_name(c), (make_charm(c), c.bands[0], colour_changes(c),
                                             bridges(c)))
    for name, colour, build in extras(charms):  # the counter plates and the gauges
        ceilings = list(GAUGES[name][0]) if name in GAUGES else []
        out[name] = (single_plate_name(name, colour), (build(), colour, [], ceilings))
    return out


def _on_bed(part: Part, x_min: float, y_min: float) -> Part:
    """Move a part (already lying on z=0) so its footprint starts at (x_min, y_min)."""
    bb = part.bounding_box()
    return Pos(x_min - bb.min.X, y_min - bb.min.Y, 0) * part


def max_copies(w: float, h: float, gap: float = GAP) -> int:
    """How many parts of this footprint fit on the bed in a grid."""
    return math.floor((BED[0] + gap) / (w + gap)) * math.floor((BED[1] + gap) / (h + gap))


def grid(name: str, part: Part, copies: int, gap: float = GAP) -> list[Part]:
    """`copies` of a part in a grid, row by row, centred on the bed."""
    bb = part.bounding_box()
    w, h = bb.size.X, bb.size.Y
    most = max_copies(w, h, gap)
    if copies < 1:
        raise ValueError(f"copies must be at least 1, not {copies}")
    if copies > most:
        raise ValueError(f"{copies} copies of {name} ({w:.0f} x {h:.0f} mm) do not fit on the "
                         f"{BED[0]:.0f} x {BED[1]:.0f} mm bed: at most {most}")
    cols = min(copies, math.floor((BED[0] + gap) / (w + gap)))
    rows = math.ceil(copies / cols)
    x0 = (BED[0] - (cols * w + (cols - 1) * gap)) / 2
    y0 = (BED[1] - (rows * h + (rows - 1) * gap)) / 2
    return [_on_bed(part, x0 + (i % cols) * (w + gap), y0 + (rows - 1 - i // cols) * (h + gap))
            for i in range(copies)]


def plates(charms: list[Charm], copies: int = 1) -> dict[str, Plate]:
    """plate name -> plate. The charms and counter plates come `copies` times, the gauges
    once. A plate that does not fit stops everything before any file is written."""
    out = {}
    for name, (plate, (part, colour, changes, ceilings)) in jobs(charms).items():
        n = 1 if name in GAUGES else copies
        placed = grid(name, part, n)
        objects = [(name if n == 1 else f"{name} {k + 1}", p, colour)
                   for k, p in enumerate(placed)]
        out[plate] = (objects, changes, ceilings)
    return out


def plate_plan(all_plates: dict[str, Plate]) -> dict[str, dict]:
    """plate name -> {"start": filament, "changes": [[print_z, filament], ...], "bridges":
    [print_z, ...]} (JSON friendly). A plate has one filament until its first M600, so its
    objects must all start in it."""
    plan = {}
    for name, (objects, changes, ceilings) in all_plates.items():
        if not objects:
            raise ValueError(f"plate {name} has no objects")
        starts = sorted({colour for _, _, colour in objects})
        if len(starts) != 1:
            raise ValueError(f"plate {name}: the objects must start in one filament, "
                             f"not {', '.join(starts)}")
        plan[name] = {"start": starts[0], "changes": [[round(z, 2), f] for z, f in changes],
                      "bridges": [round(z, 2) for z in ceilings]}
    return plan


def check(part: Part, expected_bodies: int = 1) -> list[str]:
    """Problems with the CAD solid itself (empty list = fine). A part is one body, but for
    the clip gauge (`bodies`)."""
    problems = []
    bb = part.bounding_box()
    if not part.is_valid:
        problems.append("invalid solid")
    if abs(bb.min.Z) > 1e-3:
        problems.append(f"not on the bed (zmin={bb.min.Z:.3f})")
    if bb.size.X > BED[0] or bb.size.Y > BED[1] or bb.size.Z > BED[2]:
        problems.append(f"larger than the bed {bb.size}")
    if len(part.solids()) != expected_bodies:
        problems.append(f"{len(part.solids())} separate bodies, not {expected_bodies}")
    return problems


def write_stl(part: Part, path: Path) -> list[str]:
    """Write the STL and check the mesh that a slicer will actually load."""
    export_stl(part, path, tolerance=STL_TOLERANCE[0], angular_tolerance=STL_TOLERANCE[1])
    mesh = trimesh.load(path)
    return [] if mesh.is_watertight else ["mesh not watertight"]


def mesh_problems(part: Part) -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        return write_stl(part, Path(tmp) / "part.stl")


def _named(part: Part, name: str, colour: str) -> Part:
    part = part.moved(Pos())  # a copy: the cached parts must not be changed
    part.label = name
    part.color = Color(FILAMENTS[colour])
    return part


def m600_metadata(changes: list[tuple[float, str]]) -> str:
    """PrusaSlicer's colour-change list, as stored inside its 3MF files."""
    # bed_idx: PrusaSlicer 2.9 keeps colour changes per bed (multiple beds); without it the
    # GUI silently drops them. Older versions ignore the attribute.
    codes = "".join(
        f'<code bed_idx="0" print_z="{z:.2f}" type="0" extruder="1" '
        f'color="{FILAMENTS[c]}" extra="" gcode="M600"/>\n' for z, c in changes)
    return ('<?xml version="1.0" encoding="utf-8"?>\n<custom_gcodes_per_print_z>\n'
            f'{codes}<mode bed_idx="0" value="SingleExtruder"/>\n'
            '</custom_gcodes_per_print_z>\n')


def write_3mf(path: Path, objects: list[tuple[str, Part, str]],
              changes: list[tuple[float, str]] | None = None) -> None:
    mesher = Mesher()
    for name, part, colour in objects:
        mesher.add_shape(_named(part, name, colour), linear_deflection=STL_TOLERANCE[0],
                         angular_deflection=STL_TOLERANCE[1])
    mesher.write(str(path))
    if changes:
        with zipfile.ZipFile(path, "a", zipfile.ZIP_DEFLATED) as z:
            z.writestr("Metadata/Prusa_Slicer_custom_gcode_per_print_z.xml",
                       m600_metadata(changes))


def describe(c: Charm) -> str:
    """One line about a charm: size, bands, font size and what sets it, colour changes, and
    how it is worn (`rh1charms list`, and the end of `export`)."""
    lay = layout(c)
    w, h, t = lay.size
    parts = [f"{c.name:22s} {w:5.1f} x {h:4.1f} x {t:.1f} mm", " -> ".join(c.bands)]
    if lay.art.font_size:
        bound = f" (smallest: {lay.art.size_bound})" if lay.art.size_bound else " (forced)"
        parts.append(f"font {lay.art.font_size:g} mm{bound}")
    parts.append("M600 at " + ", ".join(f"{z:.2f} {f}" for z, f in colour_changes(c)))
    if lay.pockets:
        parts.append(f"{len(lay.pockets)} x {c.pocket_d:g} mm pocket, counter plate "
                     f"{c.counter_name} ({c.plate_colour})")
    if lay.clip is not None:
        parts.append(f"clip for a {c.lanyard_w:g} mm lanyard, channel x "
                     f"{lay.clip.channel[0]:.1f}..{lay.clip.channel[1]:.1f} mm")
    if lay.tilt is not None:
        parts.append(f"hangs {lay.tilt:.2f}° off upright")
    return "; ".join(parts)


def _read_plan(path: Path) -> dict:
    """The plan.json of earlier exports (empty if there is none). A damaged one stops the
    export before it writes anything: it would be merged into, and slice would trust it."""
    if not path.is_file():
        return {}
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise ValueError(f"{path} is damaged ({e}): delete it and export again") from None
    if not isinstance(plan, dict):  # a ValueError: the command shows it as a clear message
        raise ValueError(  # noqa: TRY004
            f"{path} is not a plan written by export: delete it and export again")
    return plan


def export_all(out: Path, charms: list[Charm], copies: int = 1) -> dict[str, list[str]]:
    """STLs into out/stl, plates and plan.json into out/3mf; return the problems of every
    part. Every plate is laid out (and checked against the bed) before any file is written."""
    all_plates = plates(charms, copies)
    new_plan = plate_plan(all_plates)
    parts = {name: job[0] for name, (_, job) in jobs(charms).items()}  # cached: no rebuild
    stl_dir, mf_dir = out / "stl", out / "3mf"
    plan = _read_plan(mf_dir / PLAN)  # keep the plates of charms exported earlier
    stl_dir.mkdir(parents=True, exist_ok=True)
    mf_dir.mkdir(parents=True, exist_ok=True)
    report = {}
    for name, part in parts.items():
        problems = check(part, bodies(name)) + write_stl(part, stl_dir / f"{name}.stl")
        report[name] = problems
        status = "OK" if not problems else "; ".join(problems)
        print(f"{name:24s} {part.volume / 1000:6.2f} cm3  {status}")
    for name, (objects, changes, _) in all_plates.items():
        write_3mf(mf_dir / f"{name}.3mf", objects, changes)
        note = ", ".join(f"Z {z:.2f} -> {c}" for z, c in changes)
        print(f"{name + '.3mf':48s} {len(objects):2d} x  "
              f"{f'M600 at {note}' if note else 'no colour change'}")
    plan.update(new_plan)
    (mf_dir / PLAN).write_text(json.dumps(plan, indent=1, sort_keys=True) + "\n",
                               encoding="utf-8")
    for c in charms:
        print(describe(c))
    return report
