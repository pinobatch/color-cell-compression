// Color Cell Compression decoder inner loop
// Copyright 2025 Damian Yerrick
// SPDX-License-Identifier: Zlib

// Untested decoder for the intended byte format of an all-intra
// frame.
// Was playing around in Compiler Explorer <https://godbolt.org>
// compiler: M68K gcc 15.1.0
// options: -Wall -Wextra -O2 -mcpu=68000
#include <stdint.h>
typedef struct {
  uint32_t color0, color1;
} ColorLUTEntry;
typedef struct {
  uint32_t top, bottom;
} CodebookEntry;
// color_lut is 4 to 32 bit expansion of nibble pairs
// {0x00000000, 0x00000000}, {0x00000000, 0x11111111}, ...,
// {0x00000000, 0xFFFFFFFF}, {0x11111111, 0x00000000}, ...
extern const ColorLUTEntry color_lut[256];
// full_block_masks is 1 to 4 bit expansion of bytes
// 0x00000000, 0x0000000F, 0x000000F0, 0x000000FF, 0x00000F00, ...
extern const uint32_t full_block_masks[256];
// codebook is the most common 16-bit patterns in non-solid blocks,
// looked up through full_block_masks
extern const CodebookEntry codebook[256];
typedef unsigned short CCC_size_t;

/**
 * @param src source blocks
 * @param dst a 4bpp buffer 4 pixels wide and tall, such as one that
 * would be copied to MD VRAM at a stride of 4 bytes
 * @return src destination blocks
 */ 
const uint8_t *CCC_decode_blocks(uint32_t *dst,
                                 const uint8_t *restrict src,
                                 CCC_size_t count) {
  for(; count > 0; --count) {
    ColorLUTEntry colors = color_lut[*src++];
    uint16_t color0lo = colors.color0 & 0xFFFF;
    uint16_t color1lo = colors.color1 & 0xFFFF;
    if (color0lo == color1lo) {
      // Solid color block
      *dst++ = colors.color0;  // top 4x2
      *dst++ = colors.color0;  // bottom 4x2
    } else if (color0lo < color1lo) {
      // Codebook block
      CodebookEntry mask = codebook[*src++];
      *dst++ = colors.color1 + (colors.color0 & mask.top);
      *dst++ = colors.color1 + (colors.color0 & mask.bottom);
    } else {
      // Full block, color0 > color1
      uint32_t mask = full_block_masks[*src++];
      *dst++ = colors.color0 + (colors.color1 & mask);
      mask = full_block_masks[*src++];
      *dst++ = colors.color0 + (colors.color1 & mask);
    }
  }
  return src;
}
