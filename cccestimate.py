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
    for i in range(0, len(frame), 3):
        color = frame[i]
        shape = frame[i + 1] << 8 | frame[i + 2]
        all_shapes[shape] += 1
    return all_shapes

def try_inter(frame, prev_frame):
    this_blocks = [frame[i:i + 3] for i in range(0, len(frame), 3)]
    prev_blocks = [prev_frame[i:i + 3] for i in range(0, len(prev_frame), 3)]
    found = [t for t, p in zip_longest(this_blocks, prev_blocks) if t != p]
    return b"".join(found)

def main():
    args_input = "cccout.ccc1"
    use_interframe = True
    
    with open(args_input, "rb") as infp:
        header = infp.read(cccdec.HEADER_SIZE)
        video_size, palim = cccdec.ccc_unpack_header(header)
        small_size = (video_size[0] // cccdec.CCC_SIZE[0],
                      video_size[1] // cccdec.CCC_SIZE[1])
        frame_bytes = small_size[0] * small_size[1] * 3
        print(small_size, frame_bytes)
        frame_count = 0
        all_shapes = Counter()
        prev_frame = bytes(frame_bytes)
        total_inter_bytes = 0
        while True:
            frame = infp.read(frame_bytes)
            if len(frame) < frame_bytes: break
            if use_interframe:
                inter_result = try_inter(frame, prev_frame)
            else:
                inter_result = frame
            total_inter_bytes += len(inter_result)
            all_shapes += try_intra(inter_result)
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
    main()
