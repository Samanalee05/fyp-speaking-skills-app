from __future__ import annotations

import os
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Optional
from difflib import SequenceMatcher

import imageio_ffmpeg
import numpy as np
import soundfile as sf
import whisper


TARGET_SR = 16000
_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

_MODEL_NAME = "tiny.en"
_model = None


# Common English stop words.
# Used only as a rough lexical-density indicator, not as "bad words".
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


FILLER_PATTERNS = {
    "um": r"\bum+\b",
    "uh": r"\buh+\b",
    "erm": r"\berm+\b|\ber+\b",
    "like": r"\blike\b",
    "you know": r"\byou know\b",
    "actually": r"\bactually\b",
    "basically": r"\bbasically\b",
    "so": r"\bso\b",
}


CONNECTORS = {
    "and then",
    "so",
    "because",
    "like",
}


def _get_model():
    """Load Whisper model lazily so backend startup does not become too slow."""
    global _model
    if _model is None:
        print(f"[Pipeline C] Loading Whisper model: {_MODEL_NAME}")
        _model = whisper.load_model(_MODEL_NAME)
        print("[Pipeline C] Whisper model loaded successfully.")
    return _model


def _convert_to_wav(src: str) -> str:
    """
    Convert input audio to 16 kHz mono WAV using ffmpeg.
    Returns a temporary wav path. Caller deletes it.
    """
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


