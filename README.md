# 3d-rh1-2027: wearable charms for the Italian Consulting team at RH1 2027 ☕

Parametric, 3D-printable charms for the Italian Consulting team at Red Hat's RH1 2027 event (Las Vegas, January 2027): a **name tag** with the shell prompt `consulting@italy:~$` between a green and a red band, a tricolour **moka pot**, and a **moka that pours**, with `consulting` written along the coffee that comes out of its spout (and, in one version with a clip, `RH1` and `2027` on the clip's plate). Each one comes with an **eyelet**, with **magnets** (and a counter plate worn inside the shirt), or, for the tag and the moka that pours, with a **lanyard clip** on the back.

Everything is written in Python with [build123d](https://github.com/gumyr/build123d), in the style of the author's [3d-linux](https://github.com/amedeos/3d-linux) project. Every size, colour and clearance is a parameter. The Python package and command are called `rh1charms`.

## How it works

- **Colour bands, one extruder.** A charm prints lying flat, front face up. The first filament (white) prints the whole body. After that, each colour change (M600) adds one band, and every region of that colour rises to the top of its band: red, then green, then black. From the front you see the drawing in colour. You need **one extruder only**: no MMU and no INDX.
- **Made for the slicer grid.** The body is 1.2 mm (6 layers) and every band 0.8 mm (4 layers), but the red band of the moka that pours: 1.2 mm, so that its letters stand out more. Every horizontal face sits on the 0.2 mm layer grid, so every colour change lands exactly where it should. Raised parts are at least 85 % of a line wide, and the gaps between them at least one line (0.45 mm), so nothing disappears in the slicer.
- **The text sets the size of the tag.** The tag uses Red Hat Mono Bold, read straight from the font file. The font size is the smallest one, rounded up to 0.1 mm, at which no stroke is thinner than 85 % of a line and no gap narrower than a line. For `consulting@italy:~$` it is **8.3 mm**: the narrowest gap is the slot inside the `@` (0.055 of the font size), and it needs 0.45 mm. Then the letters must come through the cleanup of the colour bands unchanged but for their corners: the foot of an `L` or the bar of a `7` can be too thin without closing any gap, so for a text like `LT` the size goes up, 0.1 mm at a time, until they do. The tag size follows from the text. If you force a smaller `font_size`, `export` stops and tells you why.
- **The moka that pours.** The moka leans forward by 35° to pour, with its spout on the right. A white stream leaves the spout and bends down, and the text, in raised red letters, starts at the spout and runs along the stream. The text is `consulting` (any other one with `--set text=...`, on one line). The font size is the smallest one that prints, but at least 9 mm, so that the letters fill the stream (`consulting` would print from 6.4 mm, `services` from 6.8 mm). The stream ends round, 1.5 mm after the last letter: no more white than at its sides. It has no black: the knob and the handle are red, so it needs only two colour changes. `moka_pour_rh1_clip` is the same moka with a clip, and with `RH1` in red in the top right corner of the clip's white plate and `2027` in green in the middle of its bottom edge (see "Wearing them").
- **It hangs straight.** The eyelet sits right above the centre of mass, and so does the plain moka's single magnet. The tag has two magnets, a quarter of its width from each end, so it cannot turn; the moka that pours has two too, in the upper chamber and in the boiler, because its centre of mass lies on the stream, which is too narrow for a pocket.

## The charms

| Charm | Size (mm) | Colour bands (from the bed up) | Colour changes (M600) | Time* | Filament* | Per plate, at most |
|---|---|---|---|---|---|---|
| `tag_one_line_eyelet` | 109.0 × 21.4 × 2.8 | white → red → green | red 1.40, green 2.20 | 8 min 49 s | 2.72 g | 14 |
| `tag_one_line_magnet` | 109.0 × 13.4 × 4.4 | white → red → green | red 3.00, green 3.80 | 13 min 47 s | 4.27 g | 22 |
| `tag_one_line_clip` | 109.0 × 13.4 × 5.6 | white → red → green | red 4.20, green 5.00 | 14 min 26 s | 4.86 g | 22 |
| `tag_two_lines_eyelet` | 64.2 × 30.6 × 2.8 | white → red → green | red 1.40, green 2.20 | 8 min 24 s | 2.80 g | 15 |
| `tag_two_lines_magnet` | 64.2 × 22.6 × 4.4 | white → red → green | red 3.00, green 3.80 | 12 min 52 s | 4.22 g | 21 |
| `tag_two_lines_clip` | 64.2 × 22.6 × 5.6 | white → red → green | red 4.20, green 5.00 | 13 min 12 s | 4.48 g | 21 |
| `moka_eyelet` | 31.4 × 43.8 × 3.6 | white → red → green → black | red 1.40, green 2.20, black 3.00 | 7 min 42 s | 1.91 g | 24 |
| `moka_magnet` | 31.4 × 35.8 × 5.2 | white → red → green → black | red 3.00, green 3.80, black 4.60 | 10 min 15 s | 2.53 g | 30 |
| `moka_pour_eyelet` | 85.5 × 52.6 × 3.2 | white → red → green | red 1.40, green 2.60 | 12 min 33 s | 3.51 g | 6 |
| `moka_pour_magnet` | 85.5 × 52.6 × 4.8 | white → red → green | red 3.00, green 4.20 | 18 min 6 s | 5.18 g | 6 |
| `moka_pour_clip` | 85.5 × 52.6 × 6.0 | white → red → green | red 4.20, green 5.40 | 21 min 39 s | 6.73 g | 6 |
| `moka_pour_rh1_clip` | 85.5 × 52.6 × 6.0 | white → red → green | red 4.20, green 5.40 | 24 min 29 s | 7.30 g | 6 |

And the single-colour parts (white by default):

| Part | Size (mm) | For | Time* | Filament* |
|---|---|---|---|---|
| `tag_one_line_counter` | 66.7 × 12.2 × 3.0 | `tag_one_line_magnet` | 6 min 17 s | 2.19 g |
| `tag_two_lines_counter` | 44.3 × 12.2 × 3.0 | `tag_two_lines_magnet` | 4 min 28 s | 1.42 g |
| `moka_counter` | 12.2 × 12.2 × 3.0 | `moka_magnet` | 2 min 36 s | 0.35 g |
| `moka_pour_counter` | 21.3 × 25.2 × 3.0 | `moka_pour_magnet` | 3 min 21 s | 0.85 g |
| `pocket_gauge` | 53.3 × 15.7 × 3.2 | finding the magnet clearance | 7 min 59 s | 2.08 g |
| `clip_gauge` | 127.0 × 13.4 × 4.4 | finding the clip slit | 14 min 55 s | 4.25 g |

\* PrusaSlicer 2.9.6 estimates for one copy (Prusament PETG, 0.20mm STRUCTURAL), not counting the time for the filament changes. The size includes the eyelet; the thickness includes the colour bands.

The plain moka has no clip: its body is at most 18 mm wide where the bar would go, and the 22 mm channel with its walls needs 26.8 mm. `export moka_clip` stops with that message. The moka that pours is too narrow as well, so its clip sits on a white backing plate (see "Wearing them").

## Requirements

- [uv](https://docs.astral.sh/uv/) and Python 3.14 (3.13 also works)
- `uv sync` installs build123d, fontTools, shapely, trimesh and pillow
- Optional: PrusaSlicer 2.9 for `rh1charms slice`

```sh
uv sync
uv run pytest                    # ~3 min: text size, layers, bands, pockets, clip, plates, 3MF, CLI
uv run rh1charms list            # every charm: size, font size, bands, colour changes
uv run rh1charms export          # STL files and 3MF plates in out/
uv run rh1charms slice           # optional, needs PrusaSlicer: times, M600 and bridge checks, projects
uv run rh1charms render          # PNG previews in out/render
```

`export` exits with status 1 if a part has a problem. The output:

| Folder | Contents |
|---|---|
| `out/stl/` | one STL per part, already in its print position |
| `out/3mf/` | one 3MF plate per print job, with the colour changes; `plan.json` (each plate's start filament, colour changes and bridges) |
| `out/3mf/projects/` | PrusaSlicer projects, written by `slice` |
| `out/render/` | `<part>_front.png`, `_back.png` (the bed side: pockets, bar, channel), `_edge.png` (the profile as printed), `_flat.png` (the bands in 2D) and, for a charm that hangs from one point, `_hang.png` (a plumb line through the centre of mass) |

## Batches and parameters

One colour change serves the whole plate, so print a batch: `--copies N` puts N copies of one charm, with one way of wearing it, on one plate. The variants have different band heights, so each one has its own plate. A magnet charm brings a plate with the same number of counter plates, and the pocket gauge. A clip tag brings the clip gauge. If the copies do not fit on the bed, `export` stops before it writes anything and tells you the largest number that fits. For example, six one-line clip tags take 1 h 23 min and 29 g of PETG, with the same two colour changes as one tag.

```sh
uv run rh1charms export tag --wear clip --copies 8          # both tag layouts, 8 each
uv run rh1charms export tag_one_line_magnet --copies 10 --set magnet_clr=0.3
uv run rh1charms export moka --copies 6                     # every moka, 6 each
uv run rh1charms export moka_pour_clip --set text=services
uv run rh1charms export moka_pour_rh1_clip --set plate_font=7   # smaller RH1 and 2027
uv run rh1charms export tag --set text='consulting@roma:~$'
uv run rh1charms export tag_two_lines_eyelet --set 'text=consulting\n@roma:~$'
uv run rh1charms export tag_two_lines_clip --set lanyard_w=15
uv run rh1charms export tag --set font_size=10              # larger letters, a larger tag
uv run rh1charms render moka
```

A charm is a subject (`tag` or `moka`), a way to wear it (`--wear eyelet|magnet|clip`) and a layout: `--layout one_line|two_lines` for the tag, `--layout pour` for the moka that pours, `--layout pour_rh1` for it with `RH1` and `2027` on its clip's plate (clip only; the plain moka has none). Name a variant (`tag_two_lines_clip`, `moka_pour_magnet`) or a subject (all its variants). `--set` changes any parameter of `Charm` in `src/rh1charms/charms.py`:

- `text`: the text of the tag, or of the moka that pours (one line). `two_lines` splits it before the last `@`, or where you write `\n`. Every character must exist in Red Hat Mono Bold. The plain moka has no text and ignores one.
- `font_size`: 0 (the default) picks the smallest size that prints, and at least 9 mm on the moka that pours; a smaller forced size is an error. `rh1charms list` shows what sets it.
- `bands`: the filaments from the bed up, from white, red, green and black. Every colour of the drawing must be one of them, and the last band a colour of the drawing: a colour on top that the drawing does not use would give an empty band (the moka that pours has no black).
- `band_t`: the thickness of each colour band. It must be a whole number of 0.2 mm layers.
- `red_t`: the thickness of the red band (the letters). 0, the default, means `band_t`, or 1.2 mm on the moka that pours.
- `magnet_clr`: the pocket clearance on the diameter (0.2: an 8.2 mm pocket for an 8 mm magnet). It changes only the diameter: the pocket stays 2.2 mm deep under a 0.6 mm roof.
- `lanyard_w`: the ribbon width of the clip (20 mm; the channel is 2 mm wider). The channel must fit with its walls and lie over the centre of mass, or `export` says so.
- `hole_d`, `tab_r`: the eyelet's hole and outer radius (4 mm and 4 mm: a 2 mm ring).
- `plate_colour`: the filament of the counter plates and the gauges.
- `plate_top`, `plate_bottom`: the texts on the clip's plate of `moka_pour_rh1_clip`, one line each (`RH1` and `2027`; empty: none). The other charms ignore them.
- `plate_font`: their font size. 0, the default, picks the largest size at which the top text fits its corner, at most 9 mm and no wider than the plate (a narrower `lanyard_w` makes the texts smaller); the plate then grows at the bottom until the bottom text fits. If the corner is too small even for the smallest size that prints both texts (a wide top text), the plate grows at the top too, just enough. A forced size larger than the corner grows the plate at the top as well; a forced size that is too wide for the plate or does not print is an error.

## Printing

Prusa MK4 (Input Shaper firmware), **Prusament PETG**, 0.4 mm nozzle, **0.20mm STRUCTURAL** profile, **no supports**. Use the textured or satin sheet: PETG sticks too much to the smooth PEI sheet.

There are three kinds of files. Use whichever you like:

- **`out/3mf/projects/*.3mf` — easiest.** PrusaSlicer projects with the MK4 + 0.20mm STRUCTURAL + Prusament PETG settings already loaded, and every colour change already set. The filament colour is the plate's start colour (white, unless you changed `bands` or `plate_colour`), so PrusaSlicer shows the right colour from the first layer (the Prusament PETG profile would show orange). That is why PrusaSlicer marks the filament preset as "(modified)": this is expected. Open a project with **File > Open project** (Ctrl+O). If you drag it into PrusaSlicer and a dialog appears, choose **Open as project**: "Import geometry only" loses the settings and the colour changes. If no dialog appears (it may have been turned off), use Ctrl+O.
- **`out/3mf/*.3mf`** — the same plates without print settings, with the colour changes. Use them with any printer profile. Open them with **File > Open project** (Ctrl+O): PrusaSlicer 2.9 loads only the geometry, without the colour changes, when you drag such a file in, double-click it or import it (Ctrl+I). The layers before the first colour change show in the colour of the filament profile (orange for Prusament PETG). To see the right colour, click the colour square next to the filament and choose the plate's start colour (`start` in `out/3mf/plan.json`; white by default).
- Whichever file you open, if you change it, save it with **File > Save project as** outside `out/`. Ctrl+S overwrites the file in `out/3mf/`, and the next `export` replaces it anyway.
- **`out/stl/*.stl`** — one file per part. Add the colour changes yourself: open the preview, move the vertical slider to the layer that ends at the height in the table above, and click the **+**.

`rh1charms slice` slices every plate with PrusaSlicer and checks it: every M600 is where the design wants it and in the right colour; a second slice with automatic supports creates **no support**; and every ceiling prints as a **bridge**: the first layer over the pocket roofs (2.40 mm) and over the clip channel (3.00 mm).

### Test these first

1. **The clip gauge** (about 15 minutes), if you use the clip. It has four separate pieces, each one the back of a clip tag: the same channel, bar, ribbon gap and ceiling, as tall as the tag, but 4.4 mm thick: without the colour bands. Only the slit differs: 1.1, 1.3, 1.5 and 1.7 mm, marked with 1 to 4 dots. Try the ribbon in each piece: it must go in through the slit, slide along the channel, and stay in when you pull the piece sideways and twist it. Set `SLIT` in `src/rh1charms/params.py` to the narrowest slit that does all three, and export again. With the 2026 RH1 lanyard, the 1.1 mm piece (one dot) did all three, so `SLIT` is 1.1. That gauge was black PETG. The tag's body is white, and the colour can change the printed width a little. The gauge follows the first clip tag you export: its lanyard width and its height (the clip of the moka that pours has no gauge).
2. **One clip tag.** The underside of the tag bridges the 22 mm channel at 2.8 mm. PrusaSlicer confirms that it needs no support and prints the first layer over the channel as bridge infill. But the two ends of the channel, where the ribbon goes in and out, are free edges: their outer lines print as overhang perimeters across 22 mm, anchored on both walls. Print one tag before you print a plate of them. Check that the ceiling is flat, that the ribbon goes in through the slit and slides along the channel, and that it stays in when you pull the tag sideways and twist it: a whole tag pulls harder than a piece of the gauge. A two-line clip tag with `SLIT` = 1.1 passed this test with the 2026 RH1 lanyard: the ribbon needed a little force the first time it went in, and then it worked well. If the ribbon does not go in, try the next wider slit, 1.3 mm (two dots): the ribbon went into that gauge piece, but check that the piece also keeps it in when you pull and twist it. If it does, set `SLIT` to 1.3. If the ribbon comes out, the slit cannot get much narrower: 1.1 mm is the narrowest slit of the gauge, and only 0.06 mm wider than the ribbon. The clip then needs another shape. (With automatic supports on, PrusaSlicer widens the first layer of every support by 3 mm. Under a free edge of the two-line tag it trimmed the support away but left that widened first layer, a pad on the bed that supports nothing: `slice` turns the widening off in its support check.)
3. **The moka that pours with a clip.** Its clip has two bars with the slits on opposite sides (see "Wearing them"). With a 1.1 mm slit on both bars, the ribbon was hard to get into the second one: between the bars it must turn on its edge again. A gauge with 1.5, 2.0 and 2.5 mm for the second slit chose 1.5 mm (`SLIT_WIDE`). Two `moka_pour_clip` with `services` were printed with these slits on 2026-11-16: clean colours and letters, and the first one hangs level on a lanyard (not the RH1 one). On 2026-11-17 one with `consulting` at 10 mm, and then one at 9 mm with the short end of the stream, today's default, were printed: clean colours and letters. Their ribbon test on the RH1 lanyard has not been reported yet. Try it on the RH1 lanyard before you print a batch: put the ribbon into the 1.1 mm bar first, then into the 1.5 mm one, and check that it stays in when you pull the moka sideways and twist it, both ways. One `moka_pour_rh1_clip` was printed on 2026-11-17, still with the 10 mm stream and 7.9 mm texts: clean colours and letters, the bar of the `7` and the slash in the `0` of `2027` included; seen from the side, the green letters show red under the green, as expected. `moka_pour_eyelet` and `moka_pour_magnet` have not been printed yet: print one of each first.
4. **The pocket gauge** (about 8 minutes), if you use magnets. It has four pockets of 8.0, 8.1, 8.2 and 8.3 mm, marked with 1 to 4 dots, printed exactly like the charm's: on the bed side, under the same 0.6 mm roof. Push a magnet into each one. Use the pocket that holds the magnet but still lets it in without force, and set `magnet_clr` to its diameter minus 8.0 (for example `--set magnet_clr=0.1` for the 8.1 mm pocket).

## Wearing them

- **Eyelet.** A 4 mm hole in a tab on the top edge, right above the centre of mass, for a split ring, a lobster clasp or a lanyard hook. The tab is white (the body colour) and lies outside the drawing. On the moka that pours with `consulting` it stands on the stream, right of the knob, lower than the handle. `out/render/<charm>_hang.png` shows the plumb line from the top of the hole through the centre of mass.
- **Magnets.** For **8 × 2 mm** neodymium discs: two in each tag, one in the plain moka, two in the moka that pours, and as many in the counter plate. The charm's pockets open on the back (bed side) under a 0.6 mm roof; the counter plate's pockets open on top, over a 0.8 mm floor that touches the shirt.
  - **Polarity.** Stack all the magnets in one column and mark the top face of each one with a marker. Glue every magnet with its **marked face showing**: in the charm and in the counter plate alike. Then the charm's magnets face the shirt with one pole and the plate's with the other, and they pull each other through the fabric. The plate is symmetric, so it can go either way round. Before the glue sets, try it on a shirt: the plate must pull the charm, not push it.
  - **Glue.** A drop of two-part epoxy or cyanoacrylate (super glue) in each pocket, then press the magnet in. It sits 0.2 mm below the surface. Let it cure before you wear it.
  - Wear the counter plate inside the shirt with its flat floor towards the fabric. Through thick fabric the magnets hold less: try them first.
- **Lanyard clip.** A bar on the back holds a 20 mm ribbon (`lanyard_w`) in a 22 mm channel, 1.6 mm deep. The bar is joined to one wall and stops 1.1 mm short of the other: the narrowest slit of the clip gauge that lets the 1.04 mm ribbon of the 2026 RH1 lanyard in and keeps it in. Turn the ribbon on its edge, push the edge through that slit, and turn it flat inside the channel. The channel lies over the centre of mass, so the tag hangs level. The moka that pours is too narrow for the channel, so a white backing plate fills the space behind it: exactly the channel and its two 2.4 mm walls wide (26.8 mm), and 1 mm taller than the moka where it crosses the channel, but at least 27 mm, so that its two bars fit with 8 mm between them. The plate has two bars, 1.5 mm from its top and bottom edges: the top one is joined to the left wall and stops 1.1 mm short of the right one, the bottom one is joined to the right wall and stops 1.5 mm (`SLIT_WIDE`) short of the left one (seen from the front). The ribbon goes into the top bar first. With the slits on opposite sides, it cannot slide out sideways; the 1.1 mm bar alone holds it, as on the tag. On `moka_pour_rh1_clip` the plate carries `RH1` (red) in its top right corner and `2027` (green) in the middle of its bottom edge, 1.2 mm from the edges and 1 mm from the moka, at one size (9 mm, the most they may be, like the stream's letters: `RH1` fits between the knob and the stream). The plate is 5.5 mm longer at the bottom than on `moka_pour_clip`, to make room for `2027`, and its bottom bar moves down with it. Green prints on top of the red band, so `2027` stands 2.0 mm proud (`RH1` 1.2 mm), and the sides of its letters show red under the green, like the moka's boiler. The slit is not a parameter: the clip gauge tells you which one to put in `SLIT` in `src/rh1charms/params.py` (see "Test these first"). If the 2027 lanyard has a thicker ribbon, measure it, write it in `RIBBON_T`, choose the gauge's slits (`CLIP_GAUGE_SLITS`) above it, and set `SLIT` to one of them until the printed gauge tells you which one: the tests check that `SLIT` is one of the gauge's slits, and that `SLIT`, every slit of the gauge and the 1.6 mm ribbon gap are wider than the ribbon.

## The font

The text uses **Red Hat Mono Bold** (version 1.030), © The Red Hat Project Authors, under the [SIL Open Font License 1.1](src/rh1charms/fonts/OFL.txt). It is bundled in `src/rh1charms/fonts/`, from [github.com/RedHatOfficial/RedHatFont](https://github.com/RedHatOfficial/RedHatFont) (the commit is in `src/rh1charms/fonts/README.md`). The captions of the hanging previews use it too.

## Trademarks and license

Red Hat and RH1 are trademarks of Red Hat, Inc. This project is not affiliated with or endorsed by Red Hat, Inc. The models do not use the Red Hat logo: please do not add it.

This repository is under **CC BY-SA 4.0** (see `LICENSE`), except the font, which keeps the SIL Open Font License 1.1.
