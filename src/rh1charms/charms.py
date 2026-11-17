"""Every charm and its parameters.

A charm prints lying flat, front face up. The colours are bands in Z: the first filament
prints the whole body, each M600 switches to the next filament for the next band, and every
region of a colour rises to the top of its band.

Two subjects (`tag`, `moka`) and three ways to wear them (`wear`): an `eyelet` above the
centre of mass, `magnet` pockets on the bed side (with a counter plate worn inside the
shirt), or a lanyard `clip` on the back. The tag has two layouts: `one_line` and
`two_lines`. The moka has none, or `pour`: the moka that pours, with a text along the stream
(`moka_pour_eyelet`, ...), or `pour_rh1`: the same, with a clip only, and `RH1` and `2027` on
its backing plate (`moka_pour_rh1_clip`). Each subject and layout is a drawing (`drawing()`)
with its own colours, bands and ways to wear it (`default_wears()`). `VARIANTS` holds every
default combination; `charm()` makes any other one (the plain moka with a clip is a clear
error from wear.py: it is too narrow; the moka that pours gets a backing plate).
"""

import math
from dataclasses import dataclass, fields, replace

from . import params as P
from .filaments import FILAMENTS
from .text import LAYOUTS

SUBJECTS = ("tag", "moka")
WEARS = ("eyelet", "magnet", "clip")
POUR_LAYOUTS = ("pour", "pour_rh1")  # the moka that pours: the same drawing
LAYOUTS_OF = {"tag": LAYOUTS, "moka": ("", *POUR_LAYOUTS)}  # "" = the moka without a layout
# the texts on the backing plate of the clip (top right, bottom centre), by layout: the
# owner's choice (2026-11-17). Other layouts have none and ignore plate_top and plate_bottom.
PLATE_TEXTS = {"pour_rh1": ("RH1", "2027")}
PLATE_COLOURS = ("red", "green")  # the filaments of the top and the bottom text
LAYOUT_WEARS = {"pour_rh1": ("clip",)}  # the plate exists only with a clip
DEFAULT_TEXT = "consulting@italy:~$"
POUR_TEXT = "consulting"  # the text of the moka that pours (the owner's choice, 2026-11-17)
# the drawings with a text, in raised red letters (red cannot print their body), and their
# default text
TEXTS = {"tag": DEFAULT_TEXT, "moka_pour": POUR_TEXT}
# from the bed up: dark over white covers well, and red right above white gives the raised
# letters clean red walls. The moka that pours has no black: its knob and handle are red.
DEFAULT_BANDS = {"tag": ("white", "red", "green"), "moka": ("white", "red", "green", "black"),
                 "moka_pour": ("white", "red", "green")}
DEFAULT_WEARS = {"tag": WEARS, "moka": ("eyelet", "magnet"), "moka_pour": WEARS}
# the colours each drawing uses (artwork.py): all of them must be bands
COLOURS = DEFAULT_BANDS


def drawing(subject: str, layout: str) -> str:
    """The drawing of a subject and layout: tag, moka, or moka_pour (the moka that pours)."""
    return "moka_pour" if subject == "moka" and layout in POUR_LAYOUTS else subject


def default_wears(subject: str, layout: str) -> tuple[str, ...]:
    """The ways to wear a subject and layout that VARIANTS holds."""
    return LAYOUT_WEARS.get(layout, DEFAULT_WEARS[drawing(subject, layout)])


