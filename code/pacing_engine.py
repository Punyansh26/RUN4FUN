#!/usr/bin/env python3
"""
RUN4FUN - Closed-Loop Cybernetic Pacing & Decision Engine
Evaluates real-time runner biometrics, estimates physiological state,
calculates harmonic multi-objective utility across the music library,
and determines real-time playback & alert actuation.
"""

import math
import time
from typing import Dict, List, Optional, Any


class PacingEngine:
    """
    Closed-loop control engine that adapts audio playback and alerts
    based on runner biomechanics and user intent.
    """

    def __init__(self, catalog: List[Dict[str, Any]], user_mood: str = "Focused Pacing", target_spm: float = 162.0):
        self.catalog = catalog
        self.user_mood = user_mood
        self.target_spm = float(target_spm)
        
        # Smoothed biometrics (Exponential Moving Average)
        self.ema_spm = self.target_spm
        self.ema_hr = 135.0
        self.spm_history: List[float] = []
        
        # Biometric State Machine
        self.current_state = "WARMUP"
        
        # Current Playback State
        self.current_track: Optional[Dict[str, Any]] = None
        self.track_playback_pos_sec = 0.0
        self.played_history: List[str] = []  # track IDs
        
        # Actuation control
        self.micro_stretch_factor = 1.0  # 1.0 = normal, 0.97 = -3%, 1.03 = +3%
        self.alert_event: Optional[str] = None
        self.transition_queued: bool = False
        self.next_track: Optional[Dict[str, Any]] = None

        # Anti-thrashing & Transition Staging Buffer
        self.min_track_duration_sec = 20.0  # strictly keep each song playing for at least 20 seconds
        self.transition_buffer_sec = 20.0   # 20-second staging buffer before cutting to next track
        self.transition_pending = False
        self.transition_countdown = 0.0
        self.queued_next_track: Optional[Dict[str, Any]] = None
        self.queued_transition_reason: str = ""
        self.time_on_current_track = 0.0
        self.track_start_wall_time = time.time()

        # Select initial track
        self._select_initial_track()

    def _select_initial_track(self):
        """Picks the best starting track based on warmup and mood."""
        ranked = self._rank_tracks(target_spm=self.target_spm, target_energy=0.55, state="WARMUP")
        if ranked:
            self.current_track = ranked[0]["track"]
            self.played_history.append(self.current_track["id"])
            self.time_on_current_track = 0.0
            self.track_playback_pos_sec = 0.0
            self.track_start_wall_time = time.time()

    def _effective_bpm_candidates(self, track_bpm: float) -> List[float]:
        """
        Returns full-time and harmonic half-time / double-time equivalents.
        E.g. for an 85 BPM trap track: candidates are [85.0, 170.0 (double-time)].
        For a 160 BPM drum track: candidates are [160.0, 80.0 (half-time)].
        """
        candidates = [track_bpm]
        if track_bpm <= 115.0:
            candidates.append(track_bpm * 2.0)
        if track_bpm >= 130.0:
            candidates.append(track_bpm / 2.0)
        return candidates

    def compute_harmonic_tempo_score(self, track_bpm: float, runner_spm: float) -> (float, float, str):
        """
        Calculates harmonic tempo match score using Gaussian kernel.
        Returns: (tempo_score, best_matching_effective_bpm, mode_str)
        """
        candidates = self._effective_bpm_candidates(track_bpm)
        best_delta = 999.0
        best_bpm = track_bpm
        best_mode = "1:1 Full-Time"

        for b in candidates:
            delta = abs(b - runner_spm)
            if delta < best_delta:
                best_delta = delta
                best_bpm = b
                if abs(b - track_bpm * 2.0) < 0.1:
                    best_mode = "2:1 Trap/Half-Time Pulse"
                elif abs(b - track_bpm / 2.0) < 0.1:
                    best_mode = "1:2 Half-Stride Accent"
                else:
                    best_mode = "1:1 Direct Octave"

        # Gaussian kernel: sigma = 7.0 SPM
        sigma = 7.0
        score = math.exp(- (best_delta ** 2) / (2.0 * (sigma ** 2)))
        return round(score, 3), best_bpm, best_mode

    def _rank_tracks(self, target_spm: float, target_energy: float, state: str) -> List[Dict[str, Any]]:
        """
        Evaluates the multi-objective utility function across all tracks in the catalog.
        """
        ranked = []
        for track in self.catalog:
            t_bpm = track["bpm"]
            tempo_score, best_eff_bpm, harmonic_mode = self.compute_harmonic_tempo_score(t_bpm, target_spm)
            
            # Energy alignment
            t_energy = track.get("energy", 0.5)
            energy_score = max(0.0, 1.0 - abs(t_energy - target_energy))
            
            # Mood alignment
            mood_scores = track.get("mood_scores", {})
            mood_score = mood_scores.get(self.user_mood, 0.5)
            
            # Recency penalty
            penalty = 0.0
            if track["id"] in self.played_history[-3:]:
                # Heavy penalty if played very recently
                idx_from_end = len(self.played_history) - 1 - self.played_history.rfind(track["id"]) if isinstance(self.played_history, str) else 1
                penalty = 0.45
            elif self.current_track and track["id"] == self.current_track["id"]:
                # Current track has slight continuity bonus unless state changed drastically
                penalty = -0.08

            # Multi-objective utility weights
            w_tempo = 0.45
            w_energy = 0.30
            w_mood = 0.25
            
            total_utility = (w_tempo * tempo_score) + (w_energy * energy_score) + (w_mood * mood_score) - penalty
            total_utility = round(max(0.01, min(0.99, total_utility)), 3)

            ranked.append({
                "track": track,
                "utility": total_utility,
                "tempo_score": tempo_score,
                "energy_score": round(energy_score, 3),
                "mood_score": round(mood_score, 3),
                "best_eff_bpm": best_eff_bpm,
                "harmonic_mode": harmonic_mode,
                "penalty": penalty
            })

        # Sort descending by utility
        ranked.sort(key=lambda x: x["utility"], reverse=True)
        return ranked

    def process(self, telemetry: Dict[str, Any], dt_sec: float = 1.0) -> Dict[str, Any]:
        """
        Processes incoming runner telemetry, updates state machine,
        evaluates utility, and computes audio actuation & alerts.
        """
        raw_spm = telemetry.get("cadence_spm", 150.0)
        raw_hr = telemetry.get("heart_rate_bpm", 130.0)
        hr_zone = telemetry.get("hr_zone", 2)
        fatigue = telemetry.get("fatigue_index", 0.0)
        workout_phase = telemetry.get("workout_phase", "CRUISE")
        perturbation = telemetry.get("perturbation")

        # 1. Sensory Filtering (EMA)
        self.ema_spm = 0.25 * raw_spm + 0.75 * self.ema_spm
        self.ema_hr = 0.12 * raw_hr + 0.88 * self.ema_hr
        self.spm_history.append(self.ema_spm)
        if len(self.spm_history) > 30:
            self.spm_history.pop(0)

        # 2. Biometric State Machine Transition Logic
        prev_state = self.current_state
        self.alert_event = None

        if perturbation == "stumble_stop" or raw_spm < 50.0:
            self.current_state = "HAZARD_ALERT"
            self.alert_event = "Sudden Cadence Collapse / Stumble Detected!"
        elif workout_phase == "WARMUP" or (telemetry.get("progress_pct", 0) < 10 and self.ema_spm < self.target_spm * 0.88):
            self.current_state = "WARMUP"
        elif workout_phase == "COOLDOWN" or telemetry.get("progress_pct", 0) >= 95:
            self.current_state = "RECOVERY_COOLDOWN"
        elif perturbation == "sprint_finish" or self.ema_spm > self.target_spm + 9.0:
            self.current_state = "SPRINT_KICK"
        elif (self.ema_spm < self.target_spm - 10.0 and hr_zone >= 4) or hr_zone == 5 or fatigue > 0.82:
            self.current_state = "FATIGUE_OVERHEAT"
            self.alert_event = "High Cardiac Strain & Cadence Sag! Calibrating Recovery."
        else:
            self.current_state = "STEADY_FLOW"

        # 3. Determine Target Acoustic Energy for Current State
        target_energy_map = {
            "WARMUP": 0.50,
            "STEADY_FLOW": 0.68,
            "SPRINT_KICK": 0.95,
            "FATIGUE_OVERHEAT": 0.48,
            "RECOVERY_COOLDOWN": 0.32,
            "HAZARD_ALERT": 0.15
        }
        target_energy = target_energy_map.get(self.current_state, 0.65)

        # 4. Rank Tracks for Current State
        ranked_candidates = self._rank_tracks(
            target_spm=self.ema_spm if self.ema_spm > 60.0 else self.target_spm,
            target_energy=target_energy,
            state=self.current_state
        )

        best_candidate = ranked_candidates[0] if ranked_candidates else None

        # 5. Playback Advancement & Micro-Tempo Stretching
        self.time_on_current_track += dt_sec
        self.track_playback_pos_sec += dt_sec * self.micro_stretch_factor

        # Micro-tempo stretching calculation for currently playing track
        if self.current_track and self.ema_spm > 60.0:
            _, best_eff_bpm, _ = self.compute_harmonic_tempo_score(self.current_track["bpm"], self.ema_spm)
            # Desired stretch ratio = runner_spm / track_eff_bpm
            raw_stretch = self.ema_spm / max(1.0, best_eff_bpm)
            # Bound stretch to ±3.5% for acoustic transparency (prevent chipmunk or drone artifacts)
            self.micro_stretch_factor = round(float(max(0.965, min(1.035, raw_stretch))), 4)
            stretch_delta_pct = round((self.micro_stretch_factor - 1.0) * 100.0, 2)
        else:
            self.micro_stretch_factor = 1.0
            stretch_delta_pct = 0.0

        # 6. Track Transition Decision Logic (with strict 20s playback lock & 20s staging buffer)
        transition_occurred = False
        transition_reason = ""

        # Measure both simulation time and real wall-clock elapsed time on current track
        now = time.time()
        if not hasattr(self, "track_start_wall_time"):
            self.track_start_wall_time = now
        wall_elapsed = now - self.track_start_wall_time
        sim_elapsed = self.time_on_current_track

        # STRICT INVARIANT: Song must play for AT LEAST 20 seconds before any parameter-based switch can occur
        can_stage = (sim_elapsed >= self.min_track_duration_sec) and (wall_elapsed >= self.min_track_duration_sec)

        # Check if already counting down inside the 20-second transition buffer
        if self.transition_pending:
            self.transition_countdown -= dt_sec
            if self.transition_countdown <= 0.0:
                # 20-second buffer elapsed -> execute transition to queued track
                if self.queued_next_track:
                    self.current_track = self.queued_next_track
                    self.played_history.append(self.current_track["id"])
                    self.time_on_current_track = 0.0
                    self.track_playback_pos_sec = 0.0
                    self.track_start_wall_time = time.time()  # reset timer for newly started song
                    transition_occurred = True
                    transition_reason = self.queued_transition_reason
                self.transition_pending = False
                self.transition_countdown = 0.0
                self.queued_next_track = None
        else:
            # Check if a new transition should enter the 20-second staging buffer
            track_dur = self.current_track.get("duration_sec", 180.0) if self.current_track else 180.0
            
            # A) Approaching natural track outro: start 20s staging buffer before track ends (only if played >=20s)
            if self.track_playback_pos_sec >= (track_dur - self.transition_buffer_sec) and can_stage and best_candidate:
                if best_candidate["track"]["id"] != self.current_track["id"]:
                    self.transition_pending = True
                    self.transition_countdown = max(5.0, min(self.transition_buffer_sec, track_dur - self.track_playback_pos_sec))
                    self.queued_next_track = best_candidate["track"]
                    self.queued_transition_reason = "Track Outro Approaching (20s Pre-Transition Buffer)"
            # B) State or Utility shift based on parameters (Mood, Pace, Surge) strictly after 20s minimum listening
            elif can_stage and best_candidate:
                if best_candidate["track"]["id"] != self.current_track["id"]:
                    should_stage = False
                    stage_reason = ""

                    if self.current_state != prev_state and self.current_state in ("FATIGUE_OVERHEAT", "SPRINT_KICK"):
                        should_stage = True
                        stage_reason = f"Physiological Shift to {self.current_state} (20s Buffer)"
                    else:
                        curr_entry = next((c for c in ranked_candidates if c["track"]["id"] == self.current_track["id"]), None)
                        curr_util = curr_entry["utility"] if curr_entry else 0.4
                        best_util = best_candidate["utility"] if best_candidate else 0.5
                        if best_util - curr_util > 0.28:
                            should_stage = True
                            stage_reason = f"Superior Entrainment Match (+{best_util - curr_util:.2f} utility) (20s Buffer)"

                    if should_stage:
                        self.transition_pending = True
                        self.transition_countdown = self.transition_buffer_sec
                        self.queued_next_track = best_candidate["track"]
                        self.queued_transition_reason = stage_reason

        # 7. Hardware Metronome / Alert Actuation
        # In edge hardware, this controls the I2S audio DAC or piezo buzzer
        metronome_active = bool(self.current_state in ("WARMUP", "FATIGUE_OVERHEAT") or abs(self.ema_spm - self.target_spm) > 7.0)

        return {
            "state": self.current_state,
            "prev_state": prev_state,
            "ema_cadence_spm": round(self.ema_spm, 1),
            "ema_heart_rate": round(self.ema_hr, 1),
            "current_track": self.current_track,
            "track_playback_pos_sec": round(self.track_playback_pos_sec, 1),
            "track_duration_sec": self.current_track.get("duration_sec", 180.0) if self.current_track else 180.0,
            "time_on_current_track": round(self.time_on_current_track, 1),
            "micro_stretch_factor": self.micro_stretch_factor,
            "stretch_delta_pct": stretch_delta_pct,
            "ranked_candidates": ranked_candidates[:6],
            "transition_occurred": transition_occurred,
            "transition_reason": transition_reason,
            "transition_pending": self.transition_pending,
            "transition_countdown": max(0.0, round(self.transition_countdown, 1)),
            "queued_next_track": self.queued_next_track,
            "alert_event": self.alert_event,
            "metronome_active": metronome_active,
            "target_energy": target_energy,
            "min_play_met": can_stage,
            "wall_elapsed_sec": round(wall_elapsed, 1),
            "lock_time_remaining": max(0.0, round(self.min_track_duration_sec - min(sim_elapsed, wall_elapsed), 1))
        }

    def set_user_mood(self, mood: str):
        """Allows real-time user mood adjustment."""
        self.user_mood = mood

    def set_target_spm(self, spm: float):
        """Allows target pace adjustment."""
        self.target_spm = float(spm)
