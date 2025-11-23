Color Cell 2025 plan
====================

This project will explore video encoding, using an animated cartoon
130 seconds in length as test data.

For comparison, Majesco's Game Boy Advance Video cartridges store up
to 48 minutes of video on a 32 MiB cartridge.  That averages about
11 kB/s for video and audio combined, which will be tough to match.

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
further, fitting a cartoon episode into 4 MiB.  It also plots a
graph of how often each shape is used.

### How Color Cell Compression works

CCC behaves as a simplified version of [Apple Video] (RPZA) and
[S3 Texture Compression] (S3TC).  For each frame in a shot, find a
pair of representative colors for each 4x4-pixel block of the frame.

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
   10782720 bytes to 7169945, saving 33.5%.  An encoder can encode
   this through the order of nibbles in a color pair.
2. Adding inter-frame coding reduces encoded blocks by 64.0% at the
   cost of 449280 bytes to store which blocks are stored and which
   are repeated from the previous frame.  This reduces the video to
   3262341 bytes, saving 70%.

It was discovered that in animation, the most common 4x4-pixel shapes
by far are the 15 that result from Bayer dithering of solid color
areas.  These accounted for about 2/3 of the cel-animated sample and
about 1/3 of the CGI sample.  The bias was much less pronounced in
live action.

Apart from the probability of flat or nearly-flat areas, the usage of
each pattern was found not to vary much with time within a video.
This means codebook replacement probably won't be needed.

### Things to try

1. Don't store consecutive duplicate blocks or color pairs within
   an encoded frame.
2. Noise reduction: If a block vacillates between two states that
   differ in one pixel, encode it as the simpler one.
3. Find some encoding that captures how much more likely the Bayer
   dithers are than other shapes.
4. Try calculating a preliminary codebook and rounding every block
   to its closest match.
5. Make a separate 16-color palette per shot, and don't use FFmpeg's
   automatic palette generator that generates boring palettes

### Playback budget

I chose the CCC approach to accommodate the comparatively weak CPU of
Mega Drive (also called Sega Genesis) and Game Boy Advance systems.

- MD runs the MC68000 CPU at 15 cycles per 7 chroma periods, or about
  7.67 MHz, or 228×262×15/7 = 128005 cycles per 59.92 Hz vblank, or
  277 cycles per 4×4-pixel block.  Memory reads have three wait
  states, giving a usable clock rate of 1.92 MHz.   Multiplication
  is slow.  Subtract some for PSRAM refresh and to copy the completed
  frame (18432 bytes) into VRAM.
- GBA runs the ARM7TDMI at 4 cycles per dot, or about 16.8 MHz, or
  308×228×4 = 280896 cycles per 59.73 Hz vblank, or 609 cycles per
  4×4-pixel block.  GBA has far fewer wait states: 1 to 2 for most
  parts of RAM, or 0 for the tightly-coupled IWRAM.  However, there's
  no second CPU for playing sound.

Audio
-----

I started with rates close to 13 kHz for two reasons:

1. GBA can use 13379 Hz.  This is 224 samples per frame,
   or one sample per 1254 CPU cycles (at 2^24 Hz).
2. MD can use 13317 Hz.  This is one sample per four cycles
   of the FM chip (at 1171875/22 = 53267 Hz), or one sample per
   268.8 Z80 cycles.

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

Perceptual noise substitution is a party trick that can be stapled
onto various audio codecs.  Instead of storing the actual content of
high frequencies, it stores only the amount of energy in the top half
of the frequency band and restores those frequencies as high-pass
filtered noise during playback, adding about 60 bytes per second.

### To try

1. Experiment with predictors more sophisticated than `y[n]=y[n-1]`

[Color Cell Compression]: https://en.wikipedia.org/wiki/Color_Cell_Compression
[Apple Video]: https://en.wikipedia.org/wiki/Apple_Video
[S3 Texture Compression]: https://en.wikipedia.org/wiki/S3_Texture_Compression
[SSDPCM]: https://github.com/Kagamiin/ssdpcm
