"""Every charm and its parameters.

A charm prints lying flat, front face up. The colours are bands in Z: the first filament
prints the whole body, each M600 switches to the next filament for the next band, and every
region of a colour rises to the top of its band.

Two subjects (`tag`, `moka`) and three ways to wear them (`wear`): an `eyelet` above the
centre of mass, `magnet` pockets on the bed side (with a counter plate worn inside the
shirt), or a lanyard `clip` on the back (the tag only). The tag has two layouts:
`one_line` and `two_lines`. `VARIANTS` holds every default combination; `charm()` makes
any other one (the moka with a clip is a clear error from wear.py: it is too narrow).
"""

import math
from dataclasses import dataclass, fields, replace

from . import params as P
from .filaments import FILAMENTS
from .text import LAYOUTS

SUBJECTS = ("tag", "moka")
WEARS = ("eyelet", "magnet", "clip")
DEFAULT_TEXT = "consulting@italy:~$"
# from the bed up: dark over white covers well, and red right above white gives the raised
# letters clean red walls
DEFAULT_BANDS = {"tag": ("white", "red", "green"), "moka": ("white", "red", "green", "black")}
DEFAULT_WEARS = {"tag": WEARS, "moka": ("eyelet", "magnet")}
# the colours each subject's drawing uses (artwork.py): all of them must be bands
COLOURS = {"tag": ("white", "red", "green"), "moka": ("white", "red", "green", "black")}


@dataclass(frozen=True)
class Charm:
    subject: str  # tag | moka
    wear: str = "eyelet"  # eyelet | magnet | clip
    layout: str = ""  # tag: one_line | two_lines ("" = one_line); moka: ""
    text: str = DEFAULT_TEXT  # tag only; two_lines splits at a line break or before the '@'
    font_size: float = 0.0  # em size (mm); 0 = the smallest that prints (text.py)
    bands: tuple[str, ...] = ()  # filaments from the bed up; () = the subject's default
    band_t: float = P.BAND_T  # every colour band above the body
    magnet_clr: float = P.MAGNET_CLR  # pocket clearance on the diameter (mm)
    lanyard_w: float = P.LANYARD_W  # ribbon width of the clip (mm)
    hole_d: float = P.HOLE_D  # eyelet hole
    tab_r: float = P.TAB_R  # outer radius of the eyelet tab
    plate_colour: str = "white"  # filament of the counter plate and the gauges

    def __post_init__(self):
        if self.subject in DEFAULT_BANDS and not self.bands:
            object.__setattr__(self, "bands", DEFAULT_BANDS[self.subject])
        if self.subject == "tag" and not self.layout:
            object.__setattr__(self, "layout", "one_line")

    @property
    def name(self) -> str:
        """tag_one_line_eyelet, moka_magnet, ...: the file names of its parts."""
        if self.subject == "tag":
            return f"tag_{self.layout}_{self.wear}"
        return f"{self.subject}_{self.wear}"

    @property
    def base_t(self) -> float:
        """The body (band 0) in the print pose: thicker for the magnet pockets, and on top of
        the bar, the ribbon gap and the walls for the clip."""
        if self.wear == "magnet":
            return P.MAGNET_BODY_T
        if self.wear == "clip":
            return round(P.CLIP_Z + P.BASE_T, 6)
        return P.BASE_T

    @property
    def pocket_d(self) -> float:
        return round(P.MAGNET_D + self.magnet_clr, 6)

    @property
    def counter_name(self) -> str:
        """The counter plate of a magnet charm: tag_one_line_counter, moka_counter."""
        return (f"tag_{self.layout}_counter" if self.subject == "tag"
                else f"{self.subject}_counter")

    def validate(self) -> None:
        if self.subject not in SUBJECTS:
            raise ValueError(f"unknown subject {self.subject!r}; choose from "
                             f"{', '.join(SUBJECTS)}")
        for f in fields(self):  # nan and inf pass every comparison below unnoticed
            value = getattr(self, f.name)
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"{self.name}: {f.name} must be a number, not {value}")
        if self.wear not in WEARS:
            raise ValueError(f"unknown wear {self.wear!r}; choose from {', '.join(WEARS)}")
        if self.subject == "tag" and self.layout not in LAYOUTS:
            raise ValueError(f"unknown layout {self.layout!r}; choose from {', '.join(LAYOUTS)}")
        if self.subject != "tag" and self.layout:
            raise ValueError(f"{self.name}: layout is for the tag only")
        unknown = sorted({b for b in (*self.bands, self.plate_colour) if b not in FILAMENTS})
        if unknown:
            raise ValueError(f"{self.name}: unknown filament(s) {unknown}; choose from "
                             f"{sorted(FILAMENTS)}")
        if len(set(self.bands)) != len(self.bands):
            raise ValueError(f"{self.name}: a filament appears twice in bands {self.bands}")
        missing = [c for c in COLOURS[self.subject] if c not in self.bands]
        if missing:
            raise ValueError(f"{self.name}: the {self.subject} uses {', '.join(missing)}, which "
                             f"is not one of the bands {self.bands}")
        if self.subject == "tag" and self.bands[0] == "red":
            raise ValueError(f"{self.name}: the text is red, so red cannot print the body "
                             f"(bands[0]): the letters would not rise. Start the bands with "
                             "another filament, e.g. white,red,green")
        if self.band_t <= 0 or not P.on_grid(self.band_t):
            raise ValueError(f"{self.name}: band_t = {self.band_t} is not a whole number of "
                             f"{P.LAYER} mm layers")
        if self.font_size < 0:
            raise ValueError(f"{self.name}: font_size must not be negative (0 = automatic)")
        if not 0 <= self.magnet_clr < 1:
            raise ValueError(f"{self.name}: magnet_clr must be at least 0 and under 1 mm")
        if self.lanyard_w <= 0:
            raise ValueError(f"{self.name}: lanyard_w must be greater than 0")
        if self.hole_d <= 0:
            raise ValueError(f"{self.name}: hole_d must be greater than 0")
        if self.tab_r - self.hole_d / 2 < P.MIN_RING - 1e-9:
            raise ValueError(f"{self.name}: the tab (r {self.tab_r:g}) leaves a ring of "
                             f"{self.tab_r - self.hole_d / 2:.2f} mm around the {self.hole_d:g} "
                             f"mm hole, under {P.MIN_RING:.2f} mm: make tab_r larger")


