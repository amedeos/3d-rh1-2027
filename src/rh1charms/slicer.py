"""Optional step with the PrusaSlicer CLI: slice the 3MF plates and turn them into projects.

Run `rh1charms export` first, then `rh1charms slice` (or `python -m rh1charms.slicer`).

For every plate in out/3mf it:
1. slices the plate with the Prusa MK4 profiles and reports the print time and filament,
   and checks that every M600 is there exactly where the design wants it (plan.json,
   written by export.py), that the 3MF gives each one the design's colour, that nothing
   needs support (a second slice with automatic supports on must create no support at
   all), and that every ceiling the design lists (the pocket roofs, the clip channel)
   prints as a bridge at its height: the support probe leaves bridges out, so without this
   check it could never fail on them;
2. writes a PrusaSlicer project to 3mf/projects/: the same plate plus the full
   print configuration, so the MK4 settings and the colour change load with one click.
   The project's filament colour is the plate's start filament (plan.json, passed with
   --filament-colour): PrusaSlicer ignores the object colours of a 3MF and shows the
   layers before the first M600 in the colour of the filament profile (#FF8000, orange,
   for Prusament PETG). So the GUI marks the filament preset as modified. A slice of the
   project checks that the CLI reads the colour back; what the GUI shows cannot be
   checked without a display.

PrusaSlicer writes its complete configuration at the end of every G-code file, in the
same "; key = value" format that it stores inside project 3MF files. We take it from
there, because the CLI cannot export projects on a machine without a display.

Set PRUSA_SLICER to the command if `prusa-slicer` is not on the PATH, for example
PRUSA_SLICER="flatpak run com.prusa3d.PrusaSlicer". The MK4 profiles must be installed
in PrusaSlicer (Configuration Wizard), or pass --datadir in PRUSA_SLICER.
"""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from .export import PLAN
from .filaments import FILAMENTS, MATERIAL
from .params import OUT

PRINTER = "Original Prusa MK4 Input Shaper 0.4 nozzle"
PRINT = "0.20mm STRUCTURAL @MK4IS 0.4"  # matches params.LAYER / LINE_W


def profiles() -> dict[str, str]:
    return {"--printer-profile": PRINTER, "--print-profile": PRINT,
            "--material-profile": MATERIAL}


CONFIG_ENTRY = "Metadata/Slic3r_PE.config"
M600_ENTRY = "Metadata/Prusa_Slicer_custom_gcode_per_print_z.xml"


def prusaslicer_command() -> list[str]:
    if os.environ.get("PRUSA_SLICER"):
        return shlex.split(os.environ["PRUSA_SLICER"])
    for name in ("prusa-slicer", "PrusaSlicer"):
        if shutil.which(name):
            return [name]
    raise FileNotFoundError("PrusaSlicer not found: install it or set PRUSA_SLICER")


# The MK4 profiles only build supports inside support enforcers, so a normal slice can
# never show a missing support. This extra slice turns automatic supports on (bridges
# excluded): every support extrusion it creates is an overhang that needs fixing.
# The profile widens the first layer of every support by 3 mm (raft_first_layer_expansion).
# Under a free edge of the clip channel's ceiling (where the ribbon goes in), the support
# generator trims its column to nothing, but the widened first layer still left a pad on
# the bed that supports nothing (the two-line clip tag). A real support column still prints
# its own first layer without the expansion, so the probe turns the expansion off.
AUTO_SUPPORT = ["--support-material", "--support-material-auto", "--dont-support-bridges",
                "--raft-first-layer-expansion", "0"]


