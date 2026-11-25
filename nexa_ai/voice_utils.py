from __future__ import annotations

import numpy as np


def resample_mono_int16(samples, source_rate: int, target_rate: int = 16000):
    """Convert mono PCM audio from a device-native rate to the Whisper sample rate."""
    if source_rate <= 0 or target_rate <= 0:
        raise ValueError("Audio sample rates must be positive.")
    audio = np.asarray(samples).reshape(-1)
    if audio.size == 0:
        return np.asarray([], dtype=np.int16)
    if source_rate == target_rate:
        return np.clip(audio, -32768, 32767).astype(np.int16, copy=True)
    target_count = max(1, int(round(audio.size * target_rate / source_rate)))
    source_positions = np.arange(audio.size, dtype=np.float64)
    target_positions = np.arange(target_count, dtype=np.float64) * source_rate / target_rate
    converted = np.interp(target_positions, source_positions, audio.astype(np.float32))
    return np.clip(np.rint(converted), -32768, 32767).astype(np.int16)
