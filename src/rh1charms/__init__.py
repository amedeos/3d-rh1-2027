"""Parametric, 3D-printable wearable charms for the Italian Consulting team at Red Hat's
RH1 2027: a name tag and a moka pot, in colour bands, with an eyelet, magnets or a clip."""

USAGE = """\
usage: rh1charms COMMAND [CHARM ...] [options]

commands:
  list      the charms: size, font size, colour bands and colour changes
  export    STL files and 3MF plates in out/stl and out/3mf; exit 1 on problems
  slice     slice the 3MF plates with the PrusaSlicer CLI: times, M600 and bridge
            checks, projects in out/3mf/projects
  render    PNG previews in out/render

CHARM is a variant (tag_one_line_eyelet, tag_two_lines_clip, moka_magnet, ...) or a
subject (tag, moka: all its variants). Without CHARM: every variant.

options (for list, export and render):
  --wear eyelet|magnet|clip      only this way of wearing it
  --layout one_line|two_lines    only this layout of the tag
  --copies N                     copies of the charm on each plate (export; default 1)
  --bands A,B,...                filaments from the bed up, e.g. --bands white,red,green
  --set KEY=VALUE                any parameter of charms.Charm, e.g. --set magnet_clr=0.3

examples:
  uv run rh1charms list
  uv run rh1charms export tag --wear clip --copies 6
  uv run rh1charms export tag_two_lines_magnet --copies 4 --set magnet_clr=0.3
  uv run rh1charms export moka --copies 12
  uv run rh1charms render tag --layout two_lines
  uv run rh1charms export tag --set text=consulting@roma:~$
"""


def _fail(message: str) -> None:
    import sys

    print(f"rh1charms: {message}\n\n{USAGE}", file=sys.stderr)
    sys.exit(2)


def select(names: list[str], wear: str | None, layout: str | None) -> list[str]:
    """The charm names that the arguments ask for. A subject gives all its default variants
    (with --wear: that one, even one it does not have by default, like the moka's clip,
    which then fails with the reason); --wear and --layout filter the variants named."""
    from .charms import DEFAULT_WEARS, LAYOUTS, SUBJECTS, WEARS, parse_name

    if wear is not None and wear not in WEARS:
        raise ValueError(f"unknown wear {wear!r}; choose from {', '.join(WEARS)}")
    if layout is not None and layout not in LAYOUTS:
        raise ValueError(f"unknown layout {layout!r}; choose from {', '.join(LAYOUTS)}")
    out = []
    for name in names or [s for s in SUBJECTS if not (layout and s != "tag")]:
        if name in SUBJECTS:
            if layout and name != "tag":
                raise ValueError(f"--layout is for the tag only, not the {name}")
            layouts = ([layout] if layout else list(LAYOUTS)) if name == "tag" else [""]
            wears = [wear] if (wear and names) else [
                w for w in DEFAULT_WEARS[name] if wear in (None, w)]
            out += [f"{name}_{lay}_{w}" if lay else f"{name}_{w}" for lay in layouts
                    for w in wears]
        else:
            _, lay, w = parse_name(name)
            if (wear and w != wear) or (layout and lay != layout):
                continue
            out.append(name)
    if not out:
        raise ValueError("no charm matches " + " ".join(
            names + [f"--wear {wear}"] * bool(wear) + [f"--layout {layout}"] * bool(layout)))
    return list(dict.fromkeys(out))  # in order, once each


def _charms(names: list[str], wear, layout, sets: list[tuple[str, str]]) -> list:
    """The charms asked for, each laid out once: a charm that cannot be built (the moka with
    a clip, a font size that is too small) stops the command before it writes anything."""
    from . import wear as W
    from .charms import charm, parse_value

    out = []
    for name in select(names, wear, layout):
        base = charm(name)
        c = charm(name, **{k: parse_value(base, k, v) for k, v in sets})
        W.layout(c)
        out.append(c)
    return out


def main(argv: list[str] | None = None) -> None:
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        print(USAGE)
        sys.exit(0)
    command, rest = args[0], args[1:]
    if command not in ("list", "export", "slice", "render"):
        _fail(f"unknown command {command!r}")
    names, sets, opts = [], [], {"--wear": None, "--layout": None, "--copies": "1"}
    while rest:
        a = rest.pop(0)
        if a in ("--wear", "--layout", "--copies", "--bands", "--set"):
            if not rest or rest[0].startswith("--"):
                _fail(f"{a} needs a value")
            value = rest.pop(0)
            if a == "--set":
                key, sep, value = value.partition("=")
                if not sep:
                    _fail(f"--set needs KEY=VALUE, not {key!r}")
                sets.append((key.strip(), value.strip()))
            elif a == "--bands":
                sets.append(("bands", value))
            else:
                opts[a] = value
        elif a.startswith("--"):
            _fail(f"unknown option {a}")
        else:
            names.append(a)
    if command == "slice":
        from .slicer import main as slice_main

        if names or sets or opts != {"--wear": None, "--layout": None, "--copies": "1"}:
            _fail("slice takes no CHARM and no options: it slices every plate in out/3mf "
                  "(export only the charms you want first)")
        try:
            sys.exit(slice_main())
        except (OSError, RuntimeError, ValueError) as e:  # no slicer, a failed slice
            _fail(str(e))
    try:
        copies = int(opts["--copies"])
    except ValueError:
        _fail(f"--copies needs a whole number, not {opts['--copies']!r}")
    try:
        charms = _charms(names, opts["--wear"], opts["--layout"], sets)
        if command == "list":
            from .export import describe

            for c in charms:
                print(describe(c))
        elif command == "export":
            from .export import export_all
            from .params import OUT

            report = export_all(OUT, charms, copies)
            sys.exit(1 if any(report.values()) else 0)
        else:
            from .render import all_images

            for path in all_images(charms):
                print("wrote", path)
    except (KeyError, ValueError) as e:
        _fail(str(e).strip("'\""))
