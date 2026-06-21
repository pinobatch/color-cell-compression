
The playback task
-----------------

1. Fetching a compressed audio data stream from ROM, which cannot be
   done while the VDP is pulling tile data from 68000 work RAM
2. Decoding compressed audio
3. Adding perceptual noise substitution (PNS) (optional)
4. Writing samples to the YM2612 at an even pace

YM2612 operation
----------------

YM2612, the FM synthesizer in the Genesis, performs one pass through
all 6 voices every 144 68K cycles, or 53267 Hz.  A basic SSDPCM
player pushes one sample every 4 loops, or 576 68K cycles, or 268.8
Z80 cycles, or 13317 Hz.  If using perceptual noise shaping, we have
to write at twice this speed: once every 134.4 cycles.

A status register readable at $4000-$4003 has bit 7 true if busy
committing a write to an FM voice (which takes 36+ cycles), bit 1
true if timer A has finished, and bit 0 true if timer B has finished.

To write to a register, write its address to $4000 and its data to
$4001.  (Exception: FM voice 4-6 parameters are at $4002/$4003.)

To mute voice 6 and replace it with the DAC, write $80 to register
$2B.  Then to change the DAC value, write to register $2A.

YM2612 timer A counts up once per pass.  When it reaches $400, it
is reset to the 10-bit value in registers $25 (high) and $24 (low),
and bit 1 of the readable status register ($4000-$4003) becomes 1.
Write $1F then $0F to register $27 (or $5F then $4F if splitting
voice 3) to acknowledge the overflow and clear bit 1 to 0.

    ld hl, $4000
    bit 1, [hl]
    jr z, not_ready_for_next_sample

Decoding SSDPCM
---------------

Each SSDPCM packet consists of one byte encoding the slope followed
by several bytes each encoding 5 differences, each of which can be
positive slope (0), negative slope (1), or unchanged (2).  The five
differences are packed into as a big-endian base 3, where values 0-80
encode positive slope for the first sample, values 81-161 negative,
and values 162-242 unchanged.

### A sample at a time

The naive method decodes a sequence of 5 samples one at a time:

```
decode_ss16_byte:
  ld b, 5
  ; B: number of samples left in byte
  ; C: slope
  ; D: encoded byte
  ; E: sample value
  ; HL: pointer into decode buffer
  sampleloop:
    ld a, d  ; group: 18
    sub 81
    jr c, is_plus
    ld d, a  ; group: 18
    sub 81
    jr c, is_minus
      ; zero!  entry: 18+18; group: 12
      ld d, a
      jr rewrite_sample
    is_plus:  ; entry: 18+5; group max: 31
      ld a, e
      add c
      jr nc, write_sample
      sbc a  ; ld a, 255
      jr write_sample
    is_minus:  ; entry: 18+18+5; group max: 19
      ld a, e
      sub c
      jr nc, write_sample
      xor a  ; ld a, 0
    write_sample:  ; entry max: 60; group: 36
      ld e, a
    rewrite_sample:
    ld [hl], e
    inc hl
    ld a, d
    add d
    add d
    ld d, a
    djnz sampleloop
  ; that's up to 96 tstates per cycle
```

### With macros

Another method uses lookup tables to unroll decoding two or three
samples at once.  Decoding each byte is broken down into 2 phases
totaling about 326 cycles:

1. Nine routines to decode the first two samples, beginning at codes
   0, 27, ..., 216, or a failsafe for invalid codes 243-255
2. 27 routines to decode the last 3 samples, beginning with 27 to
   decode the third jumping into 9 to decode the fourth and fifth