@dataclass(frozen=True)
class Charm:
    subject: str  # tag | moka
    wear: str = "eyelet"  # eyelet | magnet | clip
    layout: str = ""  # tag: one_line | two_lines ("" = one_line); moka: "" | pour | pour_rh1
    # tag: two_lines splits at a line break or before the '@' (None = DEFAULT_TEXT); the
    # moka that pours: one line along the stream (None = POUR_TEXT); the plain moka has no
    # text and ignores one (so a --set text for every charm works)
    text: str | None = None
    # em size (mm); 0 = automatic: the smallest that prints (text.py), and on the moka that
    # pours at least artwork.POUR_FONT, so that the letters fill the stream
    font_size: float = 0.0
    bands: tuple[str, ...] = ()  # filaments from the bed up; () = the drawing's default
    band_t: float = P.BAND_T  # every colour band above the body, but red (red_t)
    red_t: float = 0.0  # the red band (the letters); 0 = band_t, or POUR_RED_T (moka_pour)
    magnet_clr: float = P.MAGNET_CLR  # pocket clearance on the diameter (mm)
    lanyard_w: float = P.LANYARD_W  # ribbon width of the clip (mm)
    hole_d: float = P.HOLE_D  # eyelet hole
    tab_r: float = P.TAB_R  # outer radius of the eyelet tab
    plate_colour: str = "white"  # filament of the counter plate and the gauges
    # the texts on the clip's backing plate, top right (red) and bottom centre (green), one
    # line each; None = the layout's (PLATE_TEXTS), "" = none. Only the layouts in
    # PLATE_TEXTS have them: the others ignore them and keep None (so a --set for every
    # charm works, and a new layout still gets its own)
    plate_top: str | None = None
    plate_bottom: str | None = None
    # their em size (mm); 0 = automatic: the largest at which the top text fits its corner,
    # at most artwork.POUR_FONT (wear.py)
    plate_font: float = 0.0

    def __post_init__(self):
        if self.subject == "tag" and not self.layout:
            object.__setattr__(self, "layout", "one_line")
        if self.drawing in DEFAULT_BANDS and not self.bands:
            object.__setattr__(self, "bands", DEFAULT_BANDS[self.drawing])
        if self.text is None and self.drawing in TEXTS:
            object.__setattr__(self, "text", TEXTS[self.drawing])
        if self.layout in PLATE_TEXTS:
            top, bottom = PLATE_TEXTS[self.layout]
            if self.plate_top is None:
                object.__setattr__(self, "plate_top", top)
            if self.plate_bottom is None:
                object.__setattr__(self, "plate_bottom", bottom)
        else:  # ignored: the same charm as without them
            for name, value in (("plate_top", None), ("plate_bottom", None), ("plate_font", 0.0)):
                object.__setattr__(self, name, value)

    @property
    def drawing(self) -> str:
        return drawing(self.subject, self.layout)

    @property
    def name(self) -> str:
        """tag_one_line_eyelet, moka_magnet, moka_pour_clip, ...: the file names of its parts."""
        if self.layout:
            return f"{self.subject}_{self.layout}_{self.wear}"
        return f"{self.subject}_{self.wear}"

    @property
    def band_ts(self) -> tuple[float, ...]:
        """The thickness of every band above the body (bands[1:]): band_t, but red_t for red
        (red_t 0: band_t, or POUR_RED_T on the moka that pours)."""
        red = self.red_t or (P.POUR_RED_T if self.drawing == "moka_pour" else self.band_t)
        return tuple(red if f == "red" else self.band_t for f in self.bands[1:])

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
        """The counter plate of a magnet charm: tag_one_line_counter, moka_counter,
        moka_pour_counter."""
        if self.layout:
            return f"{self.subject}_{self.layout}_counter"
        return f"{self.subject}_counter"

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
        if self.layout not in LAYOUTS_OF[self.subject]:
            choices = ", ".join(lay or "none" for lay in LAYOUTS_OF[self.subject])
            raise ValueError(f"unknown layout {self.layout!r} for the {self.subject}; choose from "
                             f"{choices}")
        if self.drawing in TEXTS and not self.text.strip():  # the plain moka ignores it
            raise ValueError(f"{self.name}: the text is empty")
        if self.drawing == "moka_pour" and "\n" in self.text:
            raise ValueError(f"{self.name}: the moka's text is one line, without a line break")
        if self.layout in LAYOUT_WEARS and self.wear not in LAYOUT_WEARS[self.layout]:
            raise ValueError(f"{self.name}: the {self.layout} layout puts its texts on the backing "
                             f"plate of the clip: wear it with a "
                             f"{' or '.join(LAYOUT_WEARS[self.layout])}")
        for t, colour in zip((self.plate_top, self.plate_bottom), PLATE_COLOURS):
            if not t:
                continue
            if not t.strip():
                raise ValueError(f"{self.name}: the text {t!r} on the plate has no letters: "
                                 "leave it empty for none")
            if "\n" in t:
                raise ValueError(f"{self.name}: a text on the plate is one line, without a line "
                                 "break")
            if self.bands[0] == colour:
                raise ValueError(f"{self.name}: {t!r} on the plate is {colour}, so {colour} "
                                 "cannot print the body (bands[0]): the letters would not rise")
        if self.plate_font < 0:
            raise ValueError(f"{self.name}: plate_font must not be negative (0 = automatic)")
        unknown = sorted({b for b in (*self.bands, self.plate_colour) if b not in FILAMENTS})
        if unknown:
            raise ValueError(f"{self.name}: unknown filament(s) {unknown}; choose from "
                             f"{sorted(FILAMENTS)}")
        if len(set(self.bands)) != len(self.bands):
            raise ValueError(f"{self.name}: a filament appears twice in bands {self.bands}")
        missing = [c for c in COLOURS[self.drawing] if c not in self.bands]
        if missing:
            raise ValueError(f"{self.name}: the {self.subject} uses {', '.join(missing)}, which "
                             f"is not one of the bands {self.bands}")
        # a last band in a colour the drawing does not use would be empty (a band covers its
        # colour and every one above it): a colour change for nothing
        last = max(self.bands.index(c) for c in COLOURS[self.drawing])
        if self.bands[last + 1:]:
            raise ValueError(f"{self.name}: the {self.subject} does not use "
                             f"{', '.join(self.bands[last + 1:])}, so its band would be empty: "
                             f"leave it out of the bands {self.bands}")
        if self.drawing in TEXTS and self.bands[0] == "red":
            raise ValueError(f"{self.name}: the text is red, so red cannot print the body "
                             f"(bands[0]): the letters would not rise. Start the bands with "
                             "another filament, e.g. white,red,green")
        if self.band_t <= 0 or not P.on_grid(self.band_t):
            raise ValueError(f"{self.name}: band_t = {self.band_t} is not a whole number of "
                             f"{P.LAYER} mm layers")
        if self.red_t < 0 or not P.on_grid(self.red_t):
            raise ValueError(f"{self.name}: red_t = {self.red_t} is not a whole number of "
                             f"{P.LAYER} mm layers (0 = the default)")
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
        for layout in LAYOUTS_OF[subject]:
            for wear in default_wears(subject, layout):
                c = Charm(subject, wear, layout)
                out[c.name] = c
    return out


