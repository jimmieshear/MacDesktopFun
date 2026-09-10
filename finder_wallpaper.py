#!/usr/bin/env python3
"""
Finder face wallpaper, redrawn from geometry in a choice of palettes.

Same composition as "Mac OS Background 5120x2880.png": a hugely magnified
Finder face cropped off the right edge of the frame.  Every edge in that
artwork turned out to be either an exact ellipse or a straight line, so this
script does not trace pixels -- it evaluates the geometry as a signed distance
field.  That means genuinely clean, resolution independent, anti-aliased
edges (the original was rendered with anti-aliasing off).

Palettes:
    pro             black stage, chrome silver features   (MacBook Pro)
    pro-tangerine   backlit orange plastic, frosted white (iBook G3 Tangerine)
    pro-lime        the same, in muted Lime
    pro-strawberry  the same, in iMac G3 Strawberry
    pro-grape       the same, in iMac G3 Grape
    tangerine       the original's four flat tints, hue rotated to Tangerine
    lime            the same, in muted Lime
    strawberry      the same, in Strawberry
    grape           the same, in Grape

Only numpy is required; the PNG is written directly with zlib.

    python3 finder_wallpaper.py [--palette NAME] [--size WxH] [--out FILE]
"""

import argparse
import math
import struct
import zlib

import numpy as np

# --------------------------------------------------------------------------
# Geometry, in the reference 5120x2880 coordinate space.
# Curved edges are axis aligned ellipses (cx, cy, a, b); a == b is a circle.
# Straight edges are ((x0, y0), slope).
# --------------------------------------------------------------------------
REF_W, REF_H = 5120.0, 2880.0

UO = (5808.85,  968.70, 3108.25, 3108.25)   # divider, upper arc, outer edge
UI = (5880.44,  973.81, 3037.05, 3037.05)   # divider, upper arc, inner edge
LO = (5452.22, 1413.12, 2117.42, 2117.42)   # divider, lower arc, outer edge
LI = (5241.69, 1360.00, 1772.89, 1948.92)   # divider, lower arc, inner edge

MLU = (2503.53, 180.39, 2180.84, 2180.84)   # left mouth,  upper edge
MLL = (2482.37,  89.20, 2407.60, 2407.60)   # left mouth,  lower edge
MRU = (2795.65, 376.66, 1871.56, 1871.56)   # right mouth, upper edge
MRL = (2784.63, 363.53, 2030.51, 2030.51)   # right mouth, lower edge

NOSE_UP = ((3184.5, 1669.79), -0.39366)   # nose wedge, upper edge
NOSE_LO = ((3159.5, 1830.86), -0.39391)   # nose wedge, lower edge
CAP_L   = ((2350.5, 2420.40), -3.90020)   # left mouth, end cut
CAP_R   = ((4247.5, 1663.50),  0.65230)   # right mouth, end cut

#            cx       cy      length  thickness  angle(deg)
EYE_L = (2222.8, 1209.4, 359.7, 151.6, 68.550)
EYE_R = (3420.2,  736.3, 367.7, 158.6, 68.395)

# Points known to lie inside each element, used to orient the half planes.
IN_UPPER_DIV = (2820.0,  900.0)
IN_NOSE      = (3100.0, 1790.0)
IN_LOWER_DIV = (3800.0, 2600.0)
IN_MOUTH_L   = (2600.0, 2430.0)
IN_MOUTH_R   = (4000.0, 1900.0)
IN_FACE      = (4000.0,  200.0)

# --------------------------------------------------------------------------
# Palettes.  Four slots each: the stage, the soft pool of light behind the
# face, the panel (right half of the face) and the two feature ramps -- "near"
# for the right half's features, "far" for the left half's, which the original
# keeps deliberately low contrast.
# --------------------------------------------------------------------------
GLOW_C = (3150.0, 1350.0)          # glow centre, reference coords


def flat(stage, panel, near, far):
    """A palette in the original's own style: four solid tints, nothing else.

    Dithering is off, so the output stays a handful of exact colours and
    compresses to a few hundred KB the way the original does.
    """
    return {'base': stage, 'glow': stage, 'glow_r': 1.0, 'dither': False,
            'panel': [(0.0, panel)], 'near': [(0.0, near)], 'far': [(0.0, far)]}


