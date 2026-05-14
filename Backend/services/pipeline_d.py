from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import imageio_ffmpeg
import joblib
import librosa
import numpy as np
import soundfile as sf


# ===== CONFIG =====
TARGET_SR = 16000
_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

_REFERENCE_DIR = Path(__file__).resolve().parent.parent / "references"

REFERENCE_AUDIO = {
    "student_presentations": _REFERENCE_DIR / "student_presentations.wav",
    "climate_change": _REFERENCE_DIR / "climate_change.wav",
    "technology_learning": _REFERENCE_DIR / "technology_learning.wav",
    "thursday_evening": _REFERENCE_DIR / "thursday_evening.wav",
    "effective_communication": _REFERENCE_DIR / "effective_communication.wav",
    "progress_action": _REFERENCE_DIR / "progress_action.wav",
}

# ===== TRAINED PRONUNCIATION MODEL =====
_MODEL_DIR = Path(__file__).resolve().parent.parent / "models"

_PHONE_MODEL_PATH = _MODEL_DIR / "pronunciation_phone_error_rf.pkl"
_PHONE_COLS_PATH = _MODEL_DIR / "pronunciation_phone_error_feature_cols.pkl"
_PHONE_THRESHOLD_PATH = _MODEL_DIR / "pronunciation_phone_error_threshold.pkl"

_phone_model = None
_phone_feature_cols = None
_phone_error_threshold = None


STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "because", "as", "until",
    "while", "of", "at", "by", "for", "with", "about", "against", "between",
    "into", "through", "during", "before", "after", "above", "below", "to",
    "from", "up", "down", "in", "out", "on", "off", "over", "under", "again",
    "further", "then", "once", "here", "there", "when", "where", "why", "how",
    "all", "any", "both", "each", "few", "more", "most", "other", "some",
    "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too",
    "very", "can", "will", "just", "should", "now", "i", "me", "my", "myself",
    "we", "our", "ours", "ourselves", "you", "your", "yours", "yourself",
    "he", "him", "his", "she", "her", "hers", "it", "its", "they", "them",
    "their", "what", "which", "who", "whom", "this", "that", "these", "those",
    "am", "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "having", "do", "does", "did", "doing",
}


# ===== TEXT HELPERS =====
def _tokenize_words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())


