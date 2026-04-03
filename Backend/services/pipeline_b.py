import numpy as np
import librosa

# ===== CONFIG =====

TARGET_SR = 16000
FRAME_LENGTH = 2048
HOP_LENGTH = 512
TOP_DB = 30 # silence threshold — higher = more silence detected
FMIN = 75   # min pitch Hz for human speech
FMAX = 400  # max pitch Hz for human speech
MIN_PAUSE_SEC = 0.25  # gaps shorter than this are not counted as pauses


# ==== MODE THRESHOLDS ====

MODES = {
    "academic": {
        "pauses_per_min_few":      2,
        "pauses_per_min_good":     10,
        "pauses_per_min_moderate": 16,
        "avg_pause_short":         0.4,
        "avg_pause_moderate":      0.7,
        "hesitation_good":         0.20,
        "hesitation_moderate":     0.32,
    },
    "public_speaking": {
        "pauses_per_min_few":      2,
        "pauses_per_min_good":     14,
        "pauses_per_min_moderate": 20,
        "avg_pause_short":         0.6,
        "avg_pause_moderate":      1.0,
        "hesitation_good":         0.28,
        "hesitation_moderate":     0.40,
    }
}

DEFAULT_MODE = "academic"


# ==== AUDIO LOADING ====

def load_audio(path: str):
    y, sr = librosa.load(path, sr=TARGET_SR, mono=True)
    return y, sr


# ==== SILENCE / SPEECH DETECTION ====

def _detect_speech_intervals(y, sr):
    intervals = librosa.effects.split(
        y,
        top_db=TOP_DB,
        frame_length=FRAME_LENGTH,
        hop_length=HOP_LENGTH
    )
    return intervals


# ==== FEATURE EXTRACTION ====

def _extract_timing_features(y, sr, intervals) -> dict:
    total_duration = len(y) / sr

    if len(intervals) == 0:
        return {
            "total_duration_sec":     float(total_duration),
            "speech_duration_sec":    0.0,
            "pause_count":            0,
            "avg_pause_duration_sec": 0.0,
            "hesitation_ratio":       1.0
        }

    speech_samples      = sum((end - start) for start, end in intervals)
    speech_duration_sec = speech_samples / sr

    pause_durations = []
    for i in range(1, len(intervals)):
        prev_end   = intervals[i - 1][1]
        curr_start = intervals[i][0]
        gap_sec    = (curr_start - prev_end) / sr
        if gap_sec >= MIN_PAUSE_SEC:
            pause_durations.append(gap_sec)

    pause_count        = len(pause_durations)
    avg_pause_duration = float(np.mean(pause_durations)) if pause_durations else 0.0

    silence_duration_sec = max(total_duration - speech_duration_sec, 0.0)
    hesitation_ratio     = silence_duration_sec / total_duration if total_duration > 0 else 0.0

    return {
        "total_duration_sec":     float(total_duration),
        "speech_duration_sec":    float(speech_duration_sec),
        "pause_count":            int(pause_count),
        "avg_pause_duration_sec": float(avg_pause_duration),
        "hesitation_ratio":       float(hesitation_ratio)
    }


def _extract_pitch_energy_features(y, sr) -> dict:

    # Energy (RMS)
    rms         = librosa.feature.rms(y=y, frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH)[0]
    energy_mean = float(np.mean(rms))
    energy_std  = float(np.std(rms))

    # Pitch via YIN
    f0       = librosa.yin(y, fmin=FMIN, fmax=FMAX, sr=sr,
                           frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH)
    f0_valid = f0[np.isfinite(f0)]
    f0_valid = f0_valid[f0_valid > 0]

    if len(f0_valid) == 0:
        return {
            "pitch_mean_hz":  0.0,
            "pitch_std_hz":   0.0,
            "pitch_range_hz": 0.0,
            "energy_mean":    energy_mean,
            "energy_std":     energy_std,
        }

    pitch_range = float(np.percentile(f0_valid, 95) - np.percentile(f0_valid, 5))

    return {
        "pitch_mean_hz":  float(np.mean(f0_valid)),
        "pitch_std_hz":   float(np.std(f0_valid)),
        "pitch_range_hz": pitch_range,
        "energy_mean":    energy_mean,
        "energy_std":     energy_std,
    }


def extract_features(audio_path: str) -> dict:
    #Full feature extraction — returns flat dict of all features.
    y, sr     = load_audio(audio_path)
    intervals = _detect_speech_intervals(y, sr)

    timing_feats       = _extract_timing_features(y, sr, intervals)
    pitch_energy_feats = _extract_pitch_energy_features(y, sr)

    features = {}
    features.update(timing_feats)
    features.update(pitch_energy_feats)
    return features


# ==== SCORING ====