PALETTES = {
    # Black stage, glossy graphite panel, chrome features.
    'pro': {
        'base': (0x0e, 0x0e, 0x0e),
        'glow': (0x23, 0x25, 0x2c),
        'glow_r': 5200.0,
        'panel': [
            (0.00, (0x3c, 0x3e, 0x44)),
            (0.28, (0x25, 0x27, 0x2c)),
            (0.62, (0x14, 0x15, 0x18)),
            (1.00, (0x08, 0x08, 0x0a)),
        ],
        'near': [
            (0.00, (0xff, 0xff, 0xff)),
            (0.12, (0xf1, 0xf3, 0xf6)),
            (0.32, (0xb4, 0xb8, 0xc0)),
            (0.47, (0x74, 0x78, 0x80)),
            (0.58, (0x63, 0x66, 0x6d)),
            (0.74, (0xa2, 0xa6, 0xad)),
            (0.89, (0xd8, 0xdb, 0xe1)),
            (1.00, (0xef, 0xf1, 0xf5)),
        ],
        'far': [
            (0.00, (0x70, 0x72, 0x7b)),
            (0.35, (0x54, 0x57, 0x5f)),
            (0.60, (0x45, 0x47, 0x4e)),
            (1.00, (0x59, 0x5c, 0x64)),
        ],
    },
    # iBook G3 Tangerine, dramatised: translucent orange shell lit from within,
    # frosted white accents.  Panel colours are sampled off the lid of a real
    # one -- #d27006 the body, #e8991c the lit top edge, #be411a the base.
    'pro-tangerine': {
        'base': (0x1f, 0x11, 0x0c),
        'glow': (0x68, 0x22, 0x10),
        'glow_r': 5200.0,
        'panel': [
            (0.00, (0xe0, 0x8c, 0x14)),
            (0.30, (0xc4, 0x63, 0x06)),
            (0.65, (0x82, 0x31, 0x06)),
            (1.00, (0x36, 0x10, 0x03)),
        ],
        'near': [
            (0.00, (0xff, 0xff, 0xff)),
            (0.12, (0xff, 0xf5, 0xe6)),
            (0.32, (0xff, 0xd9, 0xa8)),
            (0.47, (0xf5, 0xac, 0x55)),
            (0.58, (0xea, 0x95, 0x34)),
            (0.74, (0xfd, 0xd2, 0x9c)),
            (0.89, (0xff, 0xee, 0xda)),
            (1.00, (0xff, 0xfa, 0xf2)),
        ],
        'far': [
            (0.00, (0xc6, 0x55, 0x14)),
            (0.35, (0x9f, 0x3f, 0x0d)),
            (0.60, (0x86, 0x30, 0x09)),
            (1.00, (0xb1, 0x49, 0x11)),
        ],
    },
    # iMac/iBook Lime, same backlit treatment as pro-tangerine.  Hue and
    # saturation come off the old "Lime Sharp" desktop picture (core #36c32b,
    # hue ~115) pulled a third of the way down in saturation and a little
    # yellower, which is where lime stops looking neon.
    'pro-lime': {
        'base': (0x12, 0x1c, 0x0f),
        'glow': (0x2d, 0x59, 0x1f),
        'glow_r': 5200.0,
        'panel': [
            (0.00, (0x5d, 0xc7, 0x3c)),
            (0.30, (0x49, 0xb0, 0x29)),
            (0.65, (0x33, 0x79, 0x1e)),
            (1.00, (0x19, 0x39, 0x0f)),
        ],
        'near': [
            (0.00, (0xff, 0xff, 0xff)),
            (0.12, (0xee, 0xfb, 0xea)),
            (0.32, (0xc4, 0xf0, 0xb7)),
            (0.47, (0x89, 0xda, 0x70)),
            (0.58, (0x6f, 0xcb, 0x53)),
            (0.74, (0xbb, 0xed, 0xac)),
            (0.89, (0xe6, 0xf9, 0xe0)),
            (1.00, (0xf6, 0xfd, 0xf4)),
        ],
        'far': [
            (0.00, (0x4e, 0xa8, 0x32)),
            (0.35, (0x3c, 0x87, 0x25)),
            (0.60, (0x32, 0x72, 0x1e)),
            (1.00, (0x44, 0x95, 0x2c)),
        ],
    },
    # iMac G3 Strawberry, same backlit treatment.  Hue comes off a photo of a
    # real Strawberry tray -- the lit core reads #f62960, the shadowed shell
    # #5d162a, both sitting at hue ~344, i.e. red already leaning pink.  Held
    # a touch below the photo's saturation so it stays plastic, not neon.
    'pro-strawberry': {
        'base': (0x24, 0x0e, 0x15),
        'glow': (0x70, 0x10, 0x30),
        'glow_r': 5200.0,
        'panel': [
            (0.00, (0xf6, 0x28, 0x56)),
            (0.30, (0xd8, 0x17, 0x4c)),
            (0.65, (0x8f, 0x12, 0x3d)),
            (1.00, (0x3b, 0x08, 0x1c)),
        ],
        'near': [
            (0.00, (0xff, 0xff, 0xff)),
            (0.12, (0xff, 0xe8, 0xed)),
            (0.32, (0xff, 0xaf, 0xc2)),
            (0.47, (0xf5, 0x62, 0x86)),
            (0.58, (0xea, 0x43, 0x6c)),
            (0.74, (0xfd, 0xa4, 0xb9)),
            (0.89, (0xff, 0xdd, 0xe5)),
            (1.00, (0xff, 0xf3, 0xf6)),
        ],
        'far': [
            (0.00, (0xd6, 0x25, 0x60)),
            (0.35, (0xac, 0x1b, 0x4d)),
            (0.60, (0x91, 0x15, 0x41)),
            (1.00, (0xbf, 0x20, 0x57)),
        ],
    },
    # iMac G3 Grape, same backlit treatment.  The real shell is the darkest of
    # the five -- a photo of one reads #61009e at its lit crest and #190032 in
    # shadow, hue ~275 at full saturation.  Violet carries the least luminance
    # of any hue, so this is the one palette lifted in value rather than pulled
    # down: the panel opens brighter than the plastic ever does, which is what
    # keeps the face from going to mud.  Saturation comes off ~15% in exchange,
    # or the lit half turns neon.
    'pro-grape': {
        'base': (0x1a, 0x0b, 0x26),
        'glow': (0x46, 0x06, 0x70),
        'glow_r': 5200.0,
        'panel': [
            (0.00, (0x91, 0x2c, 0xca)),
            (0.30, (0x75, 0x1d, 0xb0)),
            (0.65, (0x47, 0x15, 0x75)),
            (1.00, (0x1c, 0x09, 0x31)),
        ],
        'near': [
            (0.00, (0xff, 0xff, 0xff)),
            (0.12, (0xf8, 0xeb, 0xff)),
            (0.32, (0xe5, 0xb9, 0xff)),
            (0.47, (0xc5, 0x75, 0xf5)),
            (0.58, (0xb2, 0x58, 0xea)),
            (0.74, (0xe0, 0xaf, 0xfd)),
            (0.89, (0xf4, 0xe1, 0xff)),
            (1.00, (0xfb, 0xf5, 0xff)),
        ],
        'far': [
            (0.00, (0x6d, 0x27, 0xaa)),
            (0.35, (0x55, 0x1d, 0x89)),
            (0.60, (0x46, 0x17, 0x73)),
            (1.00, (0x60, 0x22, 0x98)),
        ],
    },
    # The original desktop picture's own recipe -- four flat tints, no
    # gradient, no glow -- with its blues rotated to the Tangerine hue.  The
    # gaps between the four tints are widened 2.2x from the original's, which
    # at this lightness is what keeps the divider and the two halves legible.
    'tangerine': flat((0xff, 0xc1, 0x82),    # stage
                      (0xff, 0xdb, 0xb7),    # face panel
                      (0xff, 0x9d, 0x3b),    # near half features
                      (0xff, 0xac, 0x59)),   # far half features
    # Same flat treatment in Lime.  Green carries more luminance than orange,
    # so this one sits at about half saturation to stay muted.
    'lime': flat((0xa1, 0xe3, 0x96),
                 (0xc6, 0xee, 0xc0),
                 (0x6e, 0xd4, 0x5e),
                 (0x83, 0xda, 0x75)),
    # Strawberry, flat.  Same spacing between the four tints as Tangerine,
    # rotated to hue 344; red pales toward pink rather than toward peach.
    'strawberry': flat((0xff, 0x8c, 0xaa),
                       (0xff, 0xbd, 0xce),
                       (0xff, 0x4b, 0x7b),
                       (0xff, 0x66, 0x8f)),
    # Grape, flat.  Hue 276, saturation a shade under the others' -- violet
    # this pale reads as lavender, and any more of it starts to buzz.
    'grape': flat((0xd8, 0x9e, 0xff),
                  (0xe9, 0xc7, 0xff),
                  (0xc2, 0x66, 0xff),
                  (0xcb, 0x7e, 0xff)),
}

