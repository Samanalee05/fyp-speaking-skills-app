import os
import imageio_ffmpeg
import subprocess
import tempfile
from pathlib import Path
import pickle

import numpy as np
import librosa
import parselmouth
from parselmouth.praat import call
from scipy.signal import find_peaks
from scipy.ndimage import uniform_filter1d

# ===== CONFIG =====
TARGET_SR    = 16000
FRAME_LENGTH = 2048
HOP_LENGTH   = 512
TOP_DB       = 30
FMIN         = 75
FMAX         = 400
MIN_PAUSE_SEC = 0.25

_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# ===== CLASSIFIER =====
_MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "rf_classifier.pkl"
_LE_PATH    = Path(__file__).resolve().parent.parent / "models" / "label_encoder.pkl"

print(f"[Pipeline B] Loading RF classifier from: {_MODEL_PATH}")
with open(_MODEL_PATH, "rb") as f:
    _clf = pickle.load(f)
with open(_LE_PATH, "rb") as f:
    _le = pickle.load(f)
print("[Pipeline B] Classifier loaded successfully.")

FEATURE_COLS = [
    "total_duration_sec", "speech_duration_sec", "pause_count",
    "avg_pause_duration_sec", "hesitation_ratio",
    "pitch_mean_hz", "pitch_std_hz", "pitch_range_hz",
    "energy_mean", "energy_std",
    "jitter", "shimmer", "hnr",
    "syllable_rate_per_min", "estimated_syllable_count",
]

# ===== MODE THRESHOLDS =====
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
    },
}
DEFAULT_MODE = "academic"