def slice_plate(cmd: list[str], plate: Path, gcode: Path, profile: bool = True,
                extra: tuple[str, ...] = ()) -> None:
    """Slice to plain-text G-code (so we can read it). profile=False: use the 3MF's config."""
    args = [a for kv in profiles().items() for a in kv] if profile else []
    result = subprocess.run([*cmd, *args, *extra, "--no-binary-gcode", "--export-gcode",
                             "-o", str(gcode), str(plate)], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", check=False)
    if result.returncode or not gcode.is_file():
        raise RuntimeError(f"slicing {plate.name} failed:\n{result.stdout}\n{result.stderr}")


def summary(gcode: Path) -> dict:
    text = gcode.read_text(encoding="utf-8", errors="replace")

    def value(key: str) -> str:
        m = re.search(rf"^; {re.escape(key)} = (.*)$", text, re.MULTILINE)
        return m.group(1).strip() if m else "?"

    m600_z = [float(z) for z in re.findall(r"^;Z:([\d.]+)\n(?:(?!;Z:).*\n)*?M600", text, re.MULTILINE)]
    return {
        "m600_z": m600_z,
        "bridge_z": bridge_layers(text),
        "time": value("estimated printing time (normal mode)"),
        "filament_g": value("filament used [g]"),
        "m600": len(re.findall(r"^M600", text, re.MULTILINE)),
        "support_lines": text.count(";TYPE:Support material"),
        "printer": value("printer_settings_id"),
        "colour": value("filament_colour"),
    }


def bridge_layers(text: str) -> list[float]:
    """print_z of every layer that prints bridge infill, in order."""
    found, z = [], None
    for line in text.splitlines():
        if line.startswith(";Z:"):
            z = round(float(line[3:]), 2)
        elif line.startswith(";TYPE:Bridge infill") and z is not None and z not in found:
            found.append(z)
    return found


def config_from_gcode(gcode: Path) -> str:
    """The print configuration block that PrusaSlicer appends to every G-code file."""
    lines = gcode.read_text(encoding="utf-8", errors="replace").splitlines()
    try:
        start = lines.index("; prusaslicer_config = begin")
        end = lines.index("; prusaslicer_config = end")
    except ValueError:
        raise ValueError(f"{gcode.name}: PrusaSlicer wrote no configuration block") from None
    header = lines[0] if lines[0].startswith("; generated by PrusaSlicer") else ""
    body = [line for line in lines[start + 1:end] if line.startswith("; ")]
    # we sliced to text only to read the file; MK4 users normally get binary G-code
    body = ["; binary_gcode = 1" if line.startswith("; binary_gcode =") else line
            for line in body]
    return "\n".join([header, *body]) + "\n"


Change = tuple[float, str]  # (print_z, '#RRGGBB'): an M600 and the colour that follows it


def stored_colour_changes(plate: Path) -> list[Change]:
    """The colour changes written into a 3MF plate (empty list if there are none)."""
    with zipfile.ZipFile(plate) as z:
        if M600_ENTRY not in z.namelist():
            return []
        xml = z.read(M600_ENTRY).decode()
    return [(float(z), c.upper())
            for z, c in re.findall(r'print_z="([\d.]+)"[^>]*?\scolor="([^"]*)"', xml)]


STALE = "export it again, or delete the plate if no export makes it any more"


def plan_entry(plan: dict, name: str) -> tuple[str | None, list[Change] | None,
                                                list[float] | None, list[str]]:
    """What the design (plan.json) wants for a plate: the colour it starts with, its colour
    changes (colours as '#RRGGBB' like PrusaSlicer writes them) and the heights that must
    print as bridges (None where plan.json does not say), and the problems."""
    entry = plan.get(name)
    if entry is None:
        return None, None, None, [f"not in plan.json: {STALE}"]
    if not (isinstance(entry, dict) and {"start", "changes", "bridges"} <= entry.keys()):
        return None, None, None, ["incomplete entry in plan.json: export again"]
    start, changes = entry["start"], entry["changes"]
    unknown = sorted({f for f in [start, *(c for _, c in changes)] if f not in FILAMENTS})
    if unknown:
        return None, None, None, [f"unknown filament {', '.join(unknown)} in plan.json"]
    return (FILAMENTS[start].upper(), [(round(z, 2), FILAMENTS[c].upper()) for z, c in changes],
            [round(z, 2) for z in entry["bridges"]], [])


def _changes_text(changes: list[Change]) -> str:
    return ", ".join(f"Z {z:.2f} -> {c}" for z, c in changes) or "none"


def make_project(plate: Path, config: str, out: Path) -> None:
    """The plate with `config` as its print config. A plate saved from the PrusaSlicer GUI
    already has a config: it is replaced, not added as a second entry with the same name."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(plate) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            if item.filename != CONFIG_ENTRY:
                dst.writestr(item, src.read(item))
        dst.writestr(CONFIG_ENTRY, config)


def main(folder: Path = OUT / "3mf") -> int:
    cmd = prusaslicer_command()
    plates = sorted(folder.glob("*.3mf"))
    if not plates or not (folder / PLAN).is_file():
        print(f"no plates in {folder}: run `rh1charms export` first")
        return 1
    plan = json.loads((folder / PLAN).read_text(encoding="utf-8"))
    problems = 0
    with tempfile.TemporaryDirectory() as tmp:
        for plate in plates:
            # the start colour and the colour changes come from the design (plan.json), not
            # from the 3MF under check
            start, changes, ceilings, issues = plan_entry(plan, plate.stem)
            gcode = Path(tmp) / f"{plate.stem}.gcode"
            slice_plate(cmd, plate, gcode, extra=("--filament-colour", start) if start else ())
            info = summary(gcode)
            probe = Path(tmp) / f"{plate.stem}.supports.gcode"
            slice_plate(cmd, plate, probe, extra=tuple(AUTO_SUPPORT))
            support = summary(probe)["support_lines"]
            if support:
                issues.append(f"needs support ({support} extrusions)")
            if changes is not None:  # None: plan.json cannot tell, the problem says why
                stored = stored_colour_changes(plate)
                if stored != changes:
                    issues.append(f"3MF stores {_changes_text(stored)}, "
                                  f"the design says {_changes_text(changes)}")
                expected = [z for z, _ in changes]
                if info["m600"] != len(expected) or info["m600_z"] != expected:
                    issues.append(f"expected M600 at {expected}, found {info['m600']} "
                                  f"at {info['m600_z']}")
            missing = [z for z in ceilings or [] if z not in info["bridge_z"]]
            if missing:
                issues.append(f"no bridge infill at Z {missing} (bridges at "
                              f"{info['bridge_z'] or 'none'})")
            project = folder / "projects" / plate.name
            make_project(plate, config_from_gcode(gcode), project)
            # the project alone (no profile options) must give the same printer and the
            # design's start colour
            check = Path(tmp) / f"{plate.stem}.check.gcode"
            slice_plate(cmd, project, check, profile=False)
            loaded = summary(check)
            if loaded["printer"] != info["printer"]:
                issues.append("project does not carry the printer settings")
            if start and loaded["colour"].upper() != start:
                issues.append(f"project starts in {loaded['colour']}, the design in {start}")
            problems += bool(issues)
            print(f"{plate.stem:44s} {info['time']:>12s} {info['filament_g']:>7s} g  "
                  f"M600 at Z {info['m600_z'] or '-'}  bridges at Z {ceilings or '-'}  "
                  f"{'OK' if not issues else '; '.join(issues)}")
    print(f"\nProjects written to {folder / 'projects'} ({PRINTER}, {PRINT}, {MATERIAL})")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])) if len(sys.argv) > 1 else main())