# Direction of the gradient sweep across the features: 60 degrees, down right.
SWEEP_DIR = (0.5, math.sqrt(3.0) / 2.0)
SWEEP_MIN, SWEEP_MAX = 1000.0, 4700.0


# --------------------------------------------------------------------------
# Signed distance helpers.  Positive is inside; distances are in reference
# units, and coverage comes from clamping the distance across one pixel.
# --------------------------------------------------------------------------
def disc(X, Y, e):
    """Signed distance to an axis aligned ellipse; positive inside."""
    cx, cy, a, b = e
    u, v = (X - cx) / a, (Y - cy) / b
    grad = 2.0 * np.hypot(u / a, v / b)
    return (1.0 - u * u - v * v) / np.maximum(grad, 1e-12)


def hole(X, Y, e):
    return -disc(X, Y, e)


def half(X, Y, line, inside_pt):
    (x0, y0), m = line
    k = 1.0 / math.hypot(m, 1.0)
    s = math.copysign(1.0, m * (inside_pt[0] - x0) - (inside_pt[1] - y0))
    return (m * (X - x0) - (Y - y0)) * (k * s)


def bar(X, Y, eye):
    cx, cy, length, thick, deg = eye
    t = math.radians(deg)
    ct, st = math.cos(t), math.sin(t)
    u = (X - cx) * ct + (Y - cy) * st
    v = -(X - cx) * st + (Y - cy) * ct
    return np.minimum(length / 2.0 - np.abs(u), thick / 2.0 - np.abs(v))