# ===== AUDIO LOADING =====
def _convert_to_wav(src: str) -> str:
    """
    Convert a compressed audio file (M4A, MP3, MP4) to a temporary WAV file
    using ffmpeg. Returns the path to the temp WAV file.
    Caller is responsible for deleting the temp file.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    subprocess.run(
        [_FFMPEG, "-y", "-i", src,
         "-ar", str(TARGET_SR), "-ac", "1", "-f", "wav", tmp.name],
        check=True,
        capture_output=True,
    )
    return tmp.name


def load_audio(path: str):
    """
    Load audio as a mono float32 waveform resampled to TARGET_SR.
    Compressed formats (M4A, MP3, MP4) are converted via ffmpeg first.
    """
    ext      = os.path.splitext(path)[1].lower()
    tmp_path = None

    try:
        if ext in {".m4a", ".mp3", ".mp4"} and _FFMPEG and os.path.exists(_FFMPEG):
            tmp_path  = _convert_to_wav(path)
            load_path = tmp_path
        else:
            load_path = path

        y, sr = librosa.load(load_path, sr=TARGET_SR, mono=True)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    return y, sr


# ===== SPEECH / SILENCE DETECTION =====
def _detect_speech_intervals(y, sr):
    return librosa.effects.split(
        y, top_db=TOP_DB, frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH
    )


# ===== FEATURE EXTRACTION =====
def _extract_timing_features(y, sr, intervals) -> dict:
    total_duration = len(y) / sr

    if len(intervals) == 0:
        return {
            "total_duration_sec":     float(total_duration),
            "speech_duration_sec":    0.0,
            "pause_count":            0,
            "avg_pause_duration_sec": 0.0,
            "hesitation_ratio":       1.0,
        }

    speech_samples      = sum(e - s for s, e in intervals)
    speech_duration_sec = speech_samples / sr

    pause_durations = [
        (intervals[i][0] - intervals[i-1][1]) / sr
        for i in range(1, len(intervals))
        if (intervals[i][0] - intervals[i-1][1]) / sr >= MIN_PAUSE_SEC
    ]

    return {
        "total_duration_sec":     float(total_duration),
        "speech_duration_sec":    float(speech_duration_sec),
        "pause_count":            int(len(pause_durations)),
        "avg_pause_duration_sec": float(np.mean(pause_durations)) if pause_durations else 0.0,
        "hesitation_ratio":       float(max(total_duration - speech_duration_sec, 0.0) / total_duration),
    }


def _extract_pitch_energy_features(y, sr) -> dict:
    rms        = librosa.feature.rms(y=y, frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH)[0]
    energy_mean = float(np.mean(rms))
    energy_std  = float(np.std(rms))

    f0       = librosa.yin(y, fmin=FMIN, fmax=FMAX, sr=sr,
                           frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH)
    f0_valid = f0[np.isfinite(f0) & (f0 > 0)]

    if len(f0_valid) == 0:
        return {"pitch_mean_hz": 0.0, "pitch_std_hz": 0.0,
                "pitch_range_hz": 0.0, "energy_mean": energy_mean,
                "energy_std": energy_std}

    return {
        "pitch_mean_hz":  float(np.mean(f0_valid)),
        "pitch_std_hz":   float(np.std(f0_valid)),
        "pitch_range_hz": float(np.percentile(f0_valid, 95) - np.percentile(f0_valid, 5)),
        "energy_mean":    energy_mean,
        "energy_std":     energy_std,
    }


def _extract_parselmouth_features(y, sr) -> dict:
    """
    Extract voice quality features using Parselmouth (Praat wrapper).
    Jitter: cycle-to-cycle pitch perturbation - high values indicate vocal tension.
    Shimmer: cycle-to-cycle amplitude perturbation- high values indicate breathiness.
    HNR: harmonics-to-noise ratio- higher values indicate clearer more voiced speech.
    """
    sound = parselmouth.Sound(y, sampling_frequency=sr)
    try:
        pp      = call(sound, "To PointProcess (periodic, cc)", 75, 500)
        jitter  = call(pp, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
        shimmer = call([sound, pp], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
        harm    = call(sound, "To Harmonicity (cc)", 0.01, 75, 0.1, 1.0)
        hnr     = call(harm, "Get mean", 0, 0)
    except Exception:
        jitter, shimmer, hnr = 0.0, 0.0, 0.0

    return {
        "jitter":  float(jitter)  if jitter  is not None else 0.0,
        "shimmer": float(shimmer) if shimmer is not None else 0.0,
        "hnr":     float(hnr)    if hnr     is not None else 0.0,
    }


def _estimate_speaking_rate(y, sr, intervals) -> dict:
    """
    Estimate speaking rate in syllables per minute using RMS energy peak detection.
    Each syllable nucleus corresponds to a local energy peaks. 
    This is an approximation used in the absence of a full ASR transcript.
    """
    hop        = 512
    rms        = librosa.feature.rms(y=y, hop_length=hop)[0]
    rms_smooth = uniform_filter1d(rms.astype(float), size=5)
    peaks, _   = find_peaks(rms_smooth, distance=4, height=rms_smooth.mean() * 0.5)

    speech_peaks = sum(
        1 for peak in peaks
        if any(s <= peak * hop <= e for s, e in intervals)
    )

    speech_min = (sum(e - s for s, e in intervals) / sr) / 60.0 if len(intervals) > 0 else 0
    rate       = speech_peaks / speech_min if speech_min > 0 else 0.0

    return {
        "syllable_rate_per_min":    round(float(rate), 2),
        "estimated_syllable_count": int(speech_peaks),
    }


def extract_features(audio_path: str) -> dict:
    #Extract all delivery features from an audio file.
    y, sr     = load_audio(audio_path)
    intervals = _detect_speech_intervals(y, sr)

    features = {}
    features.update(_extract_timing_features(y, sr, intervals))
    features.update(_extract_pitch_energy_features(y, sr))
    features.update(_extract_parselmouth_features(y, sr))
    features.update(_estimate_speaking_rate(y, sr, intervals))
    return features


# ===== CLASSIFIER =====
def _classify_with_rf(features: dict) -> str:
    """
    Predict overall delivery level using the trained Random Forest classifier.
    Returns 'Low', 'Medium', or 'High'
    Note: classifier was trained on SpeechOcean762 (short utterances, Mandarin L1 speakers).
    Results are used as supplementary information alongside rule-based scoring.
    """
    feature_vector = np.array([[features[col] for col in FEATURE_COLS]])
    pred_enc       = _clf.predict(feature_vector)[0]
    return _le.inverse_transform([pred_enc])[0]


# ===== RULE-BASED SCORING AND FEEDBACK =====
def _score_fluency(features: dict, thresholds: dict) -> tuple:
    score, feedback  = 0, []
    total_dur        = features["total_duration_sec"]
    pause_count      = features["pause_count"]
    avg_pause        = features["avg_pause_duration_sec"]
    hesitation_ratio = features["hesitation_ratio"]
    t                = thresholds

    duration_minutes  = total_dur / 60.0
    pauses_per_minute = pause_count / duration_minutes if duration_minutes > 0 else 0

    if pauses_per_minute < t["pauses_per_min_few"]:
        score += 1
        feedback.append("Your delivery has very few pauses, which can sound rushed or robotic. "
                        "Natural pauses help listeners follow along.")
    elif pauses_per_minute <= t["pauses_per_min_good"]:
        score += 3
        feedback.append("Your use of pauses is natural and well-paced.")
    elif pauses_per_minute <= t["pauses_per_min_moderate"]:
        score += 2
        feedback.append("Your pauses are noticeable but still within a moderate range.")
    else:
        score += 1
        feedback.append("You pause quite frequently, which may reduce fluency. "
                        "Try to keep your thoughts more connected.")

    if avg_pause == 0.0:
        score += 1
        feedback.append("No distinct pauses were detected. Natural pausing improves clarity and delivery.")
    elif avg_pause <= t["avg_pause_short"]:
        score += 3
        feedback.append("Your pauses are mostly short and natural.")
    elif avg_pause <= t["avg_pause_moderate"]:
        score += 2
        feedback.append("Some of your pauses are slightly long — aim to keep them concise.")
    else:
        score += 1
        feedback.append("Your pauses are often quite long, which may disrupt the flow of your delivery.")

    if hesitation_ratio <= t["hesitation_good"]:
        score += 3
        feedback.append("Your speech flow is smooth and well-timed.")
    elif hesitation_ratio <= t["hesitation_moderate"]:
        score += 2
        feedback.append("There is a moderate amount of silence in your delivery.")
    else:
        score += 1
        feedback.append("A large portion of your delivery contains silence or hesitation. "
                        "Practising with a script or outline may help.")

    return score / 3.0, feedback


def _score_prosody(features: dict) -> tuple:
    score, feedback = 0, []
    pitch_std   = features["pitch_std_hz"]
    pitch_range = features["pitch_range_hz"]
    energy_std  = features["energy_std"]
    hnr         = features.get("hnr", 0.0)
    jitter      = features.get("jitter", 0.0)
    shimmer     = features.get("shimmer", 0.0)

    if pitch_std >= 60:
        score += 3
        feedback.append("Your pitch variation makes your delivery sound expressive and engaging.")
    elif pitch_std >= 35:
        score += 2
        feedback.append("Your pitch variation is moderate — try varying your tone more to emphasise key points.")
    else:
        score += 1
        feedback.append("Your speech sounds quite monotone. Try raising and lowering your pitch "
                        "to make your delivery more engaging.")

    if pitch_range >= 80:
        score += 3
        feedback.append("Your pitch range supports an engaging and varied speaking style.")
    elif pitch_range >= 40:
        score += 2
        feedback.append("Your pitch range is acceptable but could be broader for more impact.")
    else:
        score += 1
        feedback.append("Your pitch range is quite narrow. Try to vary your intonation — "
                        "rise at key moments and drop at conclusions.")

    if energy_std >= 0.03:
        score += 3
        feedback.append("Your loudness variation is good and helps maintain listener engagement.")
    elif energy_std >= 0.01:
        score += 2
        feedback.append("Your loudness variation is moderate. Emphasising important words more "
                        "strongly would improve your delivery.")
    else:
        score += 1
        feedback.append("Your voice is quite flat in volume. Try to speak louder on key points "
                        "and softer in transitions to add expressiveness.")

    if hnr > 0:
        if hnr >= 20:
            feedback.append("Your voice clarity is good — your speech sounds clean and well-projected.")
        elif hnr >= 12:
            feedback.append("Your voice clarity is moderate. Try to project your voice more confidently.")
        else:
            feedback.append("Your voice sounds somewhat breathy or unclear. "
                            "Focus on projecting your voice and speaking from your diaphragm.")

    if jitter > 0.02:
        feedback.append("Some vocal tension was detected. Try to relax your voice — "
                        "deep breaths before speaking can help.")

    if shimmer > 0.05:
        feedback.append("Your vocal stability could improve. "
                        "Consistent breath support will help steady your voice.")

    return score / 3.0, feedback


def _score_to_level(score: float) -> str:
    if score >= 2.67:
        return "High"
    elif score >= 2.0:
        return "Medium"
    else:
        return "Low"


# ===== ASSESSMENT =====
def assess_delivery(features: dict, mode: str = DEFAULT_MODE) -> dict:
    if mode not in MODES:
        mode = DEFAULT_MODE

    thresholds                       = MODES[mode]
    fluency_score, fluency_feedback  = _score_fluency(features, thresholds)
    prosody_score, prosody_feedback  = _score_prosody(features)
    rules_overall                    = (fluency_score + prosody_score) / 2.0
    rules_level                      = _score_to_level(rules_overall)
    rf_level                         = _classify_with_rf(features)

    # Rule-based level is primary (calibrated for presentation-length speech).
    # RF classifier is kept as supplementary: trained on short SpeechOcean762 utterances which introduces a duration bias for longer clips.

    overall_level = rules_level

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
        "overall_score": round(rules_overall, 2),
        "overall_level": overall_level,
        "rf_level":      rf_level,
        "rules_level":   rules_level,
        "mode":          mode,
        "feedback":      feedback,
    }


# ===== PUBLIC FUNCTION =====
def analyze(audio_path: str, mode: str = DEFAULT_MODE) -> dict:
    """Full Pipeline B entry point. Called from main.py."""
    features   = extract_features(audio_path)
    assessment = assess_delivery(features, mode=mode)
    return {
        "features":   features,
        "assessment": assessment,
    }