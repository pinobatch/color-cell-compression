#!/usr/bin/env python3
"""
Read unchanged areas from GIF, as an experimental approximation of
what gains could be had from interframe coding in Color Cell Compression

Copyright 2025 Damian Yerrick
SPDX-License-Identifier: Zlib
"""
import os, sys, argparse
from PIL import Image, ImageChops
try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

def main():
    filename = "out-non-ccc.gif"
    frames_per_row = 24
    COLOR_CELL_W = 4
    COLOR_CELL_H = 4
    last_frame = None
    unchanged = []
    with Image.open(filename) as im:
        print("frame count:", im.n_frames)
        print("size:", im.size)
        size_cells = (im.size[0] // COLOR_CELL_W,  im.size[1] // COLOR_CELL_H)
        num_rows = -(-im.n_frames // frames_per_row)
        diff_contact = Image.new(
            "L", (size_cells[0] * frames_per_row, size_cells[1] * num_rows)
        )
        n_frames = im.n_frames
        for i in range(im.n_frames):
            im.seek(i)
            frame = im.convert("RGB")
            diff = ImageChops.difference(frame, last_frame or frame)
            diff = diff.convert("L").point(lambda x: 255 if x > 0 else 0)
            diff = diff.resize(size_cells, Image.Resampling.BOX)
            diff = diff.point(lambda x: 255 if x > 0x18 else 0)
            last_frame = frame
            paste_y, paste_x = divmod(i, frames_per_row)
            diff_contact.paste(diff,
                               (paste_x * size_cells[0],
                                paste_y * size_cells[1]))
            unchanged.append(diff.histogram()[0])

    print("image size: %d cells (%d by %d)"
          % (size_cells[0] * size_cells[1], *size_cells))
    print("\n".join(
        "%5d:%s" % (i, "".join("%5d" % x for x in unchanged[i:i + 12]))
        for i in range(0, len(unchanged), 12)
    ))
    total_cells = size_cells[0] * size_cells[1] * n_frames
    total_unchanged = sum(unchanged)
    print("in %d frames, %d of %d color cells (%.1f%%) are unchanged"
          % (n_frames, total_unchanged, total_cells,
             total_unchanged * 100.0 / total_cells))
    print("estimated video size at 1 bit per cell and 24 bits per changed cell:")
    bits = total_cells + 24 * (total_cells - total_unchanged)
    print("%d bytes, or %d bytes/frame" % (bits // 8, bits // (8 * n_frames)))


    diff_contact.save("gif_diff_contact.png")
    if plt:
        plt.plot(range(len(unchanged)),
                 [size_cells[0] * size_cells[1] - u for u in unchanged])

if __name__=='__main__':
    main()
