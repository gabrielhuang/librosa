#!/usr/bin/env python
# CREATED:2013-03-08 15:25:18 by Brian McFee <brm2132@columbia.edu>
#  unit tests for librosa.feature (feature.py)
#
# Run me as follows:
#   cd tests/
#   nosetests -v
#
# This test suite verifies that librosa core routines match (numerically) the output
# of various DPWE matlab implementations on a broad range of input parameters.
#
# All test data is generated by the Matlab script "makeTestData.m".
# Each test loads in a .mat file which contains the input and desired output for a given
# function.  The test then runs the librosa implementation and verifies the results
# against the desired output, typically via numpy.allclose().
#
# CAVEATS:
#
#   Currently, not all tests are exhaustive in parameter space.  This is typically due
#   restricted functionality of the librosa implementations.  Similarly, there is no
#   fuzz-testing here, so behavior on invalid inputs is not yet well-defined.
#

# Disable cache
import os
try:
    os.environ.pop('LIBROSA_CACHE_DIR')
except KeyError:
    pass

import matplotlib
matplotlib.use('Agg')
import six
import glob
import numpy as np
import scipy.io

from nose.tools import eq_, raises
import warnings

import librosa

# -- utilities --#
def files(pattern):
    test_files = glob.glob(pattern)
    test_files.sort()
    return test_files

def load(infile):
    DATA = scipy.io.loadmat(infile, chars_as_strings=True)
    return DATA
# --           --#


# -- Tests     --#
def test_hz_to_mel():
    def __test_to_mel(infile):
        DATA = load(infile)
        z = librosa.hz_to_mel(DATA['f'], DATA['htk'])

        assert np.allclose(z, DATA['result'])

    for infile in files('data/feature-hz_to_mel-*.mat'):
        yield (__test_to_mel, infile)

    pass


def test_mel_to_hz():

    def __test_to_hz(infile):
        DATA = load(infile)
        z = librosa.mel_to_hz(DATA['f'], DATA['htk'])

        assert np.allclose(z, DATA['result'])

    for infile in files('data/feature-mel_to_hz-*.mat'):
        yield (__test_to_hz, infile)

    pass


def test_hz_to_octs():
    def __test_to_octs(infile):
        DATA = load(infile)
        z = librosa.hz_to_octs(DATA['f'])

        assert np.allclose(z, DATA['result'])

    for infile in files('data/feature-hz_to_octs-*.mat'):
        yield (__test_to_octs, infile)

    pass


