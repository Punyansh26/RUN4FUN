#!/usr/bin/env python3
"""
RUN4LYF - Synthetic Biometric Runner Telemetry Engine
Simulates realistic human running biomechanics:
- Cadence (SPM) with stride jitter
- Heart rate with cardiac drift & lag
- Ground reaction force / IMU packet emulation
- Fatigue accumulation & workout phases
- Real-time perturbation injection (hills, fatigue spurts, sprint kicks, stumbles)
"""

import time
import random
import math


class SyntheticRunner:
    """
    Simulates a human runner's physiological and kinematic telemetry stream.
    """
    
    PACE_PROFILES = {
        "Slow": {
            "name": "Slow (Warmup / Easy Jog)",
            "base_spm": 146.0,
            "spm_range": (140.0, 152.0),
            "speed_kmh": 8.5,       # ~7:03 min/km
            "base_hr": 128.0,
            "hr_zone": 1,
            "drift_rate": 0.03      # bpm / sec
        },
        "Medium": {
            "name": "Medium (Aerobic Cruise)",
            "base_spm": 162.0,
            "spm_range": (155.0, 168.0),
            "speed_kmh": 10.5,      # ~5:43 min/km
            "base_hr": 146.0,
            "hr_zone": 2,
            "drift_rate": 0.045
        },
        "Fast": {
            "name": "Fast (Threshold Tempo)",
            "base_spm": 175.0,
            "spm_range": (170.0, 182.0),
            "speed_kmh": 13.2,      # ~4:33 min/km
            "base_hr": 164.0,
            "hr_zone": 4,
            "drift_rate": 0.065
        },
        "Ultra": {
            "name": "Ultra (Max Vo2 Sprint)",
            "base_spm": 188.0,
            "spm_range": (182.0, 196.0),
            "speed_kmh": 15.8,      # ~3:48 min/km
            "base_hr": 178.0,
            "hr_zone": 5,
            "drift_rate": 0.09
        }
    }

    MOOD_PROFILES = {
        "Chill Flow": {"target_energy": 0.40, "preferred_tempo": "laid_back"},
        "Focused Pacing": {"target_energy": 0.65, "preferred_tempo": "locked"},
        "Beast Mode": {"target_energy": 0.90, "preferred_tempo": "high_drive"},
        "Recovery Jog": {"target_energy": 0.35, "preferred_tempo": "calm"}
    }

    def __init__(self, mood="Focused Pacing", pace_profile="Medium", target_dist_km=5.0, target_duration_min=30.0):
        self.mood = mood if mood in self.MOOD_PROFILES else "Focused Pacing"
        self.pace_profile = pace_profile if pace_profile in self.PACE_PROFILES else "Medium"
        self.target_dist_km = float(target_dist_km)
        self.target_duration_sec = float(target_duration_min * 60.0)
        
        self.profile_data = self.PACE_PROFILES[self.pace_profile]
        
        # State variables
        self.elapsed_sec = 0.0
        self.distance_km = 0.0
        self.current_spm = 110.0     # starts at walking/light warmup
        self.target_spm = self.profile_data["base_spm"]
        self.current_hr = 95.0       # resting/initial HR
        self.target_hr = self.profile_data["base_hr"]
        self.fatigue_index = 0.0     # 0.0 (fresh) to 1.0 (exhausted)
        self.workout_phase = "WARMUP"
        
        # Active perturbation: None, "hill_climb", "fatigue_spurt", "sprint_finish", "stumble_stop"
        self.active_perturbation = None
        self.perturbation_time_remaining = 0.0
        
        # Internal step simulation
        self.step_phase = 0.0
        self.step_count = 0

    def update_profile(self, mood=None, pace_profile=None, target_dist_km=None):
        """Updates runner profile smoothly without resetting progress, steps, or biomechanics."""
        if mood and mood in self.MOOD_PROFILES:
            self.mood = mood
        if pace_profile and pace_profile in self.PACE_PROFILES:
            self.pace_profile = pace_profile
            self.profile_data = self.PACE_PROFILES[self.pace_profile]
            self.target_spm = self.profile_data["base_spm"]
            self.target_hr = self.profile_data["base_hr"]
        if target_dist_km is not None:
            self.target_dist_km = float(target_dist_km)

    def inject_perturbation(self, perturbation_type, duration_sec=25.0):
        """Injects a real-time running event (hill, fatigue, sprint, stumble)."""
        valid_types = {"hill_climb", "fatigue_spurt", "sprint_finish", "stumble_stop"}
        if perturbation_type in valid_types:
            self.active_perturbation = perturbation_type
            self.perturbation_time_remaining = float(duration_sec)
        elif perturbation_type is None or perturbation_type == "clear":
            self.active_perturbation = None
            self.perturbation_time_remaining = 0.0

    def step(self, dt_sec=1.0):
        """
        Advances the simulation clock by dt_sec and computes updated telemetry.
        """
        self.elapsed_sec += dt_sec
        progress = min(1.0, max(0.0, self.elapsed_sec / max(1.0, self.target_duration_sec)))
        
        # Check active perturbation timer
        if self.active_perturbation:
            self.perturbation_time_remaining -= dt_sec
            if self.perturbation_time_remaining <= 0.0:
                self.active_perturbation = None

        # 1. Determine workout phase based on progress and active perturbations
        if self.active_perturbation == "stumble_stop":
            self.workout_phase = "STUMBLE"
        elif self.active_perturbation == "fatigue_spurt":
            self.workout_phase = "FATIGUE"
        elif self.active_perturbation == "hill_climb":
            self.workout_phase = "HILL"
        elif self.active_perturbation == "sprint_finish":
            self.workout_phase = "SPRINT"
        elif progress < 0.10:
            self.workout_phase = "WARMUP"
        elif progress >= 0.90:
            self.workout_phase = "COOLDOWN"
        elif self.fatigue_index > 0.75:
            self.workout_phase = "FATIGUE"
        else:
            self.workout_phase = "CRUISE"

        # 2. Compute Target Cadence & Heart Rate dynamically
        base_spm = self.profile_data["base_spm"]
        base_hr = self.profile_data["base_hr"]
        
        if self.workout_phase == "WARMUP":
            ramp = progress / 0.10
            desired_spm = 120.0 + (base_spm - 120.0) * ramp
            desired_hr = 100.0 + (base_hr - 100.0) * ramp
        elif self.workout_phase == "COOLDOWN":
            cooldown_ramp = (1.0 - progress) / 0.10
            desired_spm = 125.0 + (base_spm - 125.0) * cooldown_ramp
            desired_hr = 110.0 + (base_hr - 110.0) * cooldown_ramp
        elif self.workout_phase == "HILL":
            desired_spm = base_spm - 9.0     # Cadence sags on steep incline
            desired_hr = base_hr + 16.0      # Cardio demands spike sharply
        elif self.workout_phase == "FATIGUE":
            desired_spm = base_spm - 14.0    # Heavy fatigue stride collapse
            desired_hr = base_hr + 8.0       # Heart works harder for lower pace
        elif self.workout_phase == "SPRINT":
            desired_spm = min(202.0, base_spm + 16.0)
            desired_hr = min(195.0, base_hr + 18.0)
        elif self.workout_phase == "STUMBLE":
            desired_spm = 0.0                # Sudden dead stop
            desired_hr = max(100.0, self.current_hr - 5.0)
        else: # CRUISE
            desired_spm = base_spm
            desired_hr = base_hr

        # 3. Apply Cardiac Drift (slow cumulative HR drift during long cardio)
        cardiac_drift = self.elapsed_sec * (self.profile_data["drift_rate"] / 2.0)
        desired_hr = min(195.0, desired_hr + cardiac_drift)

        # 4. Smooth transition toward desired values (simulating physiological lag)
        spm_alpha = 0.35 if self.workout_phase in ("STUMBLE", "SPRINT") else 0.15
        hr_alpha = 0.08   # Heart rate responds slower than leg cadence
        
        self.current_spm += (desired_spm - self.current_spm) * spm_alpha
        self.current_hr += (desired_hr - self.current_hr) * hr_alpha

        # 5. Add realistic biological noise / stride jitter
        if self.current_spm > 40.0:
            spm_jitter = random.gauss(0.0, 1.1)
            reported_spm = max(60.0, self.current_spm + spm_jitter)
        else:
            reported_spm = max(0.0, self.current_spm)

        hr_jitter = random.gauss(0.0, 0.4)
        reported_hr = max(60.0, self.current_hr + hr_jitter)

        # 6. Distance and Speed computation
        # Speed correlates with cadence and profile
        if reported_spm > 50.0:
            # Stride length scales slightly with cadence
            stride_length_m = 0.95 * (reported_spm / 160.0) ** 0.8
            speed_mps = (reported_spm / 60.0) * stride_length_m
            speed_kmh = speed_mps * 3.6
            pace_min_km = 60.0 / max(0.1, speed_kmh)
        else:
            speed_kmh = 0.0
            pace_min_km = 99.9

        self.distance_km += (speed_kmh / 3600.0) * dt_sec

        # 7. Fatigue index accumulation
        # Higher pace & duration build fatigue faster
        fatigue_rate = (self.profile_data["base_spm"] / 170.0) * 0.0003
        self.fatigue_index = min(1.0, self.fatigue_index + fatigue_rate * dt_sec)

        # 8. HR Zone Classification (Karvonen / Astrand formula)
        # Zone 1 (<130), Zone 2 (130-145), Zone 3 (146-160), Zone 4 (161-175), Zone 5 (>175)
        if reported_hr < 130:
            hr_zone = 1
        elif reported_hr < 146:
            hr_zone = 2
        elif reported_hr < 161:
            hr_zone = 3
        elif reported_hr < 176:
            hr_zone = 4
        else:
            hr_zone = 5

        # 9. Synthetic IMU sensor packet (6-DOF Accelerometer + Gyro)
        # Emulates what an edge ESP32 / LSM6DSOX sensor would sample at 100Hz
        step_freq_hz = reported_spm / 60.0
        self.step_phase += 2.0 * math.pi * step_freq_hz * dt_sec
        accel_z_g = 1.0 + (1.8 * math.sin(self.step_phase) if reported_spm > 50 else 0.0)
        gyro_pitch = 45.0 * math.cos(self.step_phase) if reported_spm > 50 else 0.0
        step_event = bool(reported_spm > 50 and math.sin(self.step_phase) > 0.85)

        if step_event:
            self.step_count += 1

        return {
            "timestamp_sec": round(self.elapsed_sec, 2),
            "cadence_spm": round(reported_spm, 1),
            "target_spm": round(self.profile_data["base_spm"], 1),
            "heart_rate_bpm": round(reported_hr, 1),
            "hr_zone": hr_zone,
            "speed_kmh": round(speed_kmh, 2),
            "pace_min_km": round(pace_min_km, 2),
            "distance_km": round(self.distance_km, 3),
            "target_distance_km": round(self.target_dist_km, 2),
            "elapsed_sec": round(self.elapsed_sec, 1),
            "target_duration_sec": round(self.target_duration_sec, 1),
            "progress_pct": round(progress * 100.0, 1),
            "fatigue_index": round(self.fatigue_index, 3),
            "workout_phase": self.workout_phase,
            "perturbation": self.active_perturbation,
            "total_steps": self.step_count,
            "imu_packet": {
                "accel_z_g": round(accel_z_g, 3),
                "gyro_pitch_dps": round(gyro_pitch, 2),
                "step_detected": step_event
            }
        }

    def reset(self):
        """Resets the runner to initial conditions."""
        self.elapsed_sec = 0.0
        self.distance_km = 0.0
        self.current_spm = 110.0
        self.current_hr = 95.0
        self.fatigue_index = 0.0
        self.workout_phase = "WARMUP"
        self.active_perturbation = None
        self.perturbation_time_remaining = 0.0
        self.step_count = 0