```
; spl_* macros are 4 bytes and usually 16 cycles

macro spl_up
  add c
  jr nc, :+
    sbc a
  :
endm

macro spl_down
  sub c
  jr nc, :+
    xor a
  :
endm

macro spl_repeat
  nop
  nop
  nop
  nop
endm

;;
; @param C slope
; @param DE previous output sample in 256-byte circular buffer
; @param IX source sample pointer
top_dispatch:  ; 57 cycles
  ld l, [ix+0]  ; L: five deltas
  ld h, high(top_routines_table)
  ld l, [hl]  ; L: offset from start of top routines
  ld h, high(top_routines)  ; HL: routine start
  ld a, [de]  ; reload previous decoded sample
  inc de
  jp hl

top routines (count: 9) are 14 bytes, 56 cycles
  spl_*
  ld [de], a
  spl_*
  ld b, subt_value
  jp mid_dispatch

;;
; @param A second sample value to write to ++DE
; @param B value of already-handled samples to subtract
mid_dispatch:  ; 86 cycles
  inc de
  ld [de], a

  ; TODO: try pushing out a sample

  ld a, [ix+0]  ; all 5 deltas
  sub b         ; A = bottom 3 deltas, 0-27
  inc ix        ; 46 so far

  add a
  add a
  add a  ; A = low(start of middle routine)
  ld h, high(mid_routines)  ; HL: routine start
  ld l, a
  ld a, [de]  ; reload previous decoded sample
  inc de
  jp hl

middle routines (count: 27) are 8 bytes, 33 cycles
  spl_* :: ld [de], a :: jp bottom_x

bottom routines (count: 9) are 21 bytes, 55 cycles
  spl_*
  inc de
  ld [de], a
  spl_*
  jp sample_end

sample_end:  ; 39 cycles
  inc de
  ld [de], a

  ; TODO: is a sample ready to be pushed out?

  ld hl, wInputLen
  dec [hl]
  ret z
  fallthrough top_dispatch
```

Fetching samples from ROM
-------------------------

The SSDPCM stream typically uses 1 byte representing a slope followed
by 13 bytes representing 65 samples.  There are 228×262 bytes in one
VDP frame, which correspond to 222.23 samples or up to 3.42 packets.
During a part of the frame when the VDP is not busy, the Z80 will
need to switch ROM banks and fetch up to 56 bytes of SSDPCM codes
while playing already decoded samples, then decode those samples to a
circular buffer while playing samples from the other end.

- `bit 1, [hl]` is 12 cycles
- `ldi` is 16 cycles


Perceptual noise substitution
-----------------------------

Perceptual noise substitution (PNS) provides a perception of wideband
audio with a small increase in data rate.  It encodes the bottom half
of the audio frequency spectrum normally and stores only the RMS
amplitude of the top half.  For example, 26.6 kHz SSDPCM+PNS encodes
0-6.1 kHz with 13.3 kHz SDPCM and the amplitude of 6.1-13.3 kHz, to
be reconstructed as band-pass filtered white noise during playback.

It's an open question whether a Z80 can process all four of sample
fetching, SSDPCM decoding, PNS processing, and maintaining a steady
write cadence around 134 samples.

Synchronizing to the sample clock costs 81 cycles.  Ouch.  That alone
might make PNS impractical without assistance from the PSG.
```
macro sync_and_ack_vdp  ; 81 cycles by itself!
  ld hl, $4000
  syncloop:
    bit 1, [hl]
    jr z, syncloop
  ld [hl], $27  ; timer acknowledge
  inc l
  ld [hl], $1F
  ld [hl], $0F
  dec l
  ld [hl], $2A  ; dac level
  inc l


;;
; @param B shift register for noise generation
; @param C PNS level
; @param HL circular buffer

pns_push_interpolated_sample:
  sync_and_ack_vdp
  exx
  sla b
  jr nc, no_xor
    ; carry: update CRC, flip PNS sign, don't subtract
    ld a, crc8_constant
    xor b
    ld b, a
    xor a
    sub c
    ld c, a
    ld a, [hl]
    inc l
    add [hl]
    rra
    exx
    ld [hl], a
    ret
  no_xor:
    ; no carry: no update CRC, no update PNS sign, subtract
    ld a, [hl]
    inc l
    add [hl]
    rra
    sub c
    rra
    exx
    ld [hl], a
    ret

pns_push_normal_sample:
  sync_and_ack_vdp
  exx
  ld a, [hl]
  add c
  exx
  ld [hl], a
  ret
```
