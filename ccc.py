#!/usr/bin/env python3
"""
Converts a video to an uncompressed Color Cell Compression
representation for later compression experiments.

Copyright 2025 Damian Yerrick
SPDX-License-Identifier: Zlib
"""
import os, sys, argparse, subprocess, struct
from collections import Counter
from operator import or_ as bitor
from functools import reduce
from PIL import Image, ImageChops

bayer_src = bytes(int(x, 16) for x in "0C3F84B72E1DA695")
def make_bayer_img(size, scale=1, offset=128):
    width, height = size
    PATWIDTH = PATHEIGHT = 4
    src = bytes((c - 8) * scale + offset for c in bayer_src)
    assert len(src) == PATWIDTH * PATHEIGHT
    rows = [src[i:i + PATWIDTH]
            for i in range(0, len(src), PATWIDTH)]
    rows = [(row * -(-width // PATWIDTH))[:width] for row in rows]
    assert all(len(row) == width for row in rows)
    rows = (rows * -(-height // PATHEIGHT))[:height]
    return Image.frombytes("L", size, b"".join(rows))

def ffprobe_size(filename):
    args = ["ffprobe", "-show_streams", filename]
    result = subprocess.run(args, capture_output=True, encoding="utf-8")
    if result.returncode:
        sys.stderr.write(result.stderr)
        result.check_returncode()
    nvps = [line.strip().split("=", 1) for line in result.stdout.split('\n')]
    width = height = None
    for line in nvps:
        if len(line) < 2: continue
        if line[0] == "width": width = int(line[1])
        if line[0] == "height": height = int(line[1])
        if width is not None and height is not None: return width, height
    raise ValueError("ffprobe returned no width and height")

def get_frames(filename, size):
    args = [
        "ffmpeg", "-i", filename,
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"
    ]
    proc = subprocess.Popen(args, stdout=subprocess.PIPE)
    while True:
        im = proc.stdout.read(size[0] * size[1] * 3)
        if not im: break
        yield im

def PIL_get_frames(filename, size):
    for rawim in get_frames(filename, size):
        yield Image.frombytes("RGB", size, rawim)

def get_palim(filename):
    with Image.open(filename) as im:
        colors = im.getcolors()
    colors = [bytes(x[1][:3]) for x in colors]
    colors.sort(key=lambda x: x[0] * 3 + x[1] * 6 + x[2])
    colors.extend(colors[-1:] * (256 - len(colors)))
    im = Image.new("P", (4, 4))
    im.putpalette(b"".join(colors))
    return im

def imtoblocks(im, block_size):
    """Segment an image into tiles for analysis.

Return a list of bytes instances containing data from blocks in
row-major order.
"""
    block_width_px, block_height_px = block_size
    num_bands = len(im.getbands())
    block_width_bytes = block_width_px * num_bands
    scanline_bytes = im.size[0] * num_bands
    row_bytes = scanline_bytes * block_height_px
    imdata = im.tobytes()
    return [
        b"".join(
            imdata[left:left + block_width_bytes]
            for left in range(topleft, topleft + row_bytes, scanline_bytes)
        )
        for top in range(0, len(imdata), row_bytes)
        for topleft in range(top, top + scanline_bytes, block_width_bytes)
    ]

def uniq_to_indices(seq):
    out = {}
    for i, el in enumerate(seq):
        if el not in out: out[el] = []
        out[el].append(i)
    return out

CCC_SIZE = (4, 4)
def ccc_quantize_frame(im, bayer, palim, trace=False, use_population=False):

    # Find which 2 colors in the palette best represent each block.
    dithered = ImageChops.add(im, bayer, offset=-128)
    small_size = (im.size[0] // CCC_SIZE[0], im.size[1] // CCC_SIZE[1])

    # One approach is to find which color best represents colors
    # with luma greater and less than the block's mean.
    dithered_bw = dithered.convert("L")
    avg_luma = dithered_bw.resize(small_size, Image.Resampling.BOX)
    avg_luma = avg_luma.resize(im.size, Image.Resampling.NEAREST)
    grainmask = ImageChops.subtract(dithered_bw, avg_luma, offset=128)
    hipixels = dithered.convert("RGBA")
    hipixels.putalpha(grainmask.point(lambda x: 255 if x >= 128 else 0))
    hipixels_sm = hipixels.resize(small_size, Image.Resampling.BOX)
    hipixels_sm.putalpha(255)
    hibest = hipixels_sm.convert("RGB").quantize(palette=palim, dither=Image.Dither.NONE)
    lopixels = dithered.convert("RGBA")
    lopixels.putalpha(grainmask.point(lambda x: 0 if x >= 128 else 255))
    lopixels_sm = lopixels.resize(small_size, Image.Resampling.BOX)
    lopixels_sm.putalpha(255)
    lobest = lopixels_sm.convert("RGB").quantize(palette=palim, dither=Image.Dither.NONE)
    if trace:
        hibest.resize(im.size, Image.Resampling.NEAREST).show()
        lobest.resize(im.size, Image.Resampling.NEAREST).show()
    luma_colorpairs = list(zip(lobest.tobytes(), hibest.tobytes()))

    # Another approach is to take the two colors with greatest
    # population in each block.  Use this if the luma over/under
    # method returns the same color twice.
    quantized = dithered.quantize(palette=palim, dither=Image.Dither.NONE)
    quantized_blks = imtoblocks(quantized, CCC_SIZE)
    pop_colorpairs = [
        tuple(sorted(c for c, freq in Counter(blk).most_common(2)))
        for blk in quantized_blks
    ]
    blk_colorpairs = [
        lcp if lcp[0] != lcp[1] else pcp
        for lcp, pcp in zip(luma_colorpairs, pop_colorpairs)
    ]

    # Make an image from the blocks that use each color pair, and
    # quantize it to only those two colors to find the shapes of
    # blocks using that pair
    palette_size = 16
    palette_colors = bytes(palim.getpalette())
    palette_colors = [palette_colors[i:i + 3]
                      for i in range(0, palette_size * 3, 3)]
    dithered_blks = imtoblocks(dithered, CCC_SIZE)
    palim_this_pair = Image.new("P", CCC_SIZE)
    blk_shapes = [None] * len(blk_colorpairs)
    colorpair_indices = uniq_to_indices(blk_colorpairs)
    for colorpair, indices in colorpair_indices.items():
        if len(colorpair) < 2: continue
        imdata = b''.join(dithered_blks[i] for i in indices)
        dithered_this_pair = Image.frombytes(
            dithered.mode, (CCC_SIZE[0], CCC_SIZE[1] * len(indices)),
            imdata
        )
        paldata = b"".join(palette_colors[i] for i in colorpair)
        palim_this_pair.putpalette(paldata)
        shapes_this_pair = dithered_this_pair.quantize(
            palette=palim_this_pair, dither=Image.Dither.NONE
        )
        assert max(shapes_this_pair.tobytes()) < 2
        shapes_this_pair = imtoblocks(shapes_this_pair, CCC_SIZE)
        for i, shape in zip(indices, shapes_this_pair):
            blk_shapes[i] = shape
    return blk_colorpairs, blk_shapes

def ccc_form_header(video_size, palim):
    """

this version of a CCC file begins as follows
width in pixels (2 bytes)
height in pixels (2 bytes)
palette (48 bytes)
frames
"""
    out = [
        struct.pack(">HH", *video_size),
        bytes(palim.getpalette()[:48])
    ]
    return b''.join(out)

def ccc_form_frame(blk_colorpairs, blk_shapes):
    out = bytearray()
    for colorpair, shape in zip(blk_colorpairs, blk_shapes):
        shape = (reduce(bitor,
                        (0x8000 >> i for i, c in enumerate(shape) if c),
                        0)
                 if shape
                 else 0)
        if shape == 0xFFFF:
            colorpair, shape = colorpair[1:], 0
        if len(colorpair) < 2 or shape == 0:
            out.append(colorpair[0] * 0x11)
            out.append(0)
            out.append(0)
            continue
        out.append(colorpair[0] << 4 | colorpair[1])
        out.append(shape >> 8)
        out.append(shape & 0xFF)
    return bytes(out)

def parse_argv(argv):
    p = argparse.ArgumentParser(
        description="Encodes video with Color Cell Compression"
    )
    p.add_argument("input", help="video file readable by FFmpeg")
    p.add_argument("palette", help="image containing 16 colors to use")
    p.add_argument("output", help="write uncompressed CCC file")
    p.add_argument("--trace-frame", type=int,
                   help="frame number to draw")
    return p.parse_args(argv[1:])

def main(argv=None):
    args = parse_argv(argv or sys.argv)
    if args.trace_frame is not None:
        import cccdec
    video_size = ffprobe_size(args.input)
    bayer = make_bayer_img(video_size, 2, 129).convert("RGB")
    palim = get_palim(args.palette)
    src = PIL_get_frames(args.input, video_size)

    with open(args.output, "wb") as outfp:
        outfp.write(ccc_form_header(video_size, palim))
        for i, im in enumerate(src):
            trace = i == args.trace_frame
            sec, subsec = divmod(i, 12)
            if subsec == 0 and sec % 5 == 0:
                print("%d:%02d" % (sec // 60, sec % 60))
            result = ccc_quantize_frame(im, bayer, palim, trace=trace)
            outfp.write(ccc_form_frame(*result))
            if trace:
                cccdec.ccc_restore_frame(video_size[0], palim, *result).show()
                break

if __name__=='__main__':
    if 'idlelib' in sys.modules:
        main("""
./ccc.py build/source.avi tlmir-palette.png build/cccout.ccc1
""".split())
    else:
        main()
