from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np
from scipy.ndimage import maximum_filter


@dataclass(frozen=True)
class FingerprintConfig:
    sample_rate: int = 22050
    n_fft: int = 2048
    hop_length: int = 512
    peak_neighborhood_freq: int = 20
    peak_neighborhood_time: int = 20
    peak_min_db: float = -55.0
    fan_out: int = 5
    target_min_dt: int = 1
    target_max_dt: int = 100
    target_max_df: int = 200

    @property
    def seconds_per_frame(self) -> float:
        return self.hop_length / self.sample_rate


def _load_mono(path: str, sr: int) -> np.ndarray:
    y, _ = librosa.load(path, sr=sr, mono=True)
    return y.astype(np.float32)


def _peaks(spec_db: np.ndarray, cfg: FingerprintConfig) -> np.ndarray:
    neigh = (cfg.peak_neighborhood_freq, cfg.peak_neighborhood_time)
    local_max = maximum_filter(spec_db, size=neigh, mode="constant", cval=-np.inf)
    mask = (spec_db == local_max) & (spec_db >= cfg.peak_min_db)
    freqs, times = np.where(mask)
    order = np.argsort(times)
    return np.stack([freqs[order], times[order]], axis=1)


def _pack_hash(f1: int, f2: int, dt: int) -> int:
    f1 = int(f1) & 0x3FF
    f2 = int(f2) & 0x3FF
    dt = int(dt) & 0xFFF
    return (f1 << 22) | (f2 << 12) | dt


def extract_fingerprints(
    path: str,
    cfg: FingerprintConfig | None = None,
    y: np.ndarray | None = None,
) -> list[tuple[int, int]]:
    """Return list of (hash, anchor_frame_offset) for an audio file or signal."""
    cfg = cfg or FingerprintConfig()
    if y is None:
        y = _load_mono(path, cfg.sample_rate)
    if len(y) < cfg.n_fft:
        return []

    S = np.abs(librosa.stft(y, n_fft=cfg.n_fft, hop_length=cfg.hop_length, center=True))
    spec_db = librosa.amplitude_to_db(S, ref=np.max)
    peaks = _peaks(spec_db, cfg)
    if len(peaks) < 2:
        return []

    hashes: list[tuple[int, int]] = []
    n = len(peaks)
    times = peaks[:, 1]
    for i in range(n):
        f1, t1 = int(peaks[i, 0]), int(peaks[i, 1])
        j_start = np.searchsorted(times, t1 + cfg.target_min_dt)
        j_end = np.searchsorted(times, t1 + cfg.target_max_dt)
        count = 0
        for j in range(j_start, min(j_end, n)):
            f2, t2 = int(peaks[j, 0]), int(peaks[j, 1])
            df = f2 - f1
            if abs(df) > cfg.target_max_df:
                continue
            dt = t2 - t1
            h = _pack_hash(f1, f2, dt)
            hashes.append((h, t1))
            count += 1
            if count >= cfg.fan_out:
                break
    return hashes
