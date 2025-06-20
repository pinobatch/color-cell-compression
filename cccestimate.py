#!/usr/bin/env python3
"""
Estimate usable compression for a Color Cell Compression video.

Unpacked CCC video is 1.5 bits per pixel.  At 256x144 and 12 fps,
this equals 6912 bytes per frame or 81 KiB/s.  Good for CD, not so
good for cartridge.  Look for intra- and inter-frame compression
opportunities.

Copyright 2025 Damian Yerrick
SPDX-License-Identifier: Zlib
"""
import os, sys, argparse
from collections import Counter
from itertools import zip_longest
from time import sleep
import cccdec

def try_intra(frame):
    all_shapes = Counter()
    last_color = last_shape = None
    color_only_matches = full_matches = 0
    for i in range(0, len(frame), 3):
        color = frame[i]
        shape = frame[i + 1] << 8 | frame[i + 2]
        all_shapes[shape] += 1
        if color == last_color:
            if shape == last_shape:
                full_matches += 1
            else:
                color_only_matches += 1
        last_color, last_shape = color, shape
    return all_shapes, full_matches, color_only_matches

def try_inter(frame, prev_frame):
    this_blocks = [frame[i:i + 3] for i in range(0, len(frame), 3)]
    prev_blocks = [prev_frame[i:i + 3] for i in range(0, len(prev_frame), 3)]
    found = [t for t, p in zip_longest(this_blocks, prev_blocks) if t != p]
    return b"".join(found)

def parse_argv(argv):
    p = argparse.ArgumentParser(
        description="Estimates how big the compressed CCC file would be"
    )
    p.add_argument("input", help="video file produced by ccc.py")
    p.add_argument("--inter", action="store_true",
                   help="skip blocks matching a block in the previous frame")
    return p.parse_args(argv[1:])

def main(argv=None):
    args = parse_argv(argv or sys.argv)
    use_interframe = args.inter
    
    with open(args.input, "rb") as infp:
        header = infp.read(cccdec.HEADER_SIZE)
        video_size, palim = cccdec.ccc_unpack_header(header)
        small_size = (video_size[0] // cccdec.CCC_SIZE[0],
                      video_size[1] // cccdec.CCC_SIZE[1])
        frame_bytes = small_size[0] * small_size[1] * 3
        print("%s: %dx%d pixels, %dx%d blocks, %d bytes/frame"
              % (args.input, *video_size, *small_size, frame_bytes))
        frame_count = 0
        all_shapes = Counter()
        prev_frame = bytes(frame_bytes)
        total_inter_bytes = 0
        intra_color_matches = intra_full_matches = 0
        while True:
            frame = infp.read(frame_bytes)
            if len(frame) < frame_bytes: break
            if use_interframe:
                inter_result = try_inter(frame, prev_frame)
            else:
                inter_result = frame
            total_inter_bytes += len(inter_result)
            intra_result = try_intra(inter_result)
            all_shapes += intra_result[0]
            intra_full_matches += intra_result[1]
            intra_color_matches += intra_result[2]
            frame_count += 1
            prev_frame = frame
    num_blocks = small_size[0] * small_size[1] * frame_count
    before_bytes = 3 * num_blocks
    inter_blocks = total_inter_bytes // 3
    common = [row for row in all_shapes.most_common(257) if row[0]]
    del common[256:]
    total_common = sum(row[1] for row in common)
    total_full = inter_blocks - all_shapes[0] - total_common
    if use_interframe:
        inter_map_size = frame_count * frame_bytes // 24
        print("with interframe coding")
    else:
        inter_map_size = 0
        print("intra coding only!")
    print("block bitmap")
    print("of %d blocks:\n"
          "  %d inter elided, %d full match, %d color match, %d none"
          % (num_blocks, (num_blocks - inter_blocks),
             intra_full_matches, intra_color_matches,
             inter_blocks - intra_full_matches - intra_color_matches))
    print("of %d blocks to be coded, %d are full matches, %d color matches"
          % (inter_blocks, intra_full_matches, intra_color_matches))


    print("before (%4d frames):  %8d bytes" % (frame_count, before_bytes))
    print("inter: %7d (%4.1f%%),%8d bytes"
          % ((num_blocks - inter_blocks),
             (num_blocks - inter_blocks) * 100 / num_blocks,
             inter_map_size))
    print("solid: %7d (%4.1f%%),%8d bytes"
          % (all_shapes[0], 100 * all_shapes[0] / num_blocks, all_shapes[0]))
    print("common:%7d (%4.1f%%),%8d bytes"
          % (total_common, 100 * total_common / num_blocks, 2 * total_common))
    print("common shape dictionary:    512 bytes")
    print("full:  %7d (%4.1f%%),%8d bytes"
          % (total_full, 100 * total_full / num_blocks, 3 * total_full))
    total_bytes = (
        all_shapes[0] + 2 * total_common + 3 * total_full + 512
        + inter_map_size
    )
    print("total: %7d (100.%%),%8d bytes" % (num_blocks, total_bytes))
    print("saved %.1f%%" % ((before_bytes - total_bytes) * 100 / before_bytes))

    print("""
Assumed coding scheme

- Before each frame is a bitfield with one bit per 4x4-pixel block.
- For each set bit, a block is stored, starting with a 1-byte pair
  of color values.
- If the nibbles of the color value are the same, the shape is solid
  and not stored.
- If the low nibble is less than the high nibble, an index into the
  256 most common shapes is stored.
- If the high nibble is less than the low nibble, the whole 16-bit
  shape is stored.
""")

if __name__=='__main__':
    if 'idlelib' in sys.modules:
        main("""
./cccestimate.py --inter build/cccout.ccc1
""".split())
    else:
        main()
