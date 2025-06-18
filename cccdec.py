#!/usr/bin/env python3
"""
Decompresses a Color Cell Compression video

Copyright 2025 Damian Yerrick
SPDX-License-Identifier: Zlib
"""
import os, sys, argparse, subprocess, struct
from PIL import Image

HEADER_SIZE = 52
CCC_SIZE = (4, 4)

def ccc_unpack_header(header):
    video_size = struct.unpack(">HH", header[0:4])
    palette = header[4:52]
    palim = Image.new("P", video_size)
    palim.putpalette(palette)
    return video_size, palim

def ccc_unpack_frame(frame):
    blk_colorpairs = []
    blk_shapes = []
    for i in range(0, len(frame), 3):
        blk_colorpairs.append((frame[i] >> 4, frame[i] & 0x0F))
        shape_bin = frame[i + 1] << 8 | frame[i + 2]
        blk_shapes.append(bytes([1 if (0x8000 >> i) & shape_bin else 0
                                 for i in range(16)]))
##        print("%04X %s" % (shape_bin, blk_shapes[-1].hex()))
    return blk_colorpairs, blk_shapes

def blockstoimdata(blocks, width, block_size):
    width_blocks = width // block_size[0]
    block_bytes = block_size[0] * block_size[1]
    scanlines = []
    for row_start in range(0, len(blocks), width_blocks):
        row = blocks[row_start:row_start + width_blocks]
        scanlines.extend(
            b''.join(b[i:i + block_size[0]] for b in row)
            for i in range(0, block_bytes, block_size[0])
        )
    return b''.join(scanlines)

def ccc_restore_frame(width, palim, blk_colorpairs, blk_shapes):
    decoded_blocks = []
    for colorpair, shape in zip(blk_colorpairs, blk_shapes):
        if len(colorpair) < 2: shape = bytes(16)
        decoded_blocks.append(bytes(colorpair[i] for i in shape))

    imdata = blockstoimdata(decoded_blocks, width, CCC_SIZE)
    out = Image.frombytes("P", (width, len(imdata) // width), imdata)
    out.putpalette(palim.getpalette())
    return out

trace_frame = None


def parse_argv(argv):
    p = argparse.ArgumentParser(
        description="Decodes video with Color Cell Compression"
    )
    p.add_argument("input", help="uncompressed CCC file")
    p.add_argument("output", help="output video file")
    p.add_argument("--trace-frame", type=int,
                   help="frame number to draw")
    return p.parse_args(argv[1:])

def main(argv=None):
    args = parse_argv(argv or sys.argv)
    with open(args.input, "rb") as infp:
        header = infp.read(HEADER_SIZE)
        video_size, palim = ccc_unpack_header(header)
        out_size = (video_size[0] * 2, video_size[1] * 2)
        dstcmd = """
ffmpeg -y -f rawvideo -pix_fmt rgb24 -r 12 -s %dx%d -an -i -
-crf 25 -pix_fmt yuv420p -movflags +faststart
""" % out_size
        dstcmd = dstcmd.split()
        dstcmd.append(args.output)
        width_in_cells = video_size[0] // CCC_SIZE[0]
        height_in_cells = video_size[1] // CCC_SIZE[1]
        frame_length_in_bytes = width_in_cells * height_in_cells * 3
        frame_count = 0
        dst = subprocess.Popen(dstcmd, stdin=subprocess.PIPE)
        while True:
            frame = infp.read(frame_length_in_bytes)
            if len(frame) < frame_length_in_bytes: break
            sec, subsec = divmod(frame_count, 12)
            if subsec == 0 and sec % 5 == 0:
                print("%d:%02d" % (sec // 60, sec % 60))
            blk_colorpairs, blk_shapes = ccc_unpack_frame(frame)
            out = ccc_restore_frame(video_size[0], palim,
                                    blk_colorpairs, blk_shapes)
            out = out.resize(out_size, Image.Resampling.NEAREST).convert("RGB")
            if frame_count == args.trace_frame: out.show()
            dst.stdin.write(out.tobytes())
            frame_count += 1
    result = dst.communicate()

if __name__=='__main__':
    if 'idlelib' in sys.modules:
        main("""
./cccdec.py build/cccout.ccc1 build/cccout.mp4
""".split())
    else:
        main()