def both(*fields):
    out = fields[0]
    for f in fields[1:]:
        out = np.minimum(out, f)
    return out


def either(*fields):
    out = fields[0]
    for f in fields[1:]:
        out = np.maximum(out, f)
    return out


def face_panel(X, Y):
    """Right half of the face: the lit graphite plane."""
    return either(both(disc(X, Y, UI), half(X, Y, NOSE_UP, IN_FACE)),
                  disc(X, Y, LI))


def divider(X, Y):
    """Centre line of the face plus the nose wedge, as one stroke."""
    upper = both(disc(X, Y, UO), hole(X, Y, UI),
                 half(X, Y, NOSE_LO, IN_UPPER_DIV))
    nose = both(half(X, Y, NOSE_UP, IN_NOSE), half(X, Y, NOSE_LO, IN_NOSE),
                disc(X, Y, UO), hole(X, Y, LI))
    lower = both(disc(X, Y, LO), hole(X, Y, LI),
                 half(X, Y, NOSE_UP, IN_LOWER_DIV))
    return either(upper, nose, lower)


def mouth_far(X, Y):
    """Mouth of the far half; it tucks under the divider on the right."""
    return both(disc(X, Y, MLL), hole(X, Y, MLU),
                half(X, Y, CAP_L, IN_MOUTH_L), hole(X, Y, LO))


