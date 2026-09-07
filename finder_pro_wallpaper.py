#!/usr/bin/env python3
"""
Finder face wallpaper, rebuilt with a "Pro" palette (black + chrome silver).

Same composition as "Mac OS Background 5120x2880.png": a hugely magnified
Finder face cropped off the right edge of the frame.  Every edge in that
artwork turned out to be either an exact circle or a straight line, so this
script does not trace pixels -- it evaluates the geometry as a signed distance
field.  That means genuinely clean, resolution independent, anti-aliased
edges (the original was rendered with anti-aliasing off).

Only numpy is required; the PNG is written directly with zlib.

    python3 finder_pro_wallpaper.py [--size WxH] [--out FILE]
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
# "Pro" palette: black stage, chrome features, glossy graphite panel.
# --------------------------------------------------------------------------
BG_BASE  = (0x00, 0x00, 0x00)
BG_GLOW  = (0x18, 0x19, 0x1e)      # soft pool of light behind the face
GLOW_C   = (3150.0, 1350.0)        # glow centre, reference coords
GLOW_R   = 3500.0

# Graphite panel = the right half of the face.  Top-lit, falling to black.
PANEL_STOPS = [
    (0.00, (0x3c, 0x3e, 0x44)),
    (0.28, (0x25, 0x27, 0x2c)),
    (0.62, (0x14, 0x15, 0x18)),
    (1.00, (0x08, 0x08, 0x0a)),
]

# Chrome = the features of the right (near) half of the face.
CHROME_STOPS = [
    (0.00, (0xff, 0xff, 0xff)),
    (0.12, (0xf1, 0xf3, 0xf6)),
    (0.32, (0xb4, 0xb8, 0xc0)),
    (0.47, (0x74, 0x78, 0x80)),
    (0.58, (0x63, 0x66, 0x6d)),
    (0.74, (0xa2, 0xa6, 0xad)),
    (0.89, (0xd8, 0xdb, 0xe1)),
    (1.00, (0xef, 0xf1, 0xf5)),
]

# Graphite = the features of the left (far) half of the face: same sweep,
# dimmed the way the original keeps the far half low contrast.
GHOST_STOPS = [
    (0.00, (0x50, 0x52, 0x58)),
    (0.35, (0x35, 0x37, 0x3c)),
    (0.60, (0x26, 0x27, 0x2b)),
    (1.00, (0x3a, 0x3c, 0x41)),
]

# Direction of the metal sweep: 60 degrees, down and to the right.
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


def background(X, Y):
    d = np.hypot(X - GLOW_C[0], Y - GLOW_C[1]) / GLOW_R
    k = np.clip(1.0 - d, 0.0, 1.0)
    k = k * k * k * (k * (k * 6.0 - 15.0) + 10.0)   # smootherstep falloff
    base = np.array(BG_BASE, dtype=np.float64)
    glow = np.array(BG_GLOW, dtype=np.float64)
    return base + (glow - base) * k[..., None]


def over(dst, colour, sd, px):
    """Composite `colour` where the field `sd` is inside, anti-aliased."""
    a = np.clip(sd / px + 0.5, 0.0, 1.0)[..., None]
    return dst * (1.0 - a) + colour * a


# --------------------------------------------------------------------------
def render(width, height, block=192):
    out = np.empty((height, width, 3), dtype=np.uint8)
    sx, sy = REF_W / width, REF_H / height
    px = max(sx, sy)                       # one output pixel, in ref units
    xs = (np.arange(width) + 0.5) * sx
    rng = np.random.RandomState(7)         # fixed, so renders are repeatable

    for y0 in range(0, height, block):
        y1 = min(y0 + block, height)
        ys = (np.arange(y0, y1) + 0.5) * sy
        X, Y = np.meshgrid(xs, ys)

        img = background(X, Y)
        img = over(img, ramp(Y / REF_H, PANEL_STOPS), face_panel(X, Y), px)

        t = sweep(X, Y)
        ghost = either(mouth_far(X, Y), bar(X, Y, EYE_L))
        img = over(img, ramp(t, GHOST_STOPS), ghost, px)

        chrome = either(divider(X, Y), mouth_near(X, Y), bar(X, Y, EYE_R))
        img = over(img, ramp(t, CHROME_STOPS), chrome, px)

        # Triangular dither: these gradients are shallow enough that plain
        # 8-bit rounding leaves contour rings.
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
    ap.add_argument('--size', default='5120x2880')
    ap.add_argument('--out', default='Mac OS Background Pro 5120x2880.png')
    args = ap.parse_args()
    w, h = (int(v) for v in args.size.lower().split('x'))
    write_png(args.out, render(w, h))
    print('wrote %s (%dx%d)' % (args.out, w, h))


if __name__ == '__main__':
    main()
