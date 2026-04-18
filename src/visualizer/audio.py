from __future__ import annotations

import librosa
import numpy as np

N_FFT = 2048


def load_audio(path: str, sr: int = 44100) -> tuple[np.ndarray, int, float]:
    y, sr = librosa.load(path, sr=sr, mono=True)
    duration = len(y) / sr
    return y.astype(np.float32), sr, duration


def _log_band_edges(sr: int, n_bands: int, n_fft: int, fmin: float = 30.0) -> np.ndarray:
    fmax = sr / 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    edges = np.geomspace(fmin, fmax, n_bands + 1)
    idx = np.searchsorted(freqs, edges)
    return np.clip(idx, 0, len(freqs) - 1)


def compute_band_matrix(
    y: np.ndarray, sr: int, fps: int, n_bands: int = 60, n_fft: int = N_FFT
) -> np.ndarray:
    """Return (n_bands, n_frames) float32 matrix, values 0..1."""
    hop = max(1, sr // fps)
    S = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop, center=True))
    edges = _log_band_edges(sr, n_bands, n_fft)
    bands = np.zeros((n_bands, S.shape[1]), dtype=np.float32)
    for i in range(n_bands):
        lo, hi = edges[i], max(edges[i + 1], edges[i] + 1)
        bands[i] = S[lo:hi].mean(axis=0)
    db = librosa.amplitude_to_db(bands, ref=np.max)
    return np.clip((db + 60.0) / 60.0, 0.0, 1.0).astype(np.float32)


def compute_rms(y: np.ndarray, sr: int, fps: int, n_fft: int = N_FFT) -> np.ndarray:
    hop = max(1, sr // fps)
    rms = librosa.feature.rms(y=y, frame_length=n_fft, hop_length=hop, center=True)[0]
    peak = float(rms.max()) + 1e-9
    return (rms / peak).astype(np.float32)


def waveform_sample(
    y: np.ndarray, sr: int, fps: int, frame_idx: int, n_samples: int = 1024
) -> np.ndarray:
    hop = max(1, sr // fps)
    center = frame_idx * hop
    start = max(0, center - n_samples // 2)
    end = start + n_samples
    if end > len(y):
        end = len(y)
        start = max(0, end - n_samples)
    chunk = y[start:end]
    if len(chunk) < n_samples:
        chunk = np.pad(chunk, (0, n_samples - len(chunk)))
    return chunk.astype(np.float32)
