#!/bin/sh
set -e
SRCVIDEO='source_video/Sonic CD Intro [HD] [Lft02DuvqnQ].webm'
CLUT=sonic_cd_palette.png
SSDPCM="$HOME/develop/ssdpcm/build"

mkdir -p build

# make a low-resolution lossless intermediate
ffmpeg -y -i "$SRCVIDEO" \
  -r 12 -vf "crop=1248:702" -s 256x144 -c:v huffyuv -an build/source.avi
ffmpeg -y -i "$SRCVIDEO" \
  -vn -ar 13379 -af "volume=2" -ac 1 -c:a pcm_u8 build/source.wav
ffmpeg -y -i "$SRCVIDEO" \
  -vn -ar 26758 -af "volume=2" -ac 1 -c:a pcm_s16le build/source2x.wav

# make SSDPCM audio
"$SSDPCM/encoder" ss1.6 build/source.wav build/ss16.aud
"$SSDPCM/encoder" decode build/ss16.aud build/ss16.wav

# First make a 16-color palette, then apply it to the GIF
# https://superuser.com/a/556031/302629
# https://engineering.giphy.com/how-to-make-gifs-with-ffmpeg/
# https://superuser.com/a/1135202/302629
# I left off -y because you may want to hand-tweak this palette.
# This is what 16-color video can look like without the
# Color Cell Compression constraint.
ffmpeg -i build/source.avi -vf "palettegen=16" "$CLUT"
ffmpeg -y -i build/source.avi -i "$CLUT" \
  -filter_complex "[0:v][1:v] paletteuse=bayer:2" out-non-ccc.gif

# Color Cell Compression experiment
./ccc.py build/source.avi "$CLUT" build/cccout.ccc1
./cccdec.py build/cccout.ccc1 build/cccout.mp4
ffmpeg -y -i build/cccout.mp4 -i build/ss16.wav \
  -c:v copy -movflags +faststart preview.mp4
