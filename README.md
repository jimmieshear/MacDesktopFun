# Wallpaper

Two versions of the same picture — the classic Mac OS X Finder-face desktop, blown
up and cropped off the right edge of the frame — plus the script that generates the
second one.

## Files

| File | What it is |
|---|---|
| `Mac OS Background` | The 832×624 JPEG original (4:3). Everything else descends from this. |
| `Mac OS Background 5120x2880.png` | 5K version of the original, blue palette. Only 4 flat colors, hard edges (rendered with anti-aliasing off). |
| `finder_pro_wallpaper.py` | Generates the "Pro" version. |
| `Mac OS Background Pro 5120x2880.png` | Script output: black + chrome, MacBook-Pro palette. |

## How the script works

The blue 5K image was not traced pixel by pixel. Every edge in that artwork was
measured and found to be an exact **circle, axis-aligned ellipse, or straight line**
(all fit to under 0.65 px), so the script stores just those few numbers and redraws
the picture from scratch.

Three steps:

1. **Geometry** — a table of curves and lines at the top of the file, in a fixed
   5120×2880 reference coordinate space. Everything scales from there.
2. **Regions** — each part of the face (divider, nose, mouths, eyes, face panel) is
   built from those curves with `both()` / `either()`, i.e. intersection and union of
   signed distance fields. Distance to the nearest edge gives free, exact
   anti-aliasing: no supersampling, clean at any output size.
3. **Shading** — three color ramps (`PANEL_STOPS`, `CHROME_STOPS`, `GHOST_STOPS`)
   painted over a black background with a soft glow, then dithered so the shallow
   gradients don't band in 8-bit.

Only numpy is needed; the PNG is written straight out with `zlib`, so it runs on the
system `python3` with no Pillow install.

## Usage

```sh
python3 finder_pro_wallpaper.py                                # 5120x2880, ~19s
python3 finder_pro_wallpaper.py --size 3840x2160 --out 4k.png
```

## Tweaking

- **Colors** — edit the `*_STOPS` ramps, `BG_GLOW`, or `SWEEP_DIR` (the angle the
  metal gradient runs along). Nothing else needs to change.
- **Framing** — the geometry constants are in reference space; `--size` just rescales,
  it does not re-crop. To move the face, offset the `cx` values.

## One quirk worth knowing

It isn't one logo, it's two half-faces. The near (right) half is drawn about 6.5%
larger than the far (left) half — that's why the mouth is 143 px thick on the right
and 134 px on the left, and why the two mouth arcs are different curves. They meet
hidden underneath the center divider, which is drawn last and covers the seam.
