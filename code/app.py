#!/usr/bin/env python3
"""
RUN4LYF - Streamlit Cybernetic Pacing & Alert Dashboard
Real-time demonstration of the Sense -> Process -> Decide -> Act embedded AI system.
"""

import os
import sys
import json
import time
import pandas as pd
import numpy as np
import streamlit as st

# Add current directory to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from synthetic_runner import SyntheticRunner
from pacing_engine import PacingEngine

# Configure Streamlit page
st.set_page_config(
    page_title="RUN4LYF | AI Hardware & Pacing System",
    page_icon="🏃‍♂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (Dark-mode athletic cybernetic aesthetic)
st.markdown("""
<style>
    /* Global Styles */
    .stApp {
        background-color: #0b0f19;
        color: #e2e8f0;
    }
    
    /* Top Banner */
    .hero-container {
        background: linear-gradient(135deg, #111827 0%, #1e1b4b 50%, #0f172a 100%);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 24px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
    }
    .hero-title {
        font-size: 2.1rem;
        font-weight: 800;
        background: linear-gradient(90deg, #38bdf8, #818cf8, #c084fc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 4px;
    }
    .hero-subtitle {
        color: #94a3b8;
        font-size: 1.0rem;
    }
    
    /* Stat Cards */
    .metric-card {
        background: #151c2c;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    .metric-value {
        font-size: 1.9rem;
        font-weight: 700;
        color: #38bdf8;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    /* State Badges */
    .state-badge {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.95rem;
        letter-spacing: 0.05em;
    }
    .state-WARMUP { background-color: rgba(234, 179, 8, 0.2); color: #facc15; border: 1px solid #facc15; }
    .state-STEADY_FLOW { background-color: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid #4ade80; }
    .state-SPRINT_KICK { background-color: rgba(236, 72, 153, 0.2); color: #f472b6; border: 1px solid #f472b6; }
    .state-FATIGUE_OVERHEAT { background-color: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #f87171; }
    .state-RECOVERY_COOLDOWN { background-color: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid #38bdf8; }
    .state-HAZARD_ALERT { background-color: rgba(220, 38, 38, 0.35); color: #ff4d4d; border: 1px solid #ff4d4d; animation: blinker 1.2s linear infinite; }

    @keyframes blinker {
        50% { opacity: 0.4; }
    }

    /* Audio Deck */
    .deck-container {
        background: #131b2e;
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-radius: 12px;
        padding: 20px;
        margin-top: 10px;
        margin-bottom: 20px;
    }
    .track-title {
        font-size: 1.35rem;
        font-weight: 700;
        color: #f8fafc;
    }
    .track-artist {
        font-size: 0.95rem;
        color: #94a3b8;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_track_catalog():
    """Loads pre-analyzed track catalog from JSON."""
    catalog_path = os.path.join(BASE_DIR, "track_catalog.json")
    if not os.path.exists(catalog_path):
        from audio_scanner import scan_library
        scan_library(output_path=catalog_path)
    with open(catalog_path, "r", encoding="utf-8") as f:
        return json.load(f)

catalog = load_track_catalog()

# Initialize session state for persistent simulation
if "runner" not in st.session_state:
    st.session_state.runner = SyntheticRunner(mood="Focused Pacing", pace_profile="Medium", target_dist_km=5.0)
if "pacing_engine" not in st.session_state:
    st.session_state.pacing_engine = PacingEngine(
        catalog=catalog,
        user_mood="Focused Pacing",
        target_spm=st.session_state.runner.target_spm
    )
if "sim_running" not in st.session_state:
    st.session_state.sim_running = False
if "telemetry_log" not in st.session_state:
    st.session_state.telemetry_log = []
if "decision_log" not in st.session_state:
    st.session_state.decision_log = []
if "last_tick_time" not in st.session_state:
    st.session_state.last_tick_time = time.time()


# ==========================================
# SIDEBAR CONTROLS
# ==========================================
st.sidebar.markdown("### 🏃 Runner Intent & Target")

mood_options = ["Focused Pacing", "Beast Mode", "Chill Flow", "Recovery Jog"]
selected_mood = st.sidebar.selectbox("Current Mood / Vibe", mood_options, index=0)

pace_options = ["Slow", "Medium", "Fast", "Ultra"]
pace_labels = {
    "Slow": "Slow (~146 SPM | 7:03 min/km)",
    "Medium": "Medium (~162 SPM | 5:43 min/km)",
    "Fast": "Fast (~175 SPM | 4:33 min/km)",
    "Ultra": "Ultra (~188 SPM | 3:48 min/km)"
}
selected_pace = st.sidebar.selectbox(
    "Target Pace Profile",
    pace_options,
    format_func=lambda x: pace_labels[x],
    index=1
)

target_dist = st.sidebar.slider("Target Distance (km)", min_value=1.0, max_value=21.1, value=5.0, step=0.5)

# Update runner settings smoothly without resetting workout progress
if (selected_mood != st.session_state.runner.mood or 
    selected_pace != st.session_state.runner.pace_profile or 
    target_dist != st.session_state.runner.target_dist_km):
    st.session_state.runner.update_profile(
        mood=selected_mood,
        pace_profile=selected_pace,
        target_dist_km=target_dist
    )
    st.session_state.pacing_engine.set_user_mood(selected_mood)
    st.session_state.pacing_engine.set_target_spm(st.session_state.runner.target_spm)

st.sidebar.markdown("---")
st.sidebar.markdown("### ⏱️ Simulation Controls")

col_s1, col_s2 = st.sidebar.columns(2)
with col_s1:
    if st.button("▶️ Run / Pause", use_container_width=True):
        st.session_state.sim_running = not st.session_state.sim_running
with col_s2:
    if st.button("🔄 Reset", use_container_width=True):
        st.session_state.runner.reset()
        st.session_state.pacing_engine = PacingEngine(
            catalog=catalog,
            user_mood=selected_mood,
            target_spm=st.session_state.runner.target_spm
        )
        st.session_state.telemetry_log = []
        st.session_state.decision_log = []
        st.session_state.sim_running = False
        st.rerun()

speed_multiplier = st.sidebar.select_slider(
    "Simulation Speed",
    options=[1, 2, 5, 10],
    value=2,
    format_func=lambda x: f"{x}x"
)

step_button = st.sidebar.button("⏩ Step Forward (+5s)", use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚡ Live Event Perturbations")
st.sidebar.caption("Simulate real-world conditions on the runner:")

col_p1, col_p2 = st.sidebar.columns(2)
with col_p1:
    if st.button("⛰️ Hill Surge", use_container_width=True):
        st.session_state.runner.inject_perturbation("hill_climb", 20.0)
    if st.button("🥱 Fatigue Drop", use_container_width=True):
        st.session_state.runner.inject_perturbation("fatigue_spurt", 25.0)
with col_p2:
    if st.button("🚀 Sprint Finish", use_container_width=True):
        st.session_state.runner.inject_perturbation("sprint_finish", 15.0)
    if st.button("🛑 Stumble / Stop", use_container_width=True):
        st.session_state.runner.inject_perturbation("stumble_stop", 10.0)

if st.sidebar.button("🔄 Clear Perturbation", use_container_width=True):
    st.session_state.runner.inject_perturbation(None)


# Advance simulation if active or stepped
dt = 5.0 if step_button else (1.0 * speed_multiplier if st.session_state.sim_running else 0.0)
if dt > 0:
    telemetry = st.session_state.runner.step(dt_sec=dt)
    decision = st.session_state.pacing_engine.process(telemetry, dt_sec=dt)
    st.session_state.telemetry_log.append(telemetry)
    st.session_state.decision_log.append(decision)
    # Keep rolling log bounded
    if len(st.session_state.telemetry_log) > 100:
        st.session_state.telemetry_log.pop(0)
        st.session_state.decision_log.pop(0)
elif not st.session_state.telemetry_log:
    # First frame initialization
    init_telem = st.session_state.runner.step(dt_sec=0.0)
    init_dec = st.session_state.pacing_engine.process(init_telem, dt_sec=0.0)
    st.session_state.telemetry_log.append(init_telem)
    st.session_state.decision_log.append(init_dec)

curr_telem = st.session_state.telemetry_log[-1]
curr_dec = st.session_state.decision_log[-1]


# ==========================================
# MAIN INTERFACE
# ==========================================

# Hero Banner
st.markdown("""
<div class="hero-container">
    <div class="hero-title">RUN4LYF: Cybernetic Bio-Pacing Engine</div>
    <div class="hero-subtitle">
        Embedded Systems & AI Hardware Prototype • Closed-Loop Rhythmic Entrainment • 
        <b>Sense → Process → Decide → Act</b>
    </div>
</div>
""", unsafe_allow_html=True)

# Top Metrics Row
col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)

with col_m1:
    spm_val = curr_telem["cadence_spm"]
    target_spm = curr_telem["target_spm"]
    delta_spm = round(spm_val - target_spm, 1)
    st.metric("Cadence (SPM)", f"{spm_val:.1f}", delta=f"{delta_spm:+.1f} vs Target")

with col_m2:
    hr_val = curr_telem["heart_rate_bpm"]
    zone_val = curr_telem["hr_zone"]
    zone_labels = {1: "Z1 Recovery", 2: "Z2 Aerobic", 3: "Z3 Tempo", 4: "Z4 Threshold", 5: "Z5 Max"}
    st.metric("Heart Rate (BPM)", f"{hr_val:.1f}", delta=zone_labels[zone_val], delta_color="off")

with col_m3:
    st.metric("Pace (min/km)", f"{curr_telem['pace_min_km']:.2f}", f"{curr_telem['speed_kmh']:.1f} km/h")

with col_m4:
    dist_val = curr_telem["distance_km"]
    st.metric("Distance", f"{dist_val:.2f} km", f"{curr_telem['progress_pct']}% of {curr_telem['target_distance_km']}km")

with col_m5:
    mins = int(curr_telem["elapsed_sec"] // 60)
    secs = int(curr_telem["elapsed_sec"] % 60)
    st.metric("Elapsed Time", f"{mins:02d}:{secs:02d}", f"Phase: {curr_telem['workout_phase']}")

# Progress Bar
st.progress(min(1.0, curr_telem["progress_pct"] / 100.0))

# Alert Banner if active
if curr_dec.get("alert_event"):
    st.error(f"🚨 **SYSTEM DECISION ALERT**: {curr_dec['alert_event']}")

# Two-column layout: Left = Playback & Decision, Right = Biometric Telemetry
col_left, col_right = st.columns([1.1, 0.9])

with col_left:
    st.markdown("### 🎧 Dynamic Audio Actuation Deck")
    
    current_track = curr_dec["current_track"]
    state_class = f"state-{curr_dec['state']}"
    min_play_met = curr_dec.get("min_play_met", True)
    lock_left = curr_dec.get("lock_time_remaining", 0.0)
    lock_badge = f'<span style="background: rgba(234, 179, 8, 0.2); color: #facc15; padding: 2px 8px; border-radius: 10px; font-size: 0.8rem; font-weight: bold;">🔒 Min 20s Lock ({lock_left:.0f}s left)</span>' if not min_play_met else '<span style="background: rgba(34, 197, 94, 0.2); color: #4ade80; padding: 2px 8px; border-radius: 10px; font-size: 0.8rem; font-weight: bold;">🔓 Min 20s Threshold Met</span>'

    st.markdown(f"""
    <div class="deck-container">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span class="state-badge {state_class}">STATE: {curr_dec['state']}</span>
            <div style="display: flex; align-items: center; gap: 8px;">
                {lock_badge}
                <span style="color: #94a3b8; font-size: 0.88rem;">
                    Target Energy: <b>{curr_dec['target_energy']:.2f}</b>
                </span>
            </div>
        </div>
        <div class="track-title">{current_track['title']}</div>
        <div class="track-artist">{current_track['artist']} • Native BPM: <b>{current_track['bpm']}</b> • Primary Mood: <b>{current_track.get('primary_mood', 'Dynamic')}</b></div>
    </div>
    """, unsafe_allow_html=True)
    
    # 20-Second DJ Transition Staging Buffer Display
    if curr_dec.get("transition_pending"):
        next_track = curr_dec.get("queued_next_track")
        countdown = curr_dec.get("transition_countdown", 20.0)
        buf_total = 20.0
        buf_progress = min(1.0, max(0.0, 1.0 - (countdown / buf_total)))
        next_title = next_track.get("title", "Next Track") if next_track else "Next Track"
        next_artist = next_track.get("artist", "") if next_track else ""
        next_bpm = next_track.get("bpm", "") if next_track else ""

        st.markdown(f"""
        <div style="background: rgba(99, 102, 241, 0.18); border: 1.5px solid #818cf8; border-radius: 10px; padding: 14px; margin-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 800; font-size: 1.0rem; color: #a5b4fc;">
                    🔀 DJ TRANSITION BUFFER (20s Pre-Cue Active)
                </span>
                <span style="background: #4f46e5; color: #ffffff; padding: 2px 10px; border-radius: 12px; font-weight: bold; font-size: 0.88rem;">
                    ⏱️ {countdown:.1f}s buffer
                </span>
            </div>
            <div style="color: #f8fafc; font-size: 0.95rem; margin-top: 6px;">
                Queued Next: <b>{next_title}</b> &bull; {next_artist} &bull; Native BPM: <b>{next_bpm}</b>
            </div>
            <div style="color: #94a3b8; font-size: 0.82rem; margin-top: 3px;">
                Current track continues playing while acoustic engine phase-locks tempo &amp; downbeats before cut.
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.progress(buf_progress, text=f"Phrase-matching & transition buffer: {countdown:.1f}s remaining")

    # Audio Player with Autoplay
    track_file = current_track.get("filepath")
    if track_file and os.path.exists(track_file):
        # Auto-play is enabled by default to smoothly play music while running
        st.audio(track_file, format="audio/flac", autoplay=True)
    else:
        st.info("Audio track loaded into virtual buffer.")

    # Micro-Tempo Stretch & Harmonic Details
    col_t1, col_t2, col_t3 = st.columns(3)
    with col_t1:
        stretch_pct = curr_dec["stretch_delta_pct"]
        st.markdown(f"**Micro-Tempo Stretch**")
        st.markdown(f"`{stretch_pct:+.2f}%` ({curr_dec['micro_stretch_factor']:.4f}x)")
    with col_t2:
        # Check harmonic relationship
        _, eff_bpm, mode_str = st.session_state.pacing_engine.compute_harmonic_tempo_score(
            current_track["bpm"], curr_dec["ema_cadence_spm"]
        )
        st.markdown(f"**Harmonic Mode**")
        st.markdown(f"`{mode_str}`")
    with col_t3:
        st.markdown(f"**Effective Stride BPM**")
        st.markdown(f"`{eff_bpm:.1f} BPM` $\\approx$ `{curr_dec['ema_cadence_spm']:.1f} SPM`")

    # Transition Alert
    if curr_dec.get("transition_occurred"):
        st.success(f"🔀 **DJ Crossfade Executed**: Transitioned to *{current_track['title']}* ({curr_dec.get('transition_reason')})")

    # Top Candidate Tracks Table
    st.markdown("#### 🎯 Intelligent Utility Score Ranking (Next Candidate Pool)")
    candidates_data = []
    for cand in curr_dec.get("ranked_candidates", []):
        t = cand["track"]
        candidates_data.append({
            "Track": t["title"],
            "Artist": t["artist"][:18],
            "Native BPM": t["bpm"],
            "Harmonic Mode": cand["harmonic_mode"],
            "Tempo Match": f"{cand['tempo_score']:.2f}",
            "Energy Match": f"{cand['energy_score']:.2f}",
            "Mood Score": f"{cand['mood_score']:.2f}",
            "Total Utility": f"{cand['utility']:.3f}"
        })
    st.dataframe(pd.DataFrame(candidates_data), use_container_width=True, hide_index=True)


with col_right:
    st.markdown("### 📊 Real-Time Biometric & Hardware Telemetry")
    
    # Biometric Telemetry Chart
    if len(st.session_state.telemetry_log) > 1:
        chart_df = pd.DataFrame([
            {
                "Time (s)": p["timestamp_sec"],
                "Cadence (SPM)": p["cadence_spm"],
                "Target (SPM)": p["target_spm"],
                "Heart Rate (BPM)": p["heart_rate_bpm"]
            }
            for p in st.session_state.telemetry_log
        ]).set_index("Time (s)")
        
        st.line_chart(chart_df[["Cadence (SPM)", "Target (SPM)"]], height=200)
        st.line_chart(chart_df[["Heart Rate (BPM)"]], height=160)

    # Edge Hardware Telemetry (Simulated ESP32 / Wearable Packets)
    st.markdown("#### 🔬 Simulated Edge MCU Telemetry (ESP32-S3)")
    imu = curr_telem.get("imu_packet", {})
    col_h1, col_h2, col_h3 = st.columns(3)
    with col_h1:
        st.metric("IMU Vertical Shock", f"{imu.get('accel_z_g', 1.0):.2f} g")
    with col_h2:
        st.metric("Pitch Gyro Rate", f"{imu.get('gyro_pitch_dps', 0.0):.1f} °/s")
    with col_h3:
        st.metric("Step Detected", "YES 🟢" if imu.get("step_detected") else "WAIT ⚪")

    # Hardware Specs Expander
    with st.expander("🛠️ Edge Hardware Specification & Telemetry Details"):
        st.markdown("""
        - **Processor**: ESP32-S3 (Xtensa Dual-Core 32-bit LX7 @ 240MHz) with Vector Instructions
        - **Sensors**: LSM6DSOX 6-DOF IMU (I2C @ 400kHz, 100Hz ODR), MAX30102 PPG Optical Pulse (50Hz)
        - **Audio Subsystem**: MAX98357A I2S DAC (44.1kHz, 16-bit stereo DMA ring buffer)
        - **Total Power Draw**: Active ~34.5 mA @ 3.3V $\\rightarrow$ **14.5 hours** on 500mAh LiPo battery
        - **Processing Latency**: IMU autocorrelation step window = 200ms; Policy inference = 1.8ms
        """)


# ==========================================
# FULL MUSIC LIBRARY TAB
# ==========================================
st.markdown("---")
with st.expander(f"📁 Explore Full Local Music Library ({len(catalog)} Tracks Analyzed)"):
    lib_data = []
    for t in catalog:
        lib_data.append({
            "Title": t["title"],
            "Artist": t["artist"],
            "Native BPM": t["bpm"],
            "Half-Time BPM": t["half_time_bpm"],
            "Double-Time BPM": t["double_time_bpm"],
            "Energy (0-1)": t["energy"],
            "Brightness": t["brightness"],
            "Primary Mood": t["primary_mood"],
            "Duration (s)": t["duration_sec"]
        })
    st.dataframe(pd.DataFrame(lib_data), use_container_width=True, hide_index=True)


# Auto-refresh loop when simulation is running
if st.session_state.sim_running:
    time.sleep(0.5 / speed_multiplier)
    st.rerun()