def _score_fluency(features: dict, thresholds: dict) -> tuple:
    score    = 0
    feedback = []

    total_dur        = features["total_duration_sec"]
    pause_count      = features["pause_count"]
    avg_pause        = features["avg_pause_duration_sec"]
    hesitation_ratio = features["hesitation_ratio"]

    duration_minutes  = total_dur / 60.0
    pauses_per_minute = (pause_count / duration_minutes) if duration_minutes > 0 else 0

    t = thresholds

    # --- Pause count per minute ---
    if pauses_per_minute < t["pauses_per_min_few"]:
        score += 1
        feedback.append(
            "Your delivery has very few pauses, which can sound rushed or robotic. "
            "Natural pauses help listeners follow along."
        )
    elif pauses_per_minute <= t["pauses_per_min_good"]:
        score += 3
        feedback.append("Your use of pauses is natural and well-paced.")
    elif pauses_per_minute <= t["pauses_per_min_moderate"]:
        score += 2
        feedback.append("Your pauses are noticeable but still within a moderate range.")
    else:
        score += 1
        feedback.append(
            "You pause quite frequently, which may reduce fluency. "
            "Try to keep your thoughts more connected."
        )

    # --- Average pause duration ---
    if avg_pause == 0.0:
        score += 1
        feedback.append(
            "No distinct pauses were detected. Natural pausing improves clarity and delivery."
        )
    elif avg_pause <= t["avg_pause_short"]:
        score += 3
        feedback.append("Your pauses are mostly short and natural.")
    elif avg_pause <= t["avg_pause_moderate"]:
        score += 2
        feedback.append("Some of your pauses are slightly long — aim to keep them concise.")
    else:
        score += 1
        feedback.append(
            "Your pauses are often quite long, which may disrupt the flow of your delivery."
        )

    # --- Hesitation ratio ---
    if hesitation_ratio <= t["hesitation_good"]:
        score += 3
        feedback.append("Your speech flow is smooth and well-timed.")
    elif hesitation_ratio <= t["hesitation_moderate"]:
        score += 2
        feedback.append("There is a moderate amount of silence in your delivery.")
    else:
        score += 1
        feedback.append(
            "A large portion of your delivery contains silence or hesitation. "
            "Practising with a script or outline may help."
        )

    return score / 3.0, feedback


def _score_prosody(features: dict) -> tuple:
    score    = 0
    feedback = []

    pitch_std   = features["pitch_std_hz"]
    pitch_range = features["pitch_range_hz"]
    energy_std  = features["energy_std"]

    # --- Pitch variability ---
    if pitch_std >= 60:
        score += 3
        feedback.append("Your pitch variation makes your delivery sound expressive and engaging.")
    elif pitch_std >= 35:
        score += 2
        feedback.append(
            "Your pitch variation is moderate — try varying your tone more to emphasise key points."
        )
    else:
        score += 1
        feedback.append(
            "Your speech sounds quite monotone. Try raising and lowering your pitch "
            "to make your delivery more engaging."
        )

    # --- Pitch range ---
    if pitch_range >= 80:
        score += 3
        feedback.append("Your pitch range supports an engaging and varied speaking style.")
    elif pitch_range >= 40:
        score += 2
        feedback.append("Your pitch range is acceptable but could be broader for more impact.")
    else:
        score += 1
        feedback.append(
            "Your pitch range is quite narrow. Try to vary your intonation — "
            "rise at key moments and drop at conclusions."
        )

    # --- Energy / loudness variability ---
    if energy_std >= 0.03:
        score += 3
        feedback.append("Your loudness variation is good and helps maintain listener engagement.")
    elif energy_std >= 0.01:
        score += 2
        feedback.append(
            "Your loudness variation is moderate. Emphasising important words more "
            "strongly would improve your delivery."
        )
    else:
        score += 1
        feedback.append(
            "Your voice is quite flat in volume. Try to speak louder on key points "
            "and softer in transitions to add expressiveness."
        )

    return score / 3.0, feedback


def _score_to_level(score: float) -> str:
    if score >= 2.67:
        return "High"
    elif score >= 2.0:
        return "Medium"
    else:
        return "Low"


def assess_delivery(features: dict, mode: str = DEFAULT_MODE) -> dict:
    if mode not in MODES:
        mode = DEFAULT_MODE

    thresholds = MODES[mode]

    fluency_score, fluency_feedback = _score_fluency(features, thresholds)
    prosody_score, prosody_feedback = _score_prosody(features)

    overall_score = (fluency_score + prosody_score) / 2.0
    overall_level = _score_to_level(overall_score)

    feedback = fluency_feedback + prosody_feedback

    if overall_level == "High":
        summary = "Your delivery is strong and clear — well done."
    elif overall_level == "Medium":
        summary = "Your delivery is fairly good but has some areas for improvement."
    else:
        summary = "Your delivery needs improvement in fluency and expressiveness."

    feedback.insert(0, summary)

    return {
        "fluency_score": round(fluency_score, 2),
        "prosody_score": round(prosody_score, 2),
        "overall_score": round(overall_score, 2),
        "overall_level": overall_level,
        "mode":          mode,
        "feedback":      feedback,
    }


# ==== PUBLIC FUNCTION ====

def analyze(audio_path: str, mode: str = DEFAULT_MODE) -> dict:
    #Full Pipeline B entry point. Called from main.py.
    features   = extract_features(audio_path)
    assessment = assess_delivery(features, mode=mode)

    return {
        "features":   features,
        "assessment": assessment,
    }