VARIANTS = _variants()


def parse_name(name: str) -> tuple[str, str, str]:
    """'tag_two_lines_clip' -> ('tag', 'two_lines', 'clip'); 'moka_eyelet' -> ('moka', '',
    'eyelet'); 'moka_pour_clip' -> ('moka', 'pour', 'clip'); 'moka_pour_rh1_clip' -> ('moka',
    'pour_rh1', 'clip'). Any combination parses: the plain moka with a clip fails later, with
    the reason."""
    subject, _, rest = name.partition("_")
    layout, _, wear = rest.rpartition("_")
    if subject not in SUBJECTS or wear not in WEARS or layout not in LAYOUTS_OF[subject]:
        raise KeyError(f"unknown charm {name!r}; choose from {', '.join(SUBJECTS)} or "
                       f"{', '.join(VARIANTS)}")
    return subject, layout, wear


def charm(name: str, **overrides) -> Charm:
    """A charm by name (any subject_layout_wear), with some parameters changed. A new layout
    comes first: the defaults (bands, text) are its drawing's."""
    subject, layout, wear = parse_name(name)
    c = replace(Charm(subject, wear, overrides.pop("layout", layout)), **overrides)
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
    if key in ("text", "plate_top", "plate_bottom"):  # a literal \n is the line break
        return text.replace("\\n", "\n")
    if isinstance(current, float):
        try:
            return float(text)
        except ValueError:
            raise ValueError(f"{key} needs a number, not {text!r}") from None
    return text