def mouth_near(X, Y):
    """Mouth of the near half; it starts under the divider on the left."""
    return both(disc(X, Y, MRL), hole(X, Y, MRU),
                half(X, Y, CAP_R, IN_MOUTH_R), disc(X, Y, LO))


# --------------------------------------------------------------------------
# Shading
# --------------------------------------------------------------------------
def ramp(t, stops):
    """Sample a colour ramp; t is any float array, result is (..., 3) float."""
    t = np.clip(t, 0.0, 1.0)
    pos = np.array([s[0] for s in stops])
    cols = np.array([s[1] for s in stops], dtype=np.float64)
    out = np.empty(t.shape + (3,))
    for ch in range(3):
        out[..., ch] = np.interp(t, pos, cols[:, ch])
    return out


def sweep(X, Y):
    t = (X * SWEEP_DIR[0] + Y * SWEEP_DIR[1] - SWEEP_MIN)
    return t / (SWEEP_MAX - SWEEP_MIN)


def background(X, Y, pal):
    d = np.hypot(X - GLOW_C[0], Y - GLOW_C[1]) / pal['glow_r']
    k = np.clip(1.0 - d, 0.0, 1.0)
    k = k * k * k * (k * (k * 6.0 - 15.0) + 10.0)   # smootherstep falloff
    base = np.array(pal['base'], dtype=np.float64)
    glow = np.array(pal['glow'], dtype=np.float64)
    return base + (glow - base) * k[..., None]


def over(dst, colour, sd, px):
    """Composite `colour` where the field `sd` is inside, anti-aliased."""
    a = np.clip(sd / px + 0.5, 0.0, 1.0)[..., None]
    return dst * (1.0 - a) + colour * a


# --------------------------------------------------------------------------
def render(width, height, pal, block=192):
    out = np.empty((height, width, 3), dtype=np.uint8)
    sx, sy = REF_W / width, REF_H / height
    px = max(sx, sy)                       # one output pixel, in ref units
    xs = (np.arange(width) + 0.5) * sx
    rng = np.random.RandomState(7)         # fixed, so renders are repeatable

    for y0 in range(0, height, block):
        y1 = min(y0 + block, height)
        ys = (np.arange(y0, y1) + 0.5) * sy
        X, Y = np.meshgrid(xs, ys)

        img = background(X, Y, pal)
        img = over(img, ramp(Y / REF_H, pal['panel']), face_panel(X, Y), px)

        t = sweep(X, Y)
        far = either(mouth_far(X, Y), bar(X, Y, EYE_L))
        img = over(img, ramp(t, pal['far']), far, px)

        near = either(divider(X, Y), mouth_near(X, Y), bar(X, Y, EYE_R))
        img = over(img, ramp(t, pal['near']), near, px)

        # Triangular dither: gradients this shallow leave contour rings under
        # plain 8-bit rounding.  Flat palettes skip it and stay exact.
        if pal.get('dither', True):
            img += rng.triangular(-1.0, 0.0, 1.0, img.shape)
        out[y0:y1] = np.clip(img + 0.5, 0, 255).astype(np.uint8)
    return out


def write_png(path, rgb):
    h, w, _ = rgb.shape
    raw = np.concatenate(
        [np.zeros((h, 1), np.uint8), rgb.reshape(h, w * 3)], axis=1)
    body = zlib.compress(raw.tobytes(), 9)

    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)

    with open(path, 'wb') as fh:
        fh.write(b'\x89PNG\r\n\x1a\n')
        fh.write(chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)))
        fh.write(chunk(b'IDAT', body))
        fh.write(chunk(b'IEND', b''))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--palette', default='pro', choices=sorted(PALETTES))
    ap.add_argument('--size', default='5120x2880')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()
    w, h = (int(v) for v in args.size.lower().split('x'))
    out = args.out or 'Mac OS Background %s %dx%d.png' % (
        args.palette.replace('-', ' ').title(), w, h)
    write_png(out, render(w, h, PALETTES[args.palette]))
    print('wrote %s (%dx%d)' % (out, w, h))


if __name__ == '__main__':
    main()
