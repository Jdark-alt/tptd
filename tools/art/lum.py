"""Mean luminance of a region of two screenshots (v32 brightness check). Usage: lum.py before.png after.png [x0 y0 x1 y1]
(fractions of the image, default the desktop board) prints mean relative luminance (0-255 sRGB-weighted) and the ratio."""
import sys
from PIL import Image
import numpy as np
def lum(path, box):
    im = np.asarray(Image.open(path).convert('RGB')).astype(float)
    h, w, _ = im.shape; x0, y0, x1, y1 = box
    r = im[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]
    L = 0.2126 * r[..., 0] + 0.7152 * r[..., 1] + 0.0722 * r[..., 2]
    return L.mean(), np.percentile(L, 50), np.percentile(L, 99)
box = tuple(map(float, sys.argv[3:7])) if len(sys.argv) > 3 else (0.045, 0.18, 0.695, 0.89)
a, b = lum(sys.argv[1], box), lum(sys.argv[2], box)
print(f'mean {a[0]:.2f} -> {b[0]:.2f} ({100 * (b[0] / a[0] - 1):+.1f}%), median {a[1]:.1f} -> {b[1]:.1f}, p99 {a[2]:.0f} -> {b[2]:.0f}')
