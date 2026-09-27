# Wallpaper

Two versions of the same picture — the classic Mac OS X Finder-face desktop, blown
up and cropped off the right edge of the frame — plus the script that regenerates it
in different palettes.

## Files

| File | What it is |
|---|---|
| `Mac OS Background` | The 832×624 JPEG original (4:3). Everything else descends from this. |
| `Mac OS Background 5120x2880.png` | 5K version of the original, blue palette. Only 4 flat colors, hard edges (rendered with anti-aliasing off). |
| `finder_wallpaper.py` | Generates the recolored versions. |
| `Mac OS Background Pro 5120x2880.png` | Script output: black + chrome, MacBook-Pro palette. |
| `Mac OS Background Pro Tangerine 5120x2880.png` | Script output: backlit orange plastic + frosted white, iBook G3 Tangerine palette. |
| `Mac OS Background Pro Lime 5120x2880.png` | Script output: same treatment in muted Lime. |
| `Mac OS Background Pro Strawberry 5120x2880.png` | Script output: same treatment in iMac G3 Strawberry. |
| `Mac OS Background Pro Grape 5120x2880.png` | Script output: same treatment in iMac G3 Grape. |
| `Mac OS Background Tangerine 5120x2880.png` | Script output: the original's flat, soft look in Tangerine. |
| `Mac OS Background Lime 5120x2880.png` | Script output: the original's flat, soft look in muted Lime. |
| `Mac OS Background Strawberry 5120x2880.png` | Script output: the original's flat, soft look in Strawberry. |
| `Mac OS Background Grape 5120x2880.png` | Script output: the original's flat, soft look in Grape. |
| `macintosh_wallpaper.py` | Generates the portrait Macintosh line-art wallpapers. |
| `Macintosh Background <Palette> 2880x5120.png` | Its output, one per palette above (Pro, Pro Tangerine/Lime/Strawberry/Grape, Tangerine/Lime/Strawberry/Grape). |
| `Macintosh Background Classic 2880x5120.png` | One-off: the icon's own colors on black, outline turned white, half size. |

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
3. **Shading** — each palette in the `PALETTES` dict supplies a background color, a
   glow, and three color ramps: `panel` (the face's near half), `near` (that half's
   features) and `far` (the low-contrast features on the other side). Painted in that
   order, then dithered so the shallow gradients don't band in 8-bit.

Palettes that want the original's flat look are built with the `flat()` helper: four
solid tints, no gradient, no glow, dither off. Those come out as a handful of exact
colors and a ~100 KB PNG, same as the original.

Only numpy is needed; the PNG is written straight out with `zlib`, so it runs on the
system `python3` with no Pillow install.

## Usage

```sh
python3 finder_wallpaper.py                                    # pro, 5120x2880, ~19s
python3 finder_wallpaper.py --palette pro-tangerine
python3 finder_wallpaper.py --palette pro-lime
python3 finder_wallpaper.py --palette pro-strawberry
python3 finder_wallpaper.py --palette pro-grape
python3 finder_wallpaper.py --palette tangerine                # flat, ~3s
python3 finder_wallpaper.py --palette lime
python3 finder_wallpaper.py --palette strawberry
python3 finder_wallpaper.py --palette grape
python3 finder_wallpaper.py --palette pro --size 3840x2160 --out 4k.png
```

Output name defaults to `Mac OS Background <Palette> <W>x<H>.png`.

## Tweaking

- **Colors** — add or edit an entry in `PALETTES`; use `flat()` for an original-style
  one. Nothing outside that dict needs to change. `SWEEP_DIR` sets the angle the
  feature gradient runs along; `glow_r` sets how far the background glow spreads.
- **Framing** — the geometry constants are in reference space; `--size` just rescales,
  it does not re-crop. To move the face, offset the `cx` values.

## One quirk worth knowing

It isn't one logo, it's two half-faces. The near (right) half is drawn about 6.5%
larger than the far (left) half — that's why the mouth is 143 px thick on the right
and 134 px on the left, and why the two mouth arcs are different curves. They meet
hidden underneath the center divider, which is drawn last and covers the seam.

## Macintosh (portrait)

`macintosh_wallpaper.py` makes a second picture for a Studio Display rotated 90°
(2880×5120): the pixel-art Macintosh icon — Mac, keyboard, cable, mouse and apple —
as lines alone, centred in the frame with the glow pooled behind it.

The icon is stored as a character grid at the top of the script, sampled cell by
cell off a screenshot, so only the line art made it in (no carousel arrows, no
watermark). It reuses every palette in `finder_wallpaper.py`, with the Finder face's
two strengths of line: the Mac, apple and mouse paint in the bright `near` ramp,
white in the Pro palettes, and the cable in the low-contrast `far` tint. The cable
turns bright where it plugs into the Mac, like the Finder's mouth crossing the
divider.

```sh
python3 macintosh_wallpaper.py --palette pro-grape   # ~20s
python3 macintosh_wallpaper.py --palette grape       # flat
```

Output is `Macintosh Background <Palette> 2880x5120.png`. `FRAME_W` sets the zoom
(frame width in cells), `CENTRE` the point of the art that lands mid-frame, and `MAC`
the per-row cell spans of the Mac, inside which the cable turns near. `CABLE_LIFT`
sets how far the cable is lifted from the `far` tint toward `near`.

`--palette classic` is a one-off that lives only in this script: the icon's own flat
colors on black, with its black outline turned white, at half the size of the others
(`frame_w` in the `CLASSIC` dict). The tints are the screenshot's raw pixel values,
since converting them out of the display profile to sRGB clips them to neon.
