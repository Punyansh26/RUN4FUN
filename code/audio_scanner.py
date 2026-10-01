#!/usr/bin/env python3
"""
RUN4FUN - Audio Library Feature Extractor
Extracts acoustic features (BPM, half-time/double-time tempo, RMS energy,
spectral centroid, and mood tags) from music tracks for real-time pacing.
"""

import os
import sys
import json
import time
import numpy as np
import soundfile as sf
import librosa
from scipy.signal import decimate

_base_dir = os.path.dirname(os.path.abspath(__file__))
_musiclib_dir = os.path.join(_base_dir, "musiclib")
if os.path.isdir(_musiclib_dir) and len(os.listdir(_musiclib_dir)) > 0:
    MUSIC_DIR = _musiclib_dir
else:
    MUSIC_DIR = os.path.join(_base_dir, "Data", "musiclib")

OUTPUT_JSON = os.path.join(_base_dir, "track_catalog.json")


def clean_track_metadata(filename):
    """Parses track title and artist from filename."""
    name_no_ext = os.path.splitext(filename)[0]
    
    # Handle patterns like "01 - Dhurandhar The Revenge - Aari Aari" or "Billie Eilish - BIRDS OF A FEATHER"
    parts = name_no_ext.split(" - ")
    if len(parts) == 1:
        return parts[0].strip(), "Unknown Artist"
    elif len(parts) == 2:
        # Check if first part is a track number
        if parts[0].strip().isdigit():
            return parts[1].strip(), "Various Artists"
        return parts[1].strip(), parts[0].strip()
    elif len(parts) >= 3:
        # e.g. "01", "Dhurandhar The Revenge", "Aari Aari"
        if parts[0].strip().isdigit():
            return parts[2].strip(), parts[1].strip()
        return " - ".join(parts[2:]).strip(), f"{parts[0]} - {parts[1]}"
    return name_no_ext, "Unknown Artist"