def test_melfb():

    def __test(infile):
        DATA = load(infile)

        wts = librosa.filters.mel(DATA['sr'][0],
                                  DATA['nfft'][0],
                                  n_mels=DATA['nfilts'][0],
                                  fmin=DATA['fmin'][0],
                                  fmax=DATA['fmax'][0],
                                  htk=DATA['htk'][0])

        # Our version only returns the real-valued part.
        # Pad out.
        wts = np.pad(wts, [(0, 0),
                              (0, int(DATA['nfft'][0]//2 - 1))],
                        mode='constant')

        eq_(wts.shape, DATA['wts'].shape)
        assert np.allclose(wts, DATA['wts'])

    for infile in files('data/feature-melfb-*.mat'):
        yield (__test, infile)


def test_chromafb():

    def __test(infile):
        DATA = load(infile)

        octwidth = DATA['octwidth'][0, 0]
        if octwidth == 0:
            octwidth = None

        wts = librosa.filters.chroma(DATA['sr'][0, 0],
                                     DATA['nfft'][0, 0],
                                     DATA['nchroma'][0, 0],
                                     A440=DATA['a440'][0, 0],
                                     ctroct=DATA['ctroct'][0, 0],
                                     octwidth=octwidth,
                                     norm=2,
                                     base_c=False)

        # Our version only returns the real-valued part.
        # Pad out.
        wts = np.pad(wts, [(0, 0),
                           (0, int(DATA['nfft'][0, 0]//2 - 1))],
                     mode='constant')

        eq_(wts.shape, DATA['wts'].shape)
        assert np.allclose(wts, DATA['wts'])

    for infile in files('data/feature-chromafb-*.mat'):
        yield (__test, infile)


def test__window():

    def __test(n, window):

        wdec = librosa.filters.__float_window(window)

        if n == int(n):
            assert np.allclose(wdec(n), window(n))
        else:
            wf = wdec(n)
            fn = int(np.floor(n))
            assert not np.any(wf[fn:])

    for n in [16, 16.0, 16.25, 16.75]:
        for window_name in ['barthann', 'bartlett', 'blackman',
                            'blackmanharris', 'bohman', 'boxcar', 'cosine',
                            'flattop', 'hamming', 'hann', 'hanning',
                            'nuttall', 'parzen', 'triang']:
            window = getattr(scipy.signal.windows, window_name)
            yield __test, n, window


def test_constant_q():

    def __test(sr, fmin, n_bins, bins_per_octave, tuning, resolution,
               pad_fft, norm):

        F, lengths = librosa.filters.constant_q(sr,
                                                fmin=fmin,
                                                n_bins=n_bins,
                                                bins_per_octave=bins_per_octave,
                                                tuning=tuning,
                                                resolution=resolution,
                                                pad_fft=pad_fft,
                                                norm=norm)

        assert np.all(lengths <= F.shape[1])

        eq_(len(F), n_bins)

        if not pad_fft:
            return

        eq_(np.mod(np.log2(F.shape[1]), 1.0), 0.0)

        # Check for vanishing negative frequencies
        F_fft = np.abs(np.fft.fft(F, axis=1))
        # Normalize by row-wise peak
        F_fft = F_fft / np.max(F_fft, axis=1, keepdims=True)
        assert not np.any(F_fft[:, -F_fft.shape[1]//2:] > 1e-4)

    sr = 11025

    # Try to make a cq basis too close to nyquist
    yield (raises(librosa.ParameterError)(__test), sr, sr/2.0, 1, 12, 0, 1, True, 1)

    # with negative fmin
    yield (raises(librosa.ParameterError)(__test), sr, -60, 1, 12, 0, 1, True, 1)

    # with negative bins_per_octave
    yield (raises(librosa.ParameterError)(__test), sr, 60, 1, -12, 0, 1, True, 1)

    # with negative bins
    yield (raises(librosa.ParameterError)(__test), sr, 60, -1, 12, 0, 1, True, 1)

    # with negative resolution
    yield (raises(librosa.ParameterError)(__test), sr, 60, 1, 12, 0, -1, True, 1)

    # with negative norm
    yield (raises(librosa.ParameterError)(__test), sr, 60, 1, 12, 0, 1, True, -1)

    for fmin in [None, librosa.note_to_hz('C3')]:
        for n_bins in [12, 24]:
            for bins_per_octave in [12, 24]:
                for tuning in [0, 0.25]:
                    for resolution in [1, 2]:
                        for norm in [1, 2]:
                            for pad_fft in [False, True]:
                                yield (__test, sr, fmin, n_bins,
                                       bins_per_octave, tuning,
                                       resolution, pad_fft,
                                       norm)


def test_window_bandwidth():

    eq_(librosa.filters.window_bandwidth('hann'),
        librosa.filters.window_bandwidth(scipy.signal.hann))


def test_window_bandwidth_missing():
    warnings.resetwarnings()
    with warnings.catch_warnings(record=True) as out:
        x = librosa.filters.window_bandwidth('unknown_window')
        eq_(x, 1)
        assert len(out) > 0
        assert out[0].category is UserWarning
        assert 'Unknown window function' in str(out[0].message)


def binstr(m):

    out = []
    for row in m:
        line = [' '] * len(row)
        for i in np.flatnonzero(row):
            line[i] = '.'
        out.append(''.join(line))
    return '\n'.join(out)


def test_cq_to_chroma():

    def __test(n_bins, bins_per_octave, n_chroma, fmin, base_c, window):
        # Fake up a cqt matrix with the corresponding midi notes

        if fmin is None:
            midi_base = 24  # C2
        else:
            midi_base = librosa.hz_to_midi(fmin)

        midi_notes = np.linspace(midi_base,
                                 midi_base + n_bins * 12.0 / bins_per_octave,
                                 endpoint=False,
                                 num=n_bins)
        #  We don't care past 2 decimals here.
        # the log2 inside hz_to_midi can cause problems though.
        midi_notes = np.around(midi_notes, decimals=2)
        C = np.diag(midi_notes)

        cq2chr = librosa.filters.cq_to_chroma(n_input=C.shape[0],
                                              bins_per_octave=bins_per_octave,
                                              n_chroma=n_chroma,
                                              fmin=fmin,
                                              base_c=base_c,
                                              window=window)

        chroma = cq2chr.dot(C)
        for i in range(n_chroma):
            v = chroma[i][chroma[i] != 0]
            v = np.around(v, decimals=2)

            if base_c:
                resid = np.mod(v, 12)
            else:
                resid = np.mod(v - 9, 12)

            resid = np.round(resid * n_chroma / 12.0)
            assert np.allclose(np.mod(i - resid, 12), 0.0), i-resid

    for n_octaves in [2, 3, 4]:
        for semitones in [1, 3]:
            for n_chroma in 12 * np.arange(1, 1 + semitones):
                for fmin in [None] + list(librosa.midi_to_hz(range(48, 61))):
                    for base_c in [False, True]:
                        for window in [None, [1]]:
                            bins_per_octave = 12 * semitones
                            n_bins = n_octaves * bins_per_octave

                            if np.mod(bins_per_octave, n_chroma) != 0:
                                tf = raises(librosa.ParameterError)(__test)
                            else:
                                tf = __test
                            yield (tf, n_bins, bins_per_octave,
                                   n_chroma, fmin, base_c, window)
