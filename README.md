Color Cell Compression experiment
=================================

A proof of concept video encoder using [Color Cell Compression].

What is CCC?
------------

Color Cell Compression (CCC) is a lossy image codec that represents
each 4×4-pixel block of an image with two colors, selecting one of
the two for each pixel.  (The grayscale case of CCC is called Block
Truncation Coding.)

The application-specific integrated circuit (ASIC) in the Mega CD
(called Sega CD in North America) contains a CCC decompressor at
addresses `$FF804C` through `$FF8056`.  Write a color pair and a
shape and read a quarter tile.  It's suspected (but not proven) that
the main CPU of the Mega Drive (called Genesis in North America) can
decompress CCC on its own, allowing short full-motion video (FMV)
sequences in cartridge games.

CCC's successors [Apple Video] (RPZA) and [S3 Texture Compression]
(S3TC) allow mixing the two colors in various proportions and using
more colors in a scene at the cost of a higher bitrate.  When S3TC
was still under patent, open-source implementations of OpenGL used
[Super Simple Texture Compression] (S2TC), a form of CCC using S3TC's
bitstream format.

CCC for video
-------------

This implementation of CCC allocates 16 colors for an entire image.
Each block consists of three bytes: two 4-bit color indices and one
16-bit shape.  The tools that interact with video (`ccc.py` and
`cccdec.py`) use uncompressed CCC, which always represents the shape
in full.  A tool to estimate the size of a compressed CCC stream
(`cccestimate.py`) is also included.  It assumes the following:

- Use a bitmap to determine which blocks have and haven't changed
  since the previous frame.
- Store a solid color block's shape as 0 bytes with both colors in
  the pair the same, the 256 most common shapes as 1 byte with the
  color pair in reverse order, and remaining shapes as 2 bytes.

Other tools
-----------

These were built during early research before design of the encoder:

- `shotbounds.py` attempts to find shot changes in a video by
  calculating the absolute difference between successive frames.
  This could be used to trigger loading a new 16-color palette.
- `gifframediff.py` uses a GIF encoder as an approximation of the
  CCC encoder, counting how many 4×4-pixel blocks change between
  successive frames.

[Color Cell Compression]: https://en.wikipedia.org/wiki/Color_Cell_Compression
[Apple Video]: https://en.wikipedia.org/wiki/Apple_Video
[S3 Texture Compression]: https://en.wikipedia.org/wiki/S3_Texture_Compression
[Super Simple Texture Compression]: https://en.wikipedia.org/wiki/S2TC