def _load_audio_for_whisper(path: str) -> np.ndarray:
    """
    Convert audio to wav, then load as float32 numpy array at 16 kHz.
    Whisper accepts numpy audio directly, avoiding dependency on system ffmpeg.
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

        # If file is not 16 kHz and not converted, use ffmpeg conversion.
        if sr != TARGET_SR:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
            tmp_path = _convert_to_wav(path)
            y, _ = sf.read(tmp_path, dtype="float32", always_2d=False)
            if y.ndim > 1:
                y = np.mean(y, axis=1)

        return y.astype(np.float32)

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def _normalise_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _tokenize_words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())


def transcribe_audio(audio_path: str) -> dict:
    """
    Transcribe audio using local Whisper.
    Returns transcript and rough ASR confidence indicators.
    """
    model = _get_model()
    audio = _load_audio_for_whisper(audio_path)

    result = model.transcribe(
        audio,
        language="en",
        fp16=False,
        verbose=False,
    )

    transcript = (result.get("text") or "").strip()
    segments = result.get("segments") or []

    avg_logprob_values = [
        seg.get("avg_logprob")
        for seg in segments
        if isinstance(seg.get("avg_logprob"), (int, float))
    ]

    avg_logprob = (
        float(np.mean(avg_logprob_values))
        if avg_logprob_values
        else None
    )

    return {
        "transcript": transcript,
        "language": result.get("language", "en"),
        "avg_logprob": avg_logprob,
    }


def detect_filler_words(transcript: str) -> dict:
    text = _normalise_text(transcript)
    words = _tokenize_words(text)
    word_count = max(len(words), 1)

    items = {}
    total = 0

    for label, pattern in FILLER_PATTERNS.items():
        count = len(re.findall(pattern, text))
        if count > 0:
            items[label] = count
            total += count

    per_100_words = round((total / word_count) * 100, 2)

    if per_100_words <= 2:
        level = "Good"
    elif per_100_words <= 6:
        level = "Moderate"
    else:
        level = "Needs improvement"

    return {
        "total": total,
        "items": items,
        "per_100_words": per_100_words,
        "level": level,
    }


def analyse_word_use(transcript: str) -> dict:
    words = _tokenize_words(transcript)
    word_count = len(words)

    if word_count == 0:
        return {
            "word_count": 0,
            "stop_word_ratio": 0.0,
            "lexical_density": 0.0,
            "lexical_density_level": "N/A",
            "repeated_words": [],
        }

    stop_count = sum(1 for w in words if w in STOP_WORDS)
    content_count = word_count - stop_count

    stop_word_ratio = stop_count / word_count
    lexical_density = content_count / word_count

    counts = Counter(words)
    repeated_words = [
        word for word, count in counts.most_common()
        if count >= 4 and word not in STOP_WORDS
    ][:5]

    if lexical_density >= 0.55:
        level = "Rich"
    elif lexical_density >= 0.40:
        level = "Moderate"
    else:
        level = "Limited"

    return {
        "word_count": word_count,
        "stop_word_ratio": round(float(stop_word_ratio), 3),
        "lexical_density": round(float(lexical_density), 3),
        "lexical_density_level": level,
        "repeated_words": repeated_words,
    }


def analyse_grammar_basic(transcript: str) -> dict:
    """
    Basic rule-based grammar indicators.
    This is not full grammar correction.
    """
    text = _normalise_text(transcript)
    words = _tokenize_words(text)
    notes = []

    # Repeated adjacent words: "I I", "the the"
    repeated_adjacent = []
    for i in range(1, len(words)):
        if words[i] == words[i - 1]:
            repeated_adjacent.append(words[i])

    if repeated_adjacent:
        notes.append("Repeated adjacent words were detected.")

    # Very long transcript with few sentence boundaries.
    sentence_like_parts = re.split(r"[.!?]+", transcript)
    sentence_like_parts = [s.strip() for s in sentence_like_parts if s.strip()]

    if len(words) >= 80 and len(sentence_like_parts) <= 1:
        notes.append("The response may contain long run-on speech with limited sentence boundaries.")

    # Very short fragments.
    if 0 < len(words) < 20:
        notes.append("The response is quite short, which may limit language assessment.")

    # Repeated connectors.
    connector_counts = {}
    for connector in CONNECTORS:
        count = len(re.findall(rf"\b{re.escape(connector)}\b", text))
        if count >= 4:
            connector_counts[connector] = count

    if connector_counts:
        notes.append("Some connectors appear frequently; try using a wider range of linking words.")

    return {
        "issue_count": len(notes),
        "notes": notes,
        "repeated_adjacent_words": sorted(set(repeated_adjacent))[:5],
        "connector_repetition": connector_counts,
    }

def compare_expected_text(transcript: str, expected_text: Optional[str]) -> dict:
    """
    Compare ASR transcript against expected read-aloud passage.
    This is a pronunciation/articulation proxy, not phoneme-level scoring.
    """
    if not expected_text:
        return {
            "available": False,
            "similarity": None,
            "missing_keywords": [],
            "note": "No expected passage was provided for comparison.",
        }

    transcript_words = _tokenize_words(transcript)
    expected_words = _tokenize_words(expected_text)

    if not expected_words:
        return {
            "available": False,
            "similarity": None,
            "missing_keywords": [],
            "note": "Expected passage was empty.",
        }

    transcript_text = " ".join(transcript_words)
    expected_text_norm = " ".join(expected_words)

    similarity = SequenceMatcher(
        None,
        expected_text_norm,
        transcript_text,
    ).ratio()

    transcript_set = set(transcript_words)

    # Only check meaningful content words, not every "the/is/and".
    expected_keywords = [
        word for word in expected_words
        if word not in STOP_WORDS and len(word) > 4
    ]

    missing_keywords = []
    for word in expected_keywords:
        if word not in transcript_set and word not in missing_keywords:
            missing_keywords.append(word)

    missing_keywords = missing_keywords[:8]

    if similarity >= 0.85:
        level = "Good"
        note = "The read-aloud transcript closely matched the expected passage."
    elif similarity >= 0.65:
        level = "Moderate"
        note = "The transcript mostly matched the passage, but some words may need clearer articulation."
    else:
        level = "Needs improvement"
        note = "The transcript differed noticeably from the expected passage. Practise reading more clearly and steadily."

    return {
        "available": True,
        "similarity": round(float(similarity), 3),
        "level": level,
        "missing_keywords": missing_keywords,
        "note": note,
    }

def analyse_pronunciation_proxy(
    transcript: str,
    acoustic_features: Optional[dict] = None,
    expected_text: Optional[str] = None,
) -> dict:
    """
    Estimate pronunciation/clarity indicators.
    This is NOT phoneme-level pronunciation scoring.
    It uses acoustic clarity features from Pipeline B and ASR recognisability.
    """
    acoustic_features = acoustic_features or {}

    read_aloud_comparison = compare_expected_text(transcript, expected_text)

    hnr = float(acoustic_features.get("hnr", 0.0) or 0.0)
    jitter = float(acoustic_features.get("jitter", 0.0) or 0.0)
    shimmer = float(acoustic_features.get("shimmer", 0.0) or 0.0)
    speaking_rate = float(acoustic_features.get("syllable_rate_per_min", 0.0) or 0.0)

    score = 0
    notes = []

    # HNR: higher generally indicates clearer voiced speech.
    if hnr >= 20:
        score += 2
    elif hnr >= 12:
        score += 1
        notes.append("Voice clarity was moderate.")
    else:
        notes.append("Voice clarity may be reduced or breathy.")

    # Jitter/shimmer: high values suggest vocal instability.
    if jitter <= 0.02:
        score += 1
    else:
        notes.append("Some vocal instability was detected.")

    if shimmer <= 0.06:
        score += 1
    else:
        notes.append("Amplitude variation suggests unstable projection.")

    if 90 <= speaking_rate <= 190:
        score += 1
    else:
        notes.append("Speaking rate may affect intelligibility.")

    if len(_tokenize_words(transcript)) < 10:
        notes.append("Transcript was very short, so pronunciation clarity is uncertain.")

    if score >= 4:
        level = "Good"
        main_note = "Speech was generally clear and intelligible."
    elif score >= 2:
        level = "Moderate"
        main_note = "Speech was mostly recognisable, but some words may need clearer articulation."
    else:
        level = "Needs improvement"
        main_note = "Speech clarity may need improvement. Try speaking more steadily and clearly."

    if main_note not in notes:
        notes.insert(0, main_note)

    if read_aloud_comparison["available"]:
        # If read-aloud comparsion is available, include it as stronger evidenc
        comparison_level = read_aloud_comparison["level"]
        comparison_note = read_aloud_comparison["note"]

        # Keep acoustic clarity, but foreground read-aloud match.
        main_note = comparison_note
        level = comparison_level
        if comparison_note not in notes:
            notes.insert(0, comparison_note)

    return {
        "clarity_level": level,
        "note": main_note,
        "details": notes,
        "read_aloud_comparison": read_aloud_comparison,
    }


def _generate_transcript_feedback(
    filler_words: dict,
    word_use: dict,
    grammar: dict,
    pronunciation: dict,
) -> list[str]:
    feedback = []

    filler_total = filler_words.get("total", 0)
    filler_level = filler_words.get("level", "Good")

    if filler_total == 0:
        feedback.append("No major filler word use was detected.")
    elif filler_level == "Good":
        feedback.append("Only a small number of filler words were detected.")
    elif filler_level == "Moderate":
        feedback.append("Some filler words were detected. Try pausing briefly instead of using fillers.")
    else:
        feedback.append("Frequent filler words were detected. Practise planning key points before speaking.")

    lexical_level = word_use.get("lexical_density_level", "N/A")
    if lexical_level == "Limited":
        feedback.append("Your response may rely on simple or repeated wording. Try adding more specific vocabulary.")
    elif lexical_level == "Moderate":
        feedback.append("Your vocabulary use is acceptable, with room for more variety.")
    elif lexical_level == "Rich":
        feedback.append("Your response shows a good balance of content words.")

    if grammar.get("issue_count", 0) > 0:
        feedback.extend(grammar.get("notes", [])[:2])
    else:
        feedback.append("No major transcript-based grammar patterns were flagged.")

    feedback.append(pronunciation.get("note", ""))

    return [f for f in feedback if f]


def analyze(
    audio_path: str,
    acoustic_features: Optional[dict] = None,
    expected_text: Optional[str] = None,
) -> dict:
    """
    Full Pipeline C analysis.
    expected_text is reserved for future read-aloud/prompt comparison.
    """
    asr = transcribe_audio(audio_path)
    transcript = asr["transcript"]

    filler_words = detect_filler_words(transcript)
    word_use = analyse_word_use(transcript)
    grammar = analyse_grammar_basic(transcript)
    pronunciation = analyse_pronunciation_proxy(
        transcript,
        acoustic_features=acoustic_features,
        expected_text=expected_text,
    )

    feedback = _generate_transcript_feedback(
        filler_words=filler_words,
        word_use=word_use,
        grammar=grammar,
        pronunciation=pronunciation,
    )

    return {
        "transcript": transcript,
        "asr": {
            "language": asr.get("language", "en"),
            "avg_logprob": asr.get("avg_logprob"),
        },
        "filler_words": filler_words,
        "word_use": word_use,
        "grammar": grammar,
        "pronunciation": pronunciation,
        "feedback": feedback,
    }