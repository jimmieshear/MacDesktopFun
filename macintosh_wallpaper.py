#!/usr/bin/env python3
"""
Pixel-art Macintosh wallpaper, portrait, in the Finder wallpapers' palettes.

The line art -- the Mac, its keyboard, the cable, the mouse and the apple --
is stored below as a grid of cells, sampled off a screenshot of the icon.
Anything that was not line art in that screenshot (a carousel's arrows and
their bubbles, a watermark) simply isn't in the grid.

The treatment is the Finder face's: nothing but lines on the stage, split
into two sides that read at different strengths --

    near    the Mac, the apple and the mouse, in the palette's bright
            feature colour (white, in the Pro palettes)
    far     the cable, in the low-contrast tint as the Finder's far half is,
            lifted part way toward near so it still carries some colour

The art sits centred in the frame, the glow pooled behind it.

The cable crosses over where it plugs in, and changes tint at the Mac's
side the way the Finder's mouth does at the divider.

One extra palette, "classic", keeps the icon's own colours instead: flat,
on black, with the icon's black outline turned white and every other colour
as it was.  It draws at half the size of the others.

Default size is a 5K Studio Display rotated 90 degrees.  Needs only numpy.

    python3 macintosh_wallpaper.py [--palette NAME] [--size WxH] [--out FILE]
"""

import argparse
import math

import numpy as np

from finder_wallpaper import PALETTES, ramp, write_png

# --------------------------------------------------------------------------
# The icon, one character per cell.  Any non-dot is a line; the letters just
# record the icon's own colours (K black, G leaf, R cable, Y screen and mouse
# ball, B keys).  The cable (R) is the one line that paints far.
# --------------------------------------------------------------------------
ART = """
................................
.............KKKKKKKKKKKK.......
............K...................
............K....YYYYYY...K.....
............K..........Y..K.....
............K..........Y..K.....
.....G......K..........Y..K.....
....GG......K..........Y..K.....
....G.......K..........Y..K.....
.KK..KK.....K..........Y..K.....
K..KK..K....K..........Y..K.....
K......K....K...YYYYYYY...K.....
K...........K.............K.....
K...........K.............K.....
.K..K.K............KKKKK..K.....
..KK.K....................K.....
........RRRRRR............K.....
......RR........................
.....R.........KKKKKKKKKKKKK....
.....R......................K...
......RRRRR........BBBBBBBB..K..
...........R.........B.B.B.B..K.
...........R............B.B.B..K
..........R....................K
..........R............KKKKKKKK.
...........RR...................
.............R..................
................KK..............
...............K..K.............
..............K..Y.K............
................Y...K...........
....................K...........
...................K............
................................
"""

# Inclusive spans of cells on each row covering the Mac -- body, outline and
# keyboard.  The cable enters through the gap low in the Mac's left side and
# turns near inside these spans.
MAC = {**{r: (13, 31) for r in range(1, 25)},
       **{r: (12, 31) for r in range(2, 14)}}

# --------------------------------------------------------------------------
# Framing.  The frame is FRAME_W cells across, and the art's centre (CENTRE,
# in cells) lands in the middle of it.
# --------------------------------------------------------------------------
FRAME_W = 54.0
CENTRE = (16.0, 17.0)        # middle of the drawn cells, cols 0-31, rows 1-32

CABLE_LIFT = 0.35            # cable sits this far from far toward near

# Glow centre and gradient sweep, as fractions of the frame.
GLOW_C = (0.5, 0.5)
SWEEP_DIR = (0.5, math.sqrt(3.0) / 2.0)