def _variants() -> dict[str, Charm]:
    out = {}
    for subject in SUBJECTS:
        for layout in (LAYOUTS if subject == "tag" else ("",)):
            for wear in DEFAULT_WEARS[subject]:
                c = Charm(subject, wear, layout)
                out[c.name] = c
    return out


VARIANTS = _variants()


def parse_name(name: str) -> tuple[str, str, str]:
    """'tag_two_lines_clip' -> ('tag', 'two_lines', 'clip'); 'moka_eyelet' -> ('moka', '',
    'eyelet'). Any combination parses: the moka with a clip fails later, with the reason."""
    subject, _, rest = name.partition("_")
    if subject not in SUBJECTS:
        raise KeyError(f"unknown charm {name!r}; choose from {', '.join(SUBJECTS)} or "
                       f"{', '.join(VARIANTS)}")
    layout, _, wear = rest.rpartition("_")
    if wear not in WEARS or (subject == "tag" and layout not in LAYOUTS) or (
            subject != "tag" and layout):
        raise KeyError(f"unknown charm {name!r}; choose from {', '.join(SUBJECTS)} or "
                       f"{', '.join(VARIANTS)}")
    return subject, layout, wear


def charm(name: str, **overrides) -> Charm:
    """A charm by name (any subject_layout_wear), with some parameters changed."""
    subject, layout, wear = parse_name(name)
    c = replace(Charm(subject, wear, layout), **overrides)
    c.validate()
    return c


EDITABLE = tuple(f.name for f in fields(Charm) if f.name != "subject")


def parse_value(c: Charm, key: str, text: str):
    """Turn a command line value into the type of the Charm field `key`."""
    if key not in EDITABLE:
        raise KeyError(f"unknown parameter {key!r}; choose from {sorted(EDITABLE)}")
    current = getattr(c, key)
    if key == "bands":  # white,red,green
        bands = tuple(s.strip() for s in text.split(",") if s.strip())
        if not bands:  # () would mean "the default" and be ignored without a word
            raise ValueError("bands needs at least one filament, e.g. white,red,green")
        return bands
    if key == "text":  # a literal \n on the command line is the line break
        return text.replace("\\n", "\n")
    if isinstance(current, float):
        try:
            return float(text)
        except ValueError:
            raise ValueError(f"{key} needs a number, not {text!r}") from None
    return text
