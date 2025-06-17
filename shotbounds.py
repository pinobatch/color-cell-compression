#!/usr/bin/env python3
"""
Attempt to detect shot bounds, such as for palette changes

Copyright 2025 Damian Yerrick
SPDX-License-Identifier: Zlib
"""
import os, sys, argparse, subprocess
from PIL import Image, ImageChops, ImageStat, ImageFont, ImageDraw, ImageFilter
import matplotlib.pyplot as plt

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

def main():
    it = PIL_get_frames("build/source.avi", (256, 144))
    prevframe = None
    pcts = [0.0]
    SHOT_THRESHOLD = 80
    dilation = ImageFilter.BoxBlur(3)
    keyframes = []
    for i, frame in enumerate(it):
    ##    if i == 24: frame.show()
        if prevframe is not None:
            diff = ImageChops.difference(frame, prevframe)
            diff = diff.convert("L", matrix=(.25, .5, .25, 0))
            diff = diff.filter(dilation)
            diff = diff.point(lambda x: min(255, x*17))
            if i == 24: diff.show()

            diff_divisor = diff.size[0] * diff.size[1] * 255
            diffstat = ImageStat.Stat(diff)
            reldiff = diffstat.sum[0] * 100 / diff_divisor
            pcts.append(reldiff)
            if reldiff > SHOT_THRESHOLD:
                keyframes.append((i, reldiff, diff))
        prevframe = frame

    for i in range(0, len(pcts), 10):
        diffs_fmt = "".join("%5.1f" % x for x in pcts[i:i + 10])
        print("%05d:%s" % (i, diffs_fmt))

    if keyframes:
        print(len(keyframes), "autodetected keyframes")
        kf_per_row = 5
        kf_rows = -(-len(keyframes) // kf_per_row)
        kf_size = keyframes[0][-1].size
        kf_contact = Image.new("RGB",
                               (kf_size[0] * kf_per_row, kf_size[1] * kf_rows))
        font = ImageFont.load_default()
        for kfindex, (i, reldiff, frame) in enumerate(keyframes):
            annotated = frame.convert("RGB")
            dc = ImageDraw.Draw(annotated)
            text = "%d: %.1f" % (i, reldiff)
            dc.multiline_text((1, 1), text, font=font, fill=(0, 0, 0))
            dc.multiline_text((0, 0), text, font=font, fill=(255, 255, 255))
            dc = None
            paste_y, paste_x = divmod(kfindex, kf_per_row)
            kf_contact.paste(annotated,
                             (paste_x * kf_size[0], paste_y * kf_size[1]))
        kf_contact.save("shotbounds.jpg")

    plt.plot(range(len(pcts)), pcts)
    plt.show()
