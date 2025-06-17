Color Cell 2025 plan
====================

This project will explore video encoding, using an animated cartoon
130 seconds in length as test data.

For comparison, Majesco's Game Boy Advance Video cartridges store up
to 48 minutes of video on a 32 MiB cartridge.  That averages about
11 kB/s, which will be tough to match.

Video
-----

Make a lossless intermediate:

    TLMIR_SRC=/path/to/original/video.mp4
    TLMIR_HY=tlmir-hy.avi
    ffmpeg -i "$TLMIR_SRC" -r 12 -s 256x144 -c:v huffyuv -an "$TLMIR_HY"

`shotbounds.py` is an attempt to find scene changes by subtracting
consecutive frames and calculating the magnitude of the difference.
It requires FFmpeg, Pillow, and matplotlib for displaying a graph of
subtraction results.

Make a 16-color reduction of the entire video:

    TLMIR_PAL=tlmir-palette.png
    ffmpeg -i "$TLMIR_HY" -vf "palettegen=16" "$TLMIR_PAL"
    ffmpeg -y -i "$TLMIR_HY" -i "$TLMIR_PAL" \
      -filter_complex "[0:v][1:v] paletteuse=bayer:3" tlmir.gif

`gifframediff.py` reads a 16-color GIF and counts how many 4x4-pixel
areas in each frame differ by more than 1 pixel from the previous
frame.  This gives a rough estimate of the achievable file size.

`ccc.py` transforms a video into its [Color Cell Compression]
representation, where the color pair and shape bits are not otherwise
compressed.  CCC works by drawing each 4×4 pixel area with 2 colors.
This happens to correspond to the "font color calculation" feature
at Mega CD ASIC addresses `$FF804C` through `$FF8056`.

`cccdec.py` decodes an uncompressed CCC stream into a video.

`cccestimate.py` estimates how the CCC stream could be compressed
further, fitting a cartoon episode into 4 MiB.

### How Color Cell Compression works

For each frame in a shot, find a pair of representative colors for
each 4x4-pixel block of the frame.

1. Add dither pattern to frame, such as Bayer or Z1.
2. Divide the dithered frame into blocks.
3. Divide each block into pixels lighter and darker than its mean.
4. For each block, calculate the mean of pixels lighter than the mean
   and the mean of pixels darker than the mean, and find the closest
   colors in the palette to each mean.  These are the initial
   color pair for each block.
5. Quantize the dithered image to 16 colors and divide it into
   blocks.
6. For each block where both initial colors are the same,
   find the two most common colors in that block of the quantized
   image, and use those as the color pair.

Then find the shape of that block, that is, which pixels use one
color and which use the other.

1. Gather blocks of the dithered image corresponding to each distinct
   color pair into an image.
3. Quantize the image for each color pair to those 2 colors, forming
   each block's shape.
4. Convert each such image back to blocks, giving shapes for that
   color pair.
5. Store the color pairs and shapes for later analysis.
6. Optionally for debugging, reconstruct an image from the CCC
   stream.

At 256 by 144 pixels and 12 frames per second, CCC produces 81 KiB/s
of raw color pairs and shapes.  This stream can be compressed
losslessly:

1. Not encoding solid shapes and encoding the most common shapes
   using 1 byte instead of 2 reduces a 1560-frame test video from
   10782720 bytes to 7169945, saving 33.5%.
2. Adding inter-frame coding reduces encoded blocks by 64.0% at the
   cost of 449280 bytes to store which blocks are stored and which
   are repeated from the previous frame.  This reduces the video to
   3262341 bytes, saving 70%.

Once the compression is figured out, it may prove worthwhile to try
making a separate 16-color palette per shot.

Audio
-----

I started with rates close to 13 kHz for two reasons:

1. Game Boy Advance can use 13379 Hz.  This is 224 samples per frame,
   or one sample per 1254 CPU cycles (at 2^24 Hz).
2. Mega Drive can use 13317 Hz.  This is one sample per four cycles
   of the FM chip (at 1171875/22 = 53267 Hz).

Kagamiin wrote a codec called [SSDPCM] that represents each sample
as a difference from the previous sample quantized to 2, 3, 4, or 6
levels, packed into 8, 5, 4, or 3 samples per byte.  I chose the
3-level mode, called "SSDPCM 1.6" for 1.6 bits per sample.  Each
sample can add a slope value to the previous sample, subtract the
slope, or duplicate the previous sample without change.  Each 65
samples are stored as 14-byte block consisting of a slope followed
by 13 bytes with 5 samples each.  This gives a data rate of
13379×14/65 = 2882 bytes per second, or 374612 bytes for a 2:10
video's audio track.

### To try

1. Experiment with decomposition of upper frequencies into a
   perceptual noise substitution channel
2. Experiment with predictors more sophisticated than `y[n]=y[n-1]`

[Color Cell Compression]: https://en.wikipedia.org/wiki/Color_Cell_Compression
[SSDPCM]: https://github.com/Kagamiin/ssdpcm