# The icon in its own colours.  Only this script uses it, so it lives here
# rather than in finder_wallpaper.PALETTES.  The tints are the screenshot's
# raw pixel values -- what the icon looks like on screen; converting them
# from the display profile to sRGB pushes them out to clipped neon.
CLASSIC = {
    'base': (0x00, 0x00, 0x00), 'glow': (0x00, 0x00, 0x00), 'glow_r': 1.0,
    'dither': False, 'frame_w': 2.0 * FRAME_W,
    'cells': {'K': (0xff, 0xff, 0xff),     # outline, black in the icon
              'G': (0x32, 0x75, 0x1f),     # leaf
              'R': (0xde, 0x35, 0x1c),     # cable
              'Y': (0xd8, 0xdb, 0x45),     # screen, mouse ball
              'B': (0x23, 0x00, 0xea)},    # keys
}
ALL = dict(PALETTES, classic=CLASSIC)


def grid(art):
    return np.array([list(r) for r in art.strip('\n').split('\n')])


def parse(art):
    g = grid(art)
    return g != '.', g == 'R'


def spans(shape, table):
    m = np.zeros(shape, bool)
    for r, (c0, c1) in table.items():
        m[r, c0:c1 + 1] = True
    return m


def render(width, height, pal):
    ink, cable = parse(ART)
    far = cable & ~spans(ink.shape, MAC)
    near = ink & ~far

    cell = width / pal.get('frame_w', FRAME_W)
    ox = CENTRE[0] - width / cell / 2.0
    oy = CENTRE[1] - height / cell / 2.0
    ci = np.floor((np.arange(width) + 0.5) / cell + ox).astype(int)
    cj = np.floor((np.arange(height) + 0.5) / cell + oy).astype(int)
    h, w = ink.shape
    okx, oky = (ci >= 0) & (ci < w), (cj >= 0) & (cj < h)
    ci, cj = np.clip(ci, 0, w - 1), np.clip(cj, 0, h - 1)

    def lookup(m):
        return m[cj][:, ci] & oky[:, None] & okx[None, :]

    X, Y = np.meshgrid(np.arange(width) + 0.5, np.arange(height) + 0.5)
    unit = max(width, height) / 5120.0     # glow_r is in 5K units

    d = np.hypot(X - GLOW_C[0] * width, Y - GLOW_C[1] * height)
    k = np.clip(1.0 - d / (pal['glow_r'] * unit), 0.0, 1.0)
    k = k * k * k * (k * (k * 6.0 - 15.0) + 10.0)
    base = np.array(pal['base'], float)
    img = base + (np.array(pal['glow'], float) - base) * k[..., None]

    # The feature sweep spans the art's own bounding box, as it spans the
    # Finder face, so the lines run the whole white-to-tint ramp.
    rows, cols = np.nonzero(ink)
    x0, x1 = (cols.min() - ox) * cell, (cols.max() + 1 - ox) * cell
    y0, y1 = (rows.min() - oy) * cell, (rows.max() + 1 - oy) * cell
    lo = x0 * SWEEP_DIR[0] + y0 * SWEEP_DIR[1]
    hi = x1 * SWEEP_DIR[0] + y1 * SWEEP_DIR[1]
    t = (X * SWEEP_DIR[0] + Y * SWEEP_DIR[1] - lo) / (hi - lo)
    if 'cells' in pal:                     # flat, one colour per letter
        g = grid(ART)
        for ch, colour in pal['cells'].items():
            img[lookup(g == ch)] = colour
    else:
        near_c, far_c = ramp(t, pal['near']), ramp(t, pal['far'])
        far_c += (near_c - far_c) * CABLE_LIFT
        for mask, colour in ((lookup(far), far_c), (lookup(near), near_c)):
            img[mask] = colour[mask]

    if pal.get('dither', True):
        img += np.random.RandomState(7).triangular(-1.0, 0.0, 1.0, img.shape)
    return np.clip(img + 0.5, 0, 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--palette', default='pro', choices=sorted(ALL))
    ap.add_argument('--size', default='2880x5120')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()
    w, h = (int(v) for v in args.size.lower().split('x'))
    out = args.out or 'Macintosh Background %s %dx%d.png' % (
        args.palette.replace('-', ' ').title(), w, h)
    write_png(out, render(w, h, ALL[args.palette]))
    print('wrote %s (%dx%d)' % (out, w, h))


if __name__ == '__main__':
    main()
