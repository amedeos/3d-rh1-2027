"""Headless previews: a small numpy z-buffer rasteriser (no OpenGL needed).

Smooth shading inside each CAD face, crisp edges between faces, outlines from depth and
normal discontinuities. Good enough to judge shapes and to make listing images.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

from .filaments import rgb
from .params import OUT


def _rgb(color) -> np.ndarray:
    return np.array(rgb(color) if isinstance(color, str) else color, dtype=float)


def _mesh(shape, tolerance: float):
    """Triangles plus per-vertex normals averaged within each CAD face."""
    tris, norms = [], []
    shapes = shape if isinstance(shape, (list, tuple)) else [shape]
    for face in (f for sh in shapes for f in sh.faces()):
        verts, idx = face.tessellate(tolerance, 0.2)
        if not idx:
            continue
        v = np.array([[p.X, p.Y, p.Z] for p in verts])
        t = np.array(idx)
        fn = np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])
        vn = np.zeros_like(v)
        for k in range(3):
            np.add.at(vn, t[:, k], fn)
        vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12
        tris.append(v[t])
        norms.append(vn[t])
    if not tris:
        return np.zeros((0, 3, 3)), np.zeros((0, 3, 3))
    return np.concatenate(tris), np.concatenate(norms)


def _look_at(eye, target, up=(0, 0, 1)):
    f = np.asarray(target, float) - eye
    f /= np.linalg.norm(f)
    r = np.cross(f, up)
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return np.stack([r, u, -f])  # rows: camera x, y, z (camera looks along -z)


# the object fills the image but for this share of its width or height on each side
# (whichever is tighter): render() fits what the camera really sees, so a wide object in an
# upright image is not cut off
MARGIN = 0.06
# render()'s camera and image when the caller gives none
ELEV, AZIM, SIZE, TOLERANCE = 28.0, -60.0, (900, 700), 0.08


def _meshes(items, tolerance: float = TOLERANCE) -> list:
    """(triangles, normals, colour) of every (shape, colour) item."""
    return [(*_mesh(s, tolerance), _rgb(c)) for s, c in items]


def _vertices(meshes) -> np.ndarray:
    """Every vertex of the meshes, as rows of x, y, z."""
    return np.concatenate([m[0].reshape(-1, 3) for m in meshes if len(m[0])])


def _camera(pts, elev, azim):
    """Eye, rotation (rows: camera x, y, z) and viewing direction for a camera that looks at
    the middle of the points from these angles."""
    lo, hi = pts.min(0), pts.max(0)
    center = (lo + hi) / 2
    radius = np.linalg.norm(hi - lo) / 2
    el, az = np.radians(elev), np.radians(azim)
    direction = np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])
    eye = center + direction * radius * 3.2
    return eye, _look_at(eye, center), direction


def fit(pts, size, elev, azim) -> float:
    """The focal length (pixels of an image of `size`) at which the points fill the image
    up to MARGIN on its tighter side, seen from this camera."""
    eye, rot, _ = _camera(pts, elev, azim)
    cam = (pts - eye) @ rot.T
    z = np.maximum(-cam[:, 2], 1e-3)
    spread_x, spread_y = np.abs(cam[:, 0] / z).max(), np.abs(cam[:, 1] / z).max()
    return (1 - 2 * MARGIN) * min(size[0] / 2 / spread_x, size[1] / 2 / spread_y)


def render(items, path, elev=ELEV, azim=AZIM, size=SIZE, ss=2, tolerance=TOLERANCE,
           meshes=None, background=((0.93, 0.92, 0.95), (0.72, 0.70, 0.76))):
    """Render [(shape, colour), ...] to `path`, fitted into the image (fit()). Angles in
    degrees, azim around +z. meshes: _meshes(items) made already, so that several views of
    the same items tessellate them only once."""
    meshes = _meshes(items, tolerance) if meshes is None else meshes
    pts = _vertices(meshes)
    eye, rot, direction = _camera(pts, elev, azim)
    w, h = size[0] * ss, size[1] * ss
    focal = fit(pts, size, elev, azim) * ss

    zbuf = np.full((h, w), np.inf)
    nbuf = np.zeros((h, w, 3))
    cbuf = np.zeros((h, w, 3))
    light = rot.T @ np.array([-0.45, 0.65, 0.62])
    light /= np.linalg.norm(light)
    fill = rot.T @ np.array([0.6, -0.2, 0.75])
    fill /= np.linalg.norm(fill)

    for tri, nrm, base in meshes:
        if not len(tri):
            continue
        cam = (tri - eye) @ rot.T  # (n, 3, 3) camera space
        z = -cam[..., 2]
        ok = (z > 1e-3).all(1)
        cam, z, nrm = cam[ok], z[ok], nrm[ok]
        sx = w / 2 + focal * cam[..., 0] / z
        sy = h / 2 - focal * cam[..., 1] / z
        for i in range(len(sx)):
            x0, x1 = int(max(sx[i].min(), 0)), int(min(np.ceil(sx[i].max()), w - 1))
            y0, y1 = int(max(sy[i].min(), 0)), int(min(np.ceil(sy[i].max()), h - 1))
            if x1 < x0 or y1 < y0:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            (ax_, bx, cx), (ay, by, cy) = sx[i], sy[i]
            den = (by - cy) * (ax_ - cx) + (cx - bx) * (ay - cy)
            if abs(den) < 1e-9:
                continue
            l0 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
            l1 = ((cy - ay) * (gx - cx) + (ax_ - cx) * (gy - cy)) / den
            l2 = 1 - l0 - l1
            inside = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
            if not inside.any():
                continue
            iz = l0 / z[i, 0] + l1 / z[i, 1] + l2 / z[i, 2]  # perspective-correct
            depth = 1 / np.where(inside, iz, 1e-12)
            sub = zbuf[y0:y1 + 1, x0:x1 + 1]
            win = inside & (depth < sub)
            if not win.any():
                continue
            sub[win] = depth[win]
            n = (l0[..., None] * nrm[i, 0] / z[i, 0] + l1[..., None] * nrm[i, 1] / z[i, 1]
                 + l2[..., None] * nrm[i, 2] / z[i, 2]) / iz[..., None]
            nbuf[y0:y1 + 1, x0:x1 + 1][win] = n[win]
            cbuf[y0:y1 + 1, x0:x1 + 1][win] = base

    hit = np.isfinite(zbuf)
    n = nbuf / (np.linalg.norm(nbuf, axis=2, keepdims=True) + 1e-12)
    view = direction  # towards the camera
    flip = (n @ view) < 0
    n[flip] *= -1
    diff = np.clip(n @ light, 0, 1)
    diff2 = np.clip(n @ fill, 0, 1)
    half = light + view
    half /= np.linalg.norm(half)
    spec = np.clip(n @ half, 0, 1) ** 40
    shade = 0.28 + 0.62 * diff + 0.18 * diff2
    img = cbuf * shade[..., None] + 0.22 * spec[..., None]

    # outlines from depth / normal discontinuities
    zf = np.where(hit, zbuf, zbuf[hit].max() * 1.5 if hit.any() else 1)
    edge = np.zeros_like(zf, dtype=bool)
    for axis in (0, 1):  # compare each pixel with its next neighbour (no wrap-around)
        a = [slice(None)] * 2
        b = [slice(None)] * 2
        a[axis], b[axis] = slice(None, -1), slice(1, None)
        a, b = tuple(a), tuple(b)
        dz = np.abs(zf[a] - zf[b])
        dn = 1 - np.sum(n[a] * n[b], axis=2)
        edge[a] |= (dz > 0.004 * zf[a]) | ((dn > 0.35) & hit[a])
    img[edge & hit] *= 0.35

    top, bottom = (np.array(c) for c in background)
    t = np.linspace(0, 1, h)[:, None, None]
    bg = top * (1 - t) + bottom * t
    out = np.where(hit[..., None], img, np.broadcast_to(bg, img.shape))
    out = (np.clip(out, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(out).resize(size, Image.LANCZOS).save(path)



# --- the views of a charm ---------------------------------------------------------------
# straight from the front, a little from above and from the right
FRONT = {"elev": 12, "azim": -70}
BACK = {"elev": 12, "azim": 110}  # the bed side: pockets, bar and channel
EDGE = {"elev": 4, "azim": -90}  # the print pose seen along y: the stack of bands
TOP = {"elev": 35, "azim": -60}  # a plate lying on the bed
BELOW = {"elev": -35, "azim": -60}  # ...and from under the bed
WIDE = 1.3  # a part wider than this many times its height gets a landscape image
VIEWS = ("front", "back", "edge", "flat", "hang")  # <name>_<view>.png

PAD = 10  # pixels around a 2D preview
BACKGROUND = (214, 222, 230)  # behind a 2D preview
PLUMB = "#e6008c"  # the plumb line of the hanging preview: no filament has this colour


def _frame(w: float, h: float) -> tuple[int, int]:
    """Image size for a view of a part w wide and h high: landscape for a wide part."""
    return (1400, 600) if w > WIDE * h else (800, 900)


def _edge_frame(w: float) -> tuple[int, int]:
    return (1600, 420) if w > 60 else (1000, 420)


def _to_px(bounds, px_per_mm: float, pad: int = PAD):
    """The map from mm (y up) to the pixels (y down) of a 2D preview of these bounds."""
    x0, _, _, y1 = bounds
    return lambda x, y: ((x - x0) * px_per_mm + pad, (y1 - y) * px_per_mm + pad)


def mask(geom, bounds, px_per_mm: float, pad: int = PAD) -> Image.Image:
    """A 1-bit image of a geometry (y up), inside bounds = (x0, y0, x1, y1) plus pad pixels.

    Each polygon gets its own layer (outside filled, holes cleared), and the layers are
    OR-ed. Drawing them all on one image would let a later polygon's hole erase an island
    that sits inside it.
    """
    from PIL import ImageChops, ImageDraw

    from .relief import polygons

    x0, y0, x1, y1 = bounds
    size = (int((x1 - x0) * px_per_mm) + 2 * pad, int((y1 - y0) * px_per_mm) + 2 * pad)
    to_px = _to_px(bounds, px_per_mm, pad)

    def pts(coords):
        return [to_px(x, y) for x, y in coords]

    out = Image.new("1", size, 0)
    for poly in polygons(geom):
        layer = Image.new("1", size, 0)
        draw = ImageDraw.Draw(layer)
        draw.polygon(pts(poly.exterior.coords), fill=1)
        for hole in poly.interiors:
            draw.polygon(pts(hole.coords), fill=0)
        out = ImageChops.logical_or(out, layer)
    return out


def _flat_image(bands, colours, px_per_mm: float) -> Image.Image:
    """The bands in 2D, one colour per band, drawn by mask() inside bands[0].bounds."""
    from .filaments import FILAMENTS

    img = None
    for band, name in zip(bands, colours):
        m = mask(band, bands[0].bounds, px_per_mm)
        if img is None:
            img = Image.new("RGB", m.size, BACKGROUND)
        img.paste(FILAMENTS[name], mask=m)
    return img


def flat_preview(c, path: Path, px_per_mm: float = 12.0) -> Path:
    """The charm seen from the front in 2D, one colour per band: check the colours, the
    letters and the grooves."""
    from .wear import layout

    img = _flat_image(layout(c).bands, c.bands, px_per_mm)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def hang_preview(c, path: Path, px_per_mm: float = 12.0) -> Path:
    """The charm seen from the front, with a plumb line from where it hangs (the top of the
    eyelet hole, or the middle of a lone magnet) and a mark on the centre of mass of its
    solids: if the mark lies on the line, the charm hangs upright.

    The mark comes from the solids (wear.mass_centre), not from the 2D centre that placed
    the eyelet or the magnet, so the picture checks the placement."""
    from PIL import ImageDraw, ImageFont

    from .text import FONT
    from .wear import hang_angle, layout, mass_centre

    lay = layout(c)
    if lay.pivot is None:
        raise ValueError(f"{c.name} does not hang: no eyelet and not one magnet")
    centre = mass_centre(c)
    to_px = _to_px(lay.bands[0].bounds, px_per_mm)

    def px(x: float, y: float) -> tuple[int, int]:
        return tuple(round(v) for v in to_px(x, y))

    flat = _flat_image(lay.bands, c.bands, px_per_mm)
    font = ImageFont.truetype(str(FONT), 22)
    caption = f"{c.name}: hangs {hang_angle(lay.pivot, centre):.2f}° off upright"
    _, _, text_w, text_h = font.getbbox(caption)
    img = Image.new("RGB", (max(flat.width, text_w + 2 * PAD), flat.height + text_h + 2 * PAD),
                    BACKGROUND)
    img.paste(flat, (0, 0))
    draw = ImageDraw.Draw(img)
    hx, hy, r = lay.pivot
    top = px(hx, hy + r)
    draw.line([top, (top[0], flat.height - 1)], fill=PLUMB, width=3)
    if r == 0:  # a magnet: show the pocket it turns in
        rr = round(c.pocket_d / 2 * px_per_mm)
        draw.ellipse([top[0] - rr, top[1] - rr, top[0] + rr, top[1] + rr], outline=PLUMB, width=2)
    cx, cy = px(*centre)
    mark = round(1.5 * px_per_mm)
    draw.ellipse([cx - mark, cy - mark, cx + mark, cy + mark], outline=PLUMB, width=3)
    draw.line([(cx - mark, cy), (cx + mark, cy)], fill=PLUMB, width=3)
    draw.text((PAD, flat.height + PAD), caption, fill=(28, 26, 30), font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def charm_images(c, out: Path) -> list[Path]:
    """Every image of one charm: from the front and the back (worn), the edge profile (as
    printed), the bands in 2D and, if it hangs, the plumb line."""
    from .wear import coloured, layout

    out.mkdir(parents=True, exist_ok=True)
    lay = layout(c)
    w, h, _ = lay.size
    paths = {v: out / f"{c.name}_{v}.png" for v in VIEWS}
    worn = coloured(c)
    meshes = _meshes(worn)  # once for both views
    render(worn, paths["front"], size=_frame(w, h), meshes=meshes, **FRONT)
    render(worn, paths["back"], size=_frame(w, h), meshes=meshes, **BACK)
    render(coloured(c, stand=False), paths["edge"], size=_edge_frame(w), **EDGE)
    flat_preview(c, paths["flat"])
    if lay.pivot is not None:
        hang_preview(c, paths["hang"])
    else:
        paths["hang"].unlink(missing_ok=True)  # an older image from when it hung
        del paths["hang"]
    return list(paths.values())


def plate_images(name: str, part, colour: str, out: Path) -> list[Path]:
    """A part in one colour (a counter plate, a gauge): from above, from below, and the
    edge profile."""
    out.mkdir(parents=True, exist_ok=True)
    bb = part.bounding_box()
    items = [(part, colour)]
    meshes = _meshes(items)  # once for the three views
    paths = [out / f"{name}_{v}.png" for v in ("front", "back", "edge")]
    render(items, paths[0], size=_frame(bb.size.X, bb.size.Y), meshes=meshes, **TOP)
    render(items, paths[1], size=_frame(bb.size.X, bb.size.Y), meshes=meshes, **BELOW)
    render(items, paths[2], size=_edge_frame(bb.size.X), meshes=meshes, **EDGE)
    return paths


def all_images(charms, out: Path = OUT) -> list[Path]:
    """The images of every charm, and of the single-colour parts they need (the counter
    plates and the gauges, as export makes them: magnets.extras), into out/render."""
    from .magnets import extras

    folder = out / "render"
    paths = []
    for c in charms:
        paths += charm_images(c, folder)
    for name, colour, build in extras(charms):
        paths += plate_images(name, build(), colour, folder)
    return paths


if __name__ == "__main__":  # the same names and options as `rh1charms render`
    from . import main

    main(["render", *sys.argv[1:]])
