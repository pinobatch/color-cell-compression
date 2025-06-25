#!/usr/bin/env python3
"""
perceptual noise substitution, first test

"""
import os, sys, argparse, wave, array
from math import floor

try:
    import numpy as np
except ImportError:
    using_numpy = False
else:
    using_numpy = True

def naive_convolve(fircoeffs, wavdata):
    lside = len(fircoeffs) - 1
    rside = len(fircoeffs) - lside
    return [sum(a * b
                for a, b in zip(fircoeffs[max(lside - i, 0):],
                                wavdata[max(i - lside, 0): i + rside]))
            for i in range(len(wavdata) + len(fircoeffs) - 1)]

convolve = np.convolve if using_numpy else naive_convolve

def convolve_test():
    fircoeffs = [1/16, 4/16, 6/16, 4/16, 1/16]
    data = [0, 1, 0, 0, 0, 1, 2, 3, 4, 5]
    naive_result = naive_convolve(fircoeffs, data)
    print("filter %d, data %d, convolution %d samples"
          % (len(fircoeffs), len(data), len(naive_result)))
    assert len(fircoeffs) + len(data) == len(naive_result) + 1
    print(naive_result)
    print(list(np.convolve(fircoeffs, data)))

def rootmeansquare(seq):
    return (sum(x * x for x in seq) // len(seq))**.5

def pns_decimate(samples):
    """Calculate low and high pass

RMS level
"""
    fircoeffs = [x/32 for x in [-1, 0, 9, 16, 9, 0, -1]]
    lpfsamples = convolve(fircoeffs, samples)[3:-3]
    lpfresidue = [s - l for s, l in zip(samples, lpfsamples)]
    return list(lpfsamples[::2]), rootmeansquare(lpfresidue[::2])

def pns_decimate_test():
    print("pns_decimate_test")
    samples = [1, 1, 2, 2, 3, 3, 4, 4, 1, 4, 1, 4, 1, 4, 1, 4]
    samples = samples + samples
    samples = [x * 2 for x in samples]
    print("orig:", samples)
    lpfsamples, residue = pns_decimate(samples)
    print("lowpass:", lpfsamples)
    print("highpass residue:", residue)

def pns_make_noise(nsamples, level, seed=1):
    out = bytearray()
    for i in range(nsamples):
        seed = seed << 1
        if seed & 0x800:
            seed = seed ^ 0x805
            level = 255 - level
            out.append(level)
        else:
            out.append(128)
        level = 255 - level
        out.append(level)
    return out, level, seed

def constant_noise_test():
    rate = 26758  # 448 samples per frame at 16777216/280896 fps
    nsamples = rate * 5
    outfilename = "noise.wav"
    level, seed = 80, 1
    samples, level, seed = pns_make_noise(nsamples // 2, level, seed)
    with wave.open(outfilename, "w") as outfp:
        outfp.setnchannels(1)
        outfp.setsampwidth(1)
        outfp.setframerate(rate)
        outfp.writeframes(samples)

def pns_calc_test():
    infilename = "build/source2x.wav"
    outfilename_lo = "build/source2x-lpf.wav"
    outfilename_hi = "build/source2x-pns.wav"
    with wave.open(infilename, "r") as infp:
        if infp.getnchannels() != 1:
            raise ValueError("expected mono")
        if infp.getsampwidth() != 2:
            raise ValueError("expected 16-bit")
        rate = infp.getframerate()
        nframes = infp.getnframes()
        samples = array.array("h")
        samples.frombytes(infp.readframes(nframes))
        if sys.byteorder == 'big': samples.byteswap()
    print("rate %d; sample count %d (expected %d), %.2f s"
          % (rate, len(samples), nframes, nframes / rate))
    frame_length = 448
    out_lo = bytearray()
    residues = []
    for i in range(0, nframes, frame_length):
        lpfsamples, residue = pns_decimate(samples[i:i + frame_length])
        out_lo.extend(
            min(255, max(0, 128 + int(round(x/256))))
            for x in lpfsamples
        )
        residues.append(residue)
    print("residue count:", len(residues))
    with wave.open(outfilename_lo, "w") as outfp:
        outfp.setnchannels(1)
        outfp.setsampwidth(1)
        outfp.setframerate(rate // 2)
        outfp.writeframes(out_lo)

    out_hi = bytearray()
    seed = 1
    for residue in residues:
        level = 128 + floor(residue / 192)
        noise, _, seed = pns_make_noise(frame_length // 2, level, seed)
        out_hi.extend(noise)
    with wave.open(outfilename_hi, "w") as outfp:
        outfp.setnchannels(1)
        outfp.setsampwidth(1)
        outfp.setframerate(rate)
        outfp.writeframes(out_hi)

def main(argv=None):
##    convolve_test()
##    pns_decimate_test()
##    constant_noise_test()
    pns_calc_test()

if __name__=='__main__':
    main()