def _levenshtein_word_alignment(
    expected_words: list[str],
    heard_words: list[str],
) -> list[dict]:
    """
    Word-level dynamic-programming alignment.

    Operations:
    - match: expected word and heard word are the same
    - substitution: expected word was recognised as a different word
    - missing: expected word was not recognised
    - extra: extra recognised word not present in expected text
    """
    n = len(expected_words)
    m = len(heard_words)

    dp = [[0] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        dp[i][0] = i
        back[i][0] = "missing"

    for j in range(1, m + 1):
        dp[0][j] = j
        back[0][j] = "extra"

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if expected_words[i - 1] == heard_words[j - 1]:
                sub_cost = 0
                sub_op = "match"
            else:
                sub_cost = 1
                sub_op = "substitution"

            candidates = [
                (dp[i - 1][j - 1] + sub_cost, sub_op),
                (dp[i - 1][j] + 1, "missing"),
                (dp[i][j - 1] + 1, "extra"),
            ]

            best_cost, best_op = min(candidates, key=lambda item: item[0])
            dp[i][j] = best_cost
            back[i][j] = best_op

    ops = []
    i, j = n, m

    while i > 0 or j > 0:
        op = back[i][j]

        if op == "match":
            ops.append({
                "type": "match",
                "expected": expected_words[i - 1],
                "heard": heard_words[j - 1],
            })
            i -= 1
            j -= 1

        elif op == "substitution":
            ops.append({
                "type": "substitution",
                "expected": expected_words[i - 1],
                "heard": heard_words[j - 1],
            })
            i -= 1
            j -= 1

        elif op == "missing":
            ops.append({
                "type": "missing",
                "expected": expected_words[i - 1],
                "heard": "",
            })
            i -= 1

        elif op == "extra":
            ops.append({
                "type": "extra",
                "expected": "",
                "heard": heard_words[j - 1],
            })
            j -= 1

        else:
            break

    ops.reverse()
    return ops


def _pronunciation_tip(expected: str, heard: str = "") -> str:
    """
    Conservative rule-based feedback.
    Avoids overclaiming exact phoneme errors.
    """
    word = expected.lower()
    heard = heard.lower()

    if not word:
        return ""

    if word.endswith("s") and heard == word[:-1]:
        return f"Practise the final /s/ sound in '{expected}'."

    if word.endswith("ed") and heard in {word[:-1], word[:-2]}:
        return f"Practise the final past-tense sound in '{expected}'."

    if "th" in word:
        return f"Practise the 'th' sound in '{expected}' with clear tongue placement."

    if word.endswith("ing") and heard.endswith("in"):
        return f"Practise the final /ŋ/ sound in '{expected}'."

    if len(word) >= 7:
        return f"Practise saying '{expected}' slowly, then repeat it at normal speed."

    return f"Practise '{expected}' clearly and avoid rushing the word."


def _word_level_reading_analysis(expected_text: str, transcript: str) -> dict:
    expected_words = _tokenize_words(expected_text)
    heard_words = _tokenize_words(transcript)

    if not expected_words:
        return {
            "word_accuracy": 0.0,
            "word_feedback": [],
            "words_to_practise": [],
            "missing_words": [],
            "substitutions": [],
            "extra_words": [],
            "alignment": [],
        }

    alignment = _levenshtein_word_alignment(expected_words, heard_words)

    matches = sum(1 for item in alignment if item["type"] == "match")

    substitutions = [
        item for item in alignment
        if item["type"] == "substitution" and item["expected"]
    ]

    missing = [
        item for item in alignment
        if item["type"] == "missing" and item["expected"]
    ]

    extra = [
        item for item in alignment
        if item["type"] == "extra" and item["heard"]
    ]

    expected_coverage = matches / max(len(expected_words), 1)
    heard_precision = matches / max(len(heard_words), 1)

    # Coverage checks whether expected words were read.
    # Precision penalises extra or unrelated recognised words.
    word_accuracy = (0.75 * expected_coverage) + (0.25 * heard_precision)

    practice_items = []
    word_feedback = []

    for item in substitutions + missing:
        expected = item.get("expected", "")
        heard = item.get("heard", "")

        # Avoid weak practice items such as "the", "and", "to".
        if expected in STOP_WORDS and len(expected) <= 4:
            continue

        if expected and expected not in practice_items:
            practice_items.append(expected)

        word_feedback.append({
            "expected": expected,
            "heard": heard,
            "type": item["type"],
            "tip": _pronunciation_tip(expected, heard),
        })

        if len(practice_items) >= 8:
            break

    return {
        "word_accuracy": round(float(word_accuracy), 3),
        "expected_coverage": round(float(expected_coverage), 3),
        "heard_precision": round(float(heard_precision), 3),
        "word_feedback": word_feedback[:8],
        "words_to_practise": practice_items[:8],
        "missing_words": [item["expected"] for item in missing[:8]],
        "substitutions": [
            {
                "expected": item["expected"],
                "heard": item["heard"],
            }
            for item in substitutions[:8]
        ],
        "extra_words": [item["heard"] for item in extra[:8]],
        "alignment": alignment[:120],
    }


# ===== AUDIO HELPERS =====
def _convert_to_wav(src: str) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()

    subprocess.run(
        [
            _FFMPEG,
            "-y",
            "-i",
            src,
            "-ar",
            str(TARGET_SR),
            "-ac",
            "1",
            "-f",
            "wav",
            tmp.name,
        ],
        check=True,
        capture_output=True,
    )

    return tmp.name


def _load_audio_16k(path: str) -> np.ndarray:
    """
    Loads audio as mono float32 at 16 kHz.
    Handles compressed formats through ffmpeg.
    """
    ext = Path(path).suffix.lower()
    tmp_path = None

    try:
        if ext in {".mp3", ".m4a", ".mp4", ".ogg", ".flac"}:
            tmp_path = _convert_to_wav(path)
            read_path = tmp_path
        else:
            read_path = path

        y, sr = sf.read(read_path, dtype="float32", always_2d=False)

        if y.ndim > 1:
            y = np.mean(y, axis=1)

        if sr != TARGET_SR:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
            tmp_path = _convert_to_wav(path)
            y, _ = sf.read(tmp_path, dtype="float32", always_2d=False)
            if y.ndim > 1:
                y = np.mean(y, axis=1)

        y = y.astype(np.float32)

        try:
            y_trimmed, _ = librosa.effects.trim(y, top_db=30)
            if len(y_trimmed) > TARGET_SR * 0.5:
                y = y_trimmed
        except Exception:
            pass

        return y

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

def _load_phone_error_model():
    """
    Load the L2-ARCTIC phone-error model.

    The model predicts whether short phone-like acoustic windows are likely
    to contain pronunciation errors.
    """
    global _phone_model, _phone_feature_cols, _phone_error_threshold

    if _phone_model is None:
        if not _PHONE_MODEL_PATH.exists():
            raise FileNotFoundError(f"Phone-error model not found: {_PHONE_MODEL_PATH}")

        if not _PHONE_COLS_PATH.exists():
            raise FileNotFoundError(f"Phone-error feature columns not found: {_PHONE_COLS_PATH}")

        if not _PHONE_THRESHOLD_PATH.exists():
            raise FileNotFoundError(f"Phone-error threshold not found: {_PHONE_THRESHOLD_PATH}")

        _phone_model = joblib.load(_PHONE_MODEL_PATH)
        _phone_feature_cols = joblib.load(_PHONE_COLS_PATH)
        _phone_error_threshold = float(joblib.load(_PHONE_THRESHOLD_PATH))

        print(f"[Pipeline D] Loaded phone-error model from: {_PHONE_MODEL_PATH}")
        print(f"[Pipeline D] Phone-error threshold: {_phone_error_threshold}")

    return _phone_model, _phone_feature_cols, _phone_error_threshold


def _safe_stats(values: np.ndarray, prefix: str) -> dict:
    values = np.asarray(values)

    if values.size == 0:
        return {
            f"{prefix}_mean": 0.0,
            f"{prefix}_std": 0.0,
            f"{prefix}_min": 0.0,
            f"{prefix}_max": 0.0,
        }

    return {
        f"{prefix}_mean": float(np.mean(values)),
        f"{prefix}_std": float(np.std(values)),
        f"{prefix}_min": float(np.min(values)),
        f"{prefix}_max": float(np.max(values)),
    }


def _safe_delta(mfcc: np.ndarray) -> np.ndarray:
    frame_count = mfcc.shape[1]

    if frame_count < 3:
        return np.zeros_like(mfcc)

    width = min(9, frame_count)

    if width % 2 == 0:
        width -= 1

    if width < 3:
        return np.zeros_like(mfcc)

    return librosa.feature.delta(mfcc, width=width, mode="nearest")


def _extract_phone_segment_features(segment: np.ndarray) -> dict:
    """
    Feature extractor must match the PipelineD_v3 training notebook.
    """
    segment = np.asarray(segment, dtype=np.float32)

    if len(segment) < int(0.03 * TARGET_SR):
        return {}

    features = {
        "seg_duration": len(segment) / TARGET_SR,
    }

    rms = librosa.feature.rms(
        y=segment,
        frame_length=512,
        hop_length=128,
    )[0]

    zcr = librosa.feature.zero_crossing_rate(
        segment,
        frame_length=512,
        hop_length=128,
    )[0]

    features.update(_safe_stats(rms, "rms"))
    features.update(_safe_stats(zcr, "zcr"))

    mfcc = librosa.feature.mfcc(
        y=segment,
        sr=TARGET_SR,
        n_mfcc=13,
        n_fft=512,
        hop_length=128,
    )

    delta = _safe_delta(mfcc)

    for i in range(mfcc.shape[0]):
        features[f"mfcc_{i + 1}_mean"] = float(np.mean(mfcc[i]))
        features[f"mfcc_{i + 1}_std"] = float(np.std(mfcc[i]))

    for i in range(delta.shape[0]):
        features[f"delta_{i + 1}_mean"] = float(np.mean(delta[i]))
        features[f"delta_{i + 1}_std"] = float(np.std(delta[i]))

    centroid = librosa.feature.spectral_centroid(
        y=segment,
        sr=TARGET_SR,
        n_fft=512,
        hop_length=128,
    )[0]

    bandwidth = librosa.feature.spectral_bandwidth(
        y=segment,
        sr=TARGET_SR,
        n_fft=512,
        hop_length=128,
    )[0]

    features.update(_safe_stats(centroid, "centroid"))
    features.update(_safe_stats(bandwidth, "bandwidth"))

    return features


def _chunk_audio_phone_like(
    y: np.ndarray,
    chunk_ms: int = 80,
    hop_ms: int = 40,
) -> list[np.ndarray]:
    """
    Approximate phone-like windows for runtime inference.
    This is used because app recordings do not have forced-aligned phone boundaries.
    """
    chunk_len = int(TARGET_SR * chunk_ms / 1000)
    hop_len = int(TARGET_SR * hop_ms / 1000)

    if len(y) < chunk_len:
        return [y]

    chunks = []

    for start in range(0, len(y) - chunk_len + 1, hop_len):
        end = start + chunk_len
        chunk = y[start:end]

        # Skip very quiet chunks.
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        if rms < 0.005:
            continue

        chunks.append(chunk)

    return chunks


def _pronunciation_level_from_error_ratio(error_ratio: float) -> str:
    """
    Runtime thresholds calibrated using local read-aloud tests and held-out L2-ARCTIC samples.
    """
    if error_ratio <= 0.09:
        return "Good"
    if error_ratio <= 0.12:
        return "Moderate"
    return "Needs improvement"


def _pronunciation_note(level: str, error_ratio: float) -> str:
    percent = error_ratio * 100

    if level == "Good":
        return f"The trained pronunciation model detected a low pronunciation-error pattern ({percent:.1f}% estimated error-like segments)."
    if level == "Moderate":
        return f"The trained pronunciation model detected some pronunciation-error patterns ({percent:.1f}% estimated error-like segments)."
    return f"The trained pronunciation model detected frequent pronunciation-error patterns ({percent:.1f}% estimated error-like segments)."


def _predict_pronunciation_quality(audio_path: str) -> dict:
    """
    Use the trained L2-ARCTIC phone-error model to estimate pronunciation quality.
    """
    model, feature_cols, segment_threshold = _load_phone_error_model()

    y = _load_audio_16k(audio_path)
    chunks = _chunk_audio_phone_like(y)

    rows = []

    for chunk in chunks:
        features = _extract_phone_segment_features(chunk)
        if features:
            rows.append(features)

    if not rows:
        return {
            "available": False,
            "model": "l2arctic_phone_error_rf",
            "level": "N/A",
            "estimated_error_ratio": None,
            "avg_error_probability": None,
            "segment_count": 0,
            "segment_error_threshold": segment_threshold,
            "note": "No usable speech-like segments were found for pronunciation scoring.",
        }

    x = np.array(
        [[row.get(col, 0.0) for col in feature_cols] for row in rows],
        dtype=np.float32,
    )

    if hasattr(model, "predict_proba"):
        error_probs = model.predict_proba(x)[:, 1]
    else:
        preds = model.predict(x)
        error_probs = preds.astype(np.float32)

    predicted_errors = error_probs >= segment_threshold

    estimated_error_ratio = float(np.mean(predicted_errors))
    avg_error_probability = float(np.mean(error_probs))
    level = _pronunciation_level_from_error_ratio(estimated_error_ratio)

    return {
        "available": True,
        "model": "l2arctic_phone_error_rf",
        "level": level,
        "estimated_error_ratio": round(estimated_error_ratio, 3),
        "avg_error_probability": round(avg_error_probability, 3),
        "segment_count": len(rows),
        "segment_error_threshold": segment_threshold,
        "p50_error_probability": round(float(np.percentile(error_probs, 50)), 3),
        "p90_error_probability": round(float(np.percentile(error_probs, 90)), 3),
        "note": _pronunciation_note(level, estimated_error_ratio),
    }


def _pronunciation_score_from_error_ratio(error_ratio: Optional[float]) -> float:
    """
    Converts estimated error ratio into a 0..1 score.
    0.20+ is treated as poor because runtime ratios above this are already high.
    """
    if not isinstance(error_ratio, (int, float)):
        return 0.5

    return 1.0 - min(float(error_ratio) / 0.20, 1.0)


def _overall_read_aloud_level(score: float) -> tuple[str, str]:
    if score >= 0.85:
        return "Good", "You read the passage accurately with clear pronunciation."
    if score >= 0.65:
        return "Moderate", "Your reading was partly accurate, with some pronunciation or word-recognition issues."
    return "Needs improvement", "Several expected words or pronunciation patterns need more practice."

def _resolve_reference_audio_path(passage_id: Optional[str]) -> Optional[str]:
    if not passage_id:
        return None

    path = REFERENCE_AUDIO.get(passage_id)

    if path is None:
        return None

    return str(path)

# === legacy MFCC-DTW similarity for acoustic comparison ===
def _mfcc_dtw_similarity(user_audio_path: str, reference_audio_path: str) -> dict:
    """
    MFCC + DTW acoustic similarity.

    This does not use a pretrained pronunciation model or external API.
    It compares the user's recording to a local human reference recording.
    """
    if not reference_audio_path or not os.path.exists(reference_audio_path):
        return {
            "available": False,
            "similarity": None,
            "distance": None,
            "note": "Reference audio was not found for this passage.",
        }

    try:
        user_y = _load_audio_16k(user_audio_path)
        ref_y = _load_audio_16k(reference_audio_path)

        if len(user_y) < TARGET_SR * 0.5 or len(ref_y) < TARGET_SR * 0.5:
            return {
                "available": False,
                "similarity": None,
                "distance": None,
                "note": "Audio was too short for acoustic comparison.",
            }

        user_mfcc = librosa.feature.mfcc(
            y=user_y,
            sr=TARGET_SR,
            n_mfcc=20,
            n_fft=1024,
            hop_length=256,
        )

        ref_mfcc = librosa.feature.mfcc(
            y=ref_y,
            sr=TARGET_SR,
            n_mfcc=20,
            n_fft=1024,
            hop_length=256,
        )

        def normalise_mfcc(mfcc: np.ndarray) -> np.ndarray:
            mean = mfcc.mean(axis=1, keepdims=True)
            std = mfcc.std(axis=1, keepdims=True) + 1e-6
            return (mfcc - mean) / std

        user_mfcc = normalise_mfcc(user_mfcc)
        ref_mfcc = normalise_mfcc(ref_mfcc)

        D, wp = librosa.sequence.dtw(
            X=ref_mfcc,
            Y=user_mfcc,
            metric="cosine",
        )

        avg_distance = float(D[-1, -1] / max(len(wp), 1))

        # Smoothly maps lower distance to higher similarity.
        similarity = float(np.exp(-2.0 * avg_distance))
        similarity = max(0.0, min(1.0, similarity))

        return {
            "available": True,
            "similarity": round(similarity, 3),
            "distance": round(avg_distance, 4),
            "note": "Acoustic similarity was computed using MFCC-DTW against a human reference recording.",
        }

    except Exception as exc:
        return {
            "available": False,
            "similarity": None,
            "distance": None,
            "note": f"Acoustic comparison failed: {exc}",
        }


def _score_to_level(score: float) -> tuple[str, str]:
    if score >= 0.85:
        return "Good", "You read most of the passage clearly and accurately."
    if score >= 0.65:
        return "Moderate", "Most of the passage was recognisable, but some words may need clearer pronunciation."
    return "Needs improvement", "Several words were not recognised clearly. Try reading more slowly and pronouncing each word carefully."


# ===== PUBLIC FUNCTION =====
def analyze_read_aloud(
    audio_path: str,
    transcript: str,
    expected_text: Optional[str],
    passage_id: Optional[str] = None,
) -> dict:
    """
    Pipeline D: read-aloud pronunciation comparison.

    Combines:
    1. Reading accuracy from expected-text vs ASR transcript alignment.
    2. Pronunciation quality from trained L2-ARCTIC phone-error model.

    MFCC-DTW reference similarity is kept only as experimental code and is not
    used in the final score anymore.
    """
    if not expected_text:
        return {
            "available": False,
            "similarity": None,
            "word_accuracy": None,
            "pronunciation_model": {
                "available": False,
                "level": "N/A",
            },
            "missing_keywords": [],
            "words_to_practise": [],
            "word_feedback": [],
            "note": "No expected passage was provided for comparison.",
        }

    expected_words = _tokenize_words(expected_text)

    if not expected_words:
        return {
            "available": False,
            "similarity": None,
            "word_accuracy": None,
            "pronunciation_model": {
                "available": False,
                "level": "N/A",
            },
            "missing_keywords": [],
            "words_to_practise": [],
            "word_feedback": [],
            "note": "Expected passage was empty.",
        }

    # 1. Text/ reading accuracy.
    word_result = _word_level_reading_analysis(expected_text, transcript)
    word_accuracy = float(word_result["word_accuracy"])

    # 2. Trained pronunciation model.
    try:
        pronunciation_model = _predict_pronunciation_quality(audio_path)
    except Exception as exc:
        pronunciation_model = {
            "available": False,
            "model": "l2arctic_phone_error_rf",
            "level": "N/A",
            "estimated_error_ratio": None,
            "avg_error_probability": None,
            "segment_count": 0,
            "note": f"Pronunciation model was unavailable: {exc}",
        }

    error_ratio = pronunciation_model.get("estimated_error_ratio")
    pronunciation_score = _pronunciation_score_from_error_ratio(error_ratio)

    # 3. Combined read-aloud score.
    # Reading accuracy is primary; pronunciation quality is supporting.
    overall_score = (0.60 * word_accuracy) + (0.40 * pronunciation_score)
    overall_score = max(0.0, min(1.0, float(overall_score)))

    level, overall_note = _overall_read_aloud_level(overall_score)

    words_to_practise = word_result["words_to_practise"]

    missing_count = len(word_result.get("missing_words", []))
    substitution_count = len(word_result.get("substitutions", []))
    extra_count = len(word_result.get("extra_words", []))

    detail_notes = []

    if missing_count:
        detail_notes.append(f"{missing_count} expected word(s) were not clearly detected.")

    if substitution_count:
        detail_notes.append(f"{substitution_count} word difference(s) were detected.")

    if extra_count:
        detail_notes.append(f"{extra_count} extra word(s) were detected outside the expected passage.")

    if not detail_notes:
        detail_notes.append("No major word-level differences were detected.")

    pronunciation_note = pronunciation_model.get("note", "")

    return {
        "available": True,

        # Backward-compatible overall field used by current UI.
        "similarity": round(overall_score, 3),
        "level": level,
        "note": " ".join([overall_note, *detail_notes, pronunciation_note]).strip(),

        # Separate scores.
        "overall_score": round(overall_score, 3),
        "read_aloud_score": round(overall_score, 3),
        "word_accuracy": round(word_accuracy, 3),
        "reading_accuracy": round(word_accuracy, 3),
        "pronunciation_score": round(pronunciation_score, 3),
        "pronunciation_model": pronunciation_model,

        # Word-level feedback.
        "missing_keywords": words_to_practise,
        "words_to_practise": words_to_practise,
        "word_feedback": word_result["word_feedback"],
        "missing_words": word_result["missing_words"],
        "substitutions": word_result["substitutions"],
        "extra_words": word_result["extra_words"],
        "expected_coverage": word_result.get("expected_coverage"),
        "heard_precision": word_result.get("heard_precision"),

        # Old acoustic fields retained but disabled in final scoring.
        "acoustic_similarity": None,
        "acoustic_comparison": {
            "available": False,
            "similarity": None,
            "note": "Reference-audio MFCC-DTW comparison is not used in the final score.",
        },

        "method": "word_alignment_plus_l2arctic_phone_error_model",
        "uses_pretrained_pronunciation_model": False,
        "uses_trained_l2arctic_model": True,
        "score_weights": {
            "reading_accuracy": 0.60,
            "pronunciation_quality": 0.40,
        },
    }