def analyze_audio_file(filepath):
    """
    Extracts core MIR features from an audio file.
    Uses soundfile block reading for speed, analyzing a representative 45s slice.
    """
    info = sf.info(filepath)
    sr = info.samplerate
    duration = info.duration

    # Select representative 45-second segment (avoiding quiet intro/outro if possible)
    start_time = 15.0 if duration > 60 else 0.0
    frames_to_read = int(min(duration - start_time, 45.0) * sr)
    start_frame = int(start_time * sr)

    try:
        data, _ = sf.read(filepath, start=start_frame, frames=frames_to_read, always_2d=True)
    except Exception as e:
        print(f"  Warning: Seek failed ({e}), reading from start...")
        data, _ = sf.read(filepath, frames=int(min(duration, 45.0) * sr), always_2d=True)

    # Convert to mono
    mono = np.mean(data, axis=1)

    # Target ~22,050 Hz for efficient MIR analysis
    target_sr = 22050
    q = max(1, sr // target_sr)
    if q > 1:
        mono_resampled = decimate(mono, q)
        eff_sr = sr // q
    else:
        mono_resampled = mono
        eff_sr = sr

    # Normalize audio buffer
    max_val = np.max(np.abs(mono_resampled))
    if max_val > 1e-4:
        mono_resampled = mono_resampled / max_val

    # 1. Beat tracking / Native BPM
    onset_env = librosa.onset.onset_strength(y=mono_resampled, sr=eff_sr)
    tempo, _ = librosa.beat.beat_track(onset_envelope=onset_env, sr=eff_sr)
    bpm = float(tempo[0]) if hasattr(tempo, "__len__") else float(tempo)
    bpm = round(bpm, 1)

    # 2. RMS Energy (dynamic intensity)
    rms = librosa.feature.rms(y=mono_resampled)
    mean_rms = float(np.mean(rms))
    # Normalized energy score between 0.1 and 1.0
    energy_score = round(float(np.clip(mean_rms * 2.5, 0.1, 1.0)), 2)

    # 3. Spectral Centroid (timbral brightness / drive)
    cent = librosa.feature.spectral_centroid(y=mono_resampled, sr=eff_sr)
    mean_cent = float(np.mean(cent))
    brightness_score = round(float(np.clip(mean_cent / 3500.0, 0.1, 1.0)), 2)

    # 4. Harmonic tempos (for half-time / double-time matching)
    # E.g. Trap / Hip-Hop beats at 80 BPM match 160 SPM stride (half-time)
    # Upbeat tracks at 160 BPM can be stepped to on every downbeat or half-stride
    half_time_bpm = round(bpm / 2.0, 1) if bpm >= 120 else bpm
    double_time_bpm = round(bpm * 2.0, 1) if bpm <= 110 else bpm

    # 5. Algorithmic Mood Affinity
    # Heuristics based on BPM and Energy:
    # - Chill Flow: Moderate BPM (70-115 or 140-155 half-time), low/medium energy (< 0.55)
    # - Focused Pacing: Steady cadence (155-175 SPM / 78-88 or 155-175 BPM), medium/high energy (0.50 - 0.80)
    # - Beast Mode / Sprint: High energy (>0.70) or fast BPM (>165 BPM or >85 half-time with heavy drive)
    # - Recovery Jog: Slower tempo (<145 BPM), relaxed energy (<0.50)
    mood_scores = {
        "Chill Flow": round(float(np.clip(1.0 - energy_score + 0.3 * (1.0 if bpm < 125 else 0.4), 0.1, 0.99)), 2),
        "Focused Pacing": round(float(np.clip(0.6 * energy_score + 0.4 * (1.0 if (150 <= bpm <= 175 or 75 <= bpm <= 88) else 0.6), 0.1, 0.99)), 2),
        "Beast Mode": round(float(np.clip(energy_score * 0.75 + brightness_score * 0.25, 0.1, 0.99)), 2),
        "Recovery Jog": round(float(np.clip(1.1 - energy_score, 0.1, 0.99)), 2)
    }

    primary_mood = max(mood_scores, key=mood_scores.get)

    return {
        "bpm": bpm,
        "half_time_bpm": half_time_bpm,
        "double_time_bpm": double_time_bpm,
        "energy": energy_score,
        "brightness": brightness_score,
        "duration_sec": round(duration, 1),
        "mood_scores": mood_scores,
        "primary_mood": primary_mood,
    }


def scan_library(music_dir=MUSIC_DIR, output_path=OUTPUT_JSON):
    """Scans all audio files in the music directory and saves metadata JSON."""
    if not os.path.exists(music_dir):
        print(f"Error: Music directory {music_dir} does not exist.")
        return []

    audio_extensions = {".flac", ".mp3", ".wav", ".m4a", ".ogg"}
    files = sorted([f for f in os.listdir(music_dir) if os.path.splitext(f)[1].lower() in audio_extensions])
    
    print(f"Found {len(files)} audio tracks in {music_dir}. Beginning feature extraction...")
    
    catalog = []
    start_total = time.time()

    for idx, filename in enumerate(files, 1):
        filepath = os.path.join(music_dir, filename)
        rel_path = os.path.relpath(filepath, os.path.dirname(output_path))
        title, artist = clean_track_metadata(filename)
        
        print(f"[{idx}/{len(files)}] Analyzing: {title} by {artist} ...", end=" ", flush=True)
        t0 = time.time()
        
        try:
            features = analyze_audio_file(filepath)
            track_entry = {
                "id": f"track_{idx:03d}",
                "filename": filename,
                "filepath": rel_path,
                "rel_path": rel_path,
                "title": title,
                "artist": artist,
                **features
            }
            catalog.append(track_entry)
            print(f"Done in {time.time()-t0:.2f}s -> BPM: {features['bpm']}, Energy: {features['energy']}, Mood: {features['primary_mood']}")
        except Exception as e:
            print(f"FAILED ({e})")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)

    print(f"\nSuccessfully indexed {len(catalog)} tracks into {output_path} in {time.time()-start_total:.2f}s")
    return catalog


if __name__ == "__main__":
    scan_library()
