"""The filaments, and the PrusaSlicer material profile.

Only these colours exist: the charms use the owner's Prusament PETG in white, red, green and
black. The hex values are close to Prusament PETG and are used for the 3MF object colours,
the M600 entries and the renders.
"""

FILAMENTS = {
    "white": "#ece8dc",
    "red": "#c62127",
    "green": "#3e9b35",
    "black": "#1c1a1e",
}

# PrusaSlicer filament profile for the Prusa MK4 Input Shaper printer profile
MATERIAL = "Prusament PETG @PGIS"


def hex_rgb(colour: str) -> tuple[float, float, float]:
    """'#rrggbb' or '#rgb' -> (r, g, b) in 0..1."""
    h = colour.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb(name: str) -> tuple[float, float, float]:
    return hex_rgb(FILAMENTS[name])
