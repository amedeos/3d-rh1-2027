"""Printer and process constants shared by every charm (millimetres).

Every flat horizontal face must sit on a layer boundary when the part lies in its print
position, and thin walls are a whole number of extrusion lines (see `lines()` and
tests/test_layers.py). The parameters of each charm live in `charms.py`.
"""

from math import ceil, pi
from pathlib import Path

# --- printer / process: Prusa MK4, 0.4 mm nozzle, PrusaSlicer "0.20mm STRUCTURAL" -----
BED = (250.0, 210.0, 220.0)  # Prusa MK4 print volume
NOZZLE = 0.4
LAYER = 0.2  # layer height
FIRST_LAYER = 0.2  # first layer height
LINE_W = 0.45  # extrusion width (perimeters and infill)
# centre distance of two touching lines, as PrusaSlicer computes it
LINE_SPACING = LINE_W - LAYER * (1 - pi / 4)
MIN_STROKE = 0.85 * LINE_W  # Arachne drops walls thinner than this (min_bead_width)
MIN_GAP = LINE_W  # narrower gaps and grooves close up


def lines(n: int) -> float:
    """Width of a wall made of n touching extrusion lines."""
    return (n - 1) * LINE_SPACING + LINE_W


def layers(n: int) -> float:
    """Height of n layers (the first layer included)."""
    return round(FIRST_LAYER + (n - 1) * LAYER, 6) if n > 0 else 0.0


def layer_top(z: float) -> float:
    """Top (print_z) of the first layer that starts at or above height z."""
    if z <= 1e-9:
        return FIRST_LAYER
    k = ceil((z - FIRST_LAYER) / LAYER - 1e-9) + 1
    return round(FIRST_LAYER + k * LAYER, 6)


def snap_up(z: float) -> float:
    """Smallest layer boundary at or above z (boundaries: 0, FIRST_LAYER, + n * LAYER)."""
    if z <= FIRST_LAYER:
        return 0.0 if z <= 1e-9 else FIRST_LAYER
    return round(FIRST_LAYER + ceil((z - FIRST_LAYER) / LAYER - 1e-9) * LAYER, 6)


def on_grid(z: float) -> bool:
    """z is a layer boundary. The tolerance only absorbs floating-point noise: a thickness a
    hair off the grid would move the next band's M600 one layer late (layer_top)."""
    return abs(z - round(z / LAYER) * LAYER) < 1e-6


# --- body and colour bands ------------------------------------------------------------
BASE_T = layers(6)  # the body (band 0) of a charm: 1.2 mm
BAND_T = layers(4)  # every further colour band: 0.8 mm

# --- eyelet: a tab with a hole, above the centre of mass --------------------------------
TAB_R = 4.0  # outer radius of the tab
HOLE_D = 4.0  # the hole: a 2.0 mm ring all round
MIN_RING = lines(4)  # the thinnest ring a tab may have (hole_d and tab_r are parameters)

# --- magnets: 8 x 2 mm neodymium discs ----------------------------------------------------
MAGNET_D = 8.0
MAGNET_H = 2.0
MAGNET_CLR = 0.2  # pocket clearance on the diameter: an 8.2 mm pocket (a parameter)
POCKET_DEPTH = snap_up(MAGNET_H + LAYER)  # 2.2 mm: one layer more than the magnet
ROOF_T = layers(3)  # the bridged roof over a pocket of the charm: 0.6 mm
MAGNET_BODY_T = round(POCKET_DEPTH + ROOF_T, 6)  # the body of a magnet charm: 2.8 mm
MIN_POCKET_WALL = lines(3)  # the least plastic between a pocket and the edge of the body
COUNTER_FLOOR = layers(4)  # counter plate: 0.8 mm under the magnets (towards the shirt)
COUNTER_T = round(COUNTER_FLOOR + POCKET_DEPTH, 6)  # 3.0 mm, pockets open on top
COUNTER_WALL = 2.0  # plastic around the pockets of a counter plate
GAUGE_D = (8.0, 8.1, 8.2, 8.3)  # pocket diameters of the pocket gauge

# --- lanyard clip: a bar on the bed, a gap for the ribbon, then the tag ----------------
BAR_T = layers(6)  # 1.2 mm
BAR_W = 8.0
RIBBON_GAP = layers(8)  # 1.6 mm between the bar and the underside of the tag
CLIP_Z = round(BAR_T + RIBBON_GAP, 6)  # the underside of the tag over the channel: 2.8 mm
RISER_W = 2.4  # the least wall beside the channel
RIBBON_T = 1.04  # ribbon thickness, measured on the 2026 RH1 lanyard
# The bar stops SLIT short of one wall: the ribbon slides in on its edge through the slit.
# The owner chose 1.1 mm with the clip gauge on 2026-11-15. It is the gauge's narrowest
# slit, and it took the 2026 ribbon and held it. That gauge was black PETG, and the tag's
# body is white: the colour can change the printed width a little. Every slit needs a
# margin over RIBBON_T for the XY tolerance of the layers from 0.4 to 1.2 mm. In the
# first layer the slit prints 0.4 mm wider (elefant_foot_compensation = 0.2 mm a side).
SLIT = 1.1
CLIP_GAUGE_SLITS = (1.1, 1.3, 1.5, 1.7)  # the slits of the clip gauge, marked with 1 to 4 dots
LANYARD_W = 20.0  # default ribbon width (a parameter)
CHANNEL_EXTRA = 2.0  # the channel is this much wider than the ribbon
OVERLAP = 0.05  # a joined piece reaches this far into the other, so the two fuse

# --- output -----------------------------------------------------------------------------
OUT = Path("out")
