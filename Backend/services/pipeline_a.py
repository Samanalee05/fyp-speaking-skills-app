import os
import imageio_ffmpeg
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchaudio

# ===== CONFIG =====
SAMPLE_RATE = 16000
CLIP_SECONDS = 4.0
TARGET_LEN   = int(SAMPLE_RATE * CLIP_SECONDS)
N_MELS       = 64
N_FFT        = 1024
HOP_LENGTH   = 160
WIN_LENGTH   = 400
F_MIN        = 20
F_MAX        = 7600

DEVICE     = torch.device("cuda" if torch.cuda.is_available() else "cpu")
MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "best_spoof_cnn_v4.pth"

_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


# ===== MODEL ARCHITECTURE =====
class SpoofCNN(nn.Module):
    def __init__(self, n_mels: int = 64):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, padding=1),
            nn.BatchNorm2d(16),
            nn.LeakyReLU(0.1),
            nn.MaxPool2d(2),
            nn.Dropout(0.2),

            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.LeakyReLU(0.1),
            nn.MaxPool2d(2),
            nn.Dropout(0.3),

            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.LeakyReLU(0.1),
            nn.MaxPool2d(2),
            nn.Dropout(0.4),
        )
        self.gap = nn.AdaptiveAvgPool2d((1, 1))
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64, 64),
            nn.LeakyReLU(0.1),
            nn.Dropout(0.4),
            nn.Linear(64, 2),
        )

    def forward(self, x):
        x = self.features(x)
        x = self.gap(x)
        return self.classifier(x)


# ===== FEATURE EXTRACTOR =====
class LogMelExtractor(nn.Module):
    def __init__(self):
        super().__init__()
        self.melspec = torchaudio.transforms.MelSpectrogram(
            sample_rate=SAMPLE_RATE,
            n_fft=N_FFT,
            win_length=WIN_LENGTH,
            hop_length=HOP_LENGTH,
            f_min=F_MIN,
            f_max=F_MAX,
            n_mels=N_MELS,
            power=2.0,
        )
        self.amp_to_db = torchaudio.transforms.AmplitudeToDB(stype="power", top_db=80)

    def forward(self, wav: torch.Tensor):
        mel    = self.melspec(wav)
        logmel = self.amp_to_db(mel)
        mean   = logmel.mean()
        std    = logmel.std().clamp_min(1e-6)
        return (logmel - mean) / std


# ===== AUDIO LOADING =====
def _convert_to_wav(src: str) -> str:
    """
    Convert a compressed audio file (M4A, MP3, MP4) to a temporary WAV file
    using ffmpeg. Returns the path to the temp WAV file
    Caller is responsible for deleting the temp file.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    subprocess.run(
        [_FFMPEG, "-y", "-i", src,
         "-ar", str(SAMPLE_RATE), "-ac", "1", "-f", "wav", tmp.name],
        check=True,
        capture_output=True,
    )
    return tmp.name


def _load_audio(path: Path) -> torch.Tensor:
    """
    Load audio from any supported format and return a (1, T) float32 tensor
    resampled to SAMPLE_RATE. Compressed formats (M4A, MP3, MP4) are
    converted via ffmpeg before loading.
    """
    ext      = path.suffix.lower()
    tmp_path = None

    try:
        if ext in {".m4a", ".mp3", ".mp4"} and _FFMPEG and os.path.exists(_FFMPEG):
            tmp_path = _convert_to_wav(str(path))
            read_path = tmp_path
        else:
            read_path = str(path)

        wav_np, sr = sf.read(read_path, dtype="float32", always_2d=True)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    wav = torch.from_numpy(wav_np).transpose(0, 1)  # (channels, T)
    if wav.shape[0] > 1:
        wav = wav.mean(dim=0, keepdim=True)          # force mono
    if sr != SAMPLE_RATE:
        wav = torchaudio.functional.resample(wav, sr, SAMPLE_RATE)
    return wav


def _fix_length(wav: torch.Tensor, target_len: int) -> torch.Tensor:
    t = wav.shape[-1]
    if t > target_len:
        return wav[..., :target_len]
    if t < target_len:
        return F.pad(wav, (0, target_len - t))
    return wav


# ===== LOAD MODEL =====
print(f"[Pipeline A] Loading model from: {MODEL_PATH}")
print(f"[Pipeline A] Using device: {DEVICE}")

_model     = SpoofCNN(N_MELS).to(DEVICE)
_extractor = LogMelExtractor().to(DEVICE)

if not MODEL_PATH.exists():
    raise FileNotFoundError(f"Model file not found: {MODEL_PATH}")

_ckpt = torch.load(MODEL_PATH, map_location=DEVICE, weights_only=True)
_model.load_state_dict(_ckpt["model_state"])
_model.eval()

print("[Pipeline A] Model loaded successfully.")


# ===== PUBLIC FUNCTION =====
@torch.no_grad()
def predict_file(path_to_audio: str) -> dict:
    path = Path(path_to_audio)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    wav  = _load_audio(path)
    wav  = _fix_length(wav, TARGET_LEN)
    feat = _extractor(wav.to(DEVICE))
    x    = feat.unsqueeze(0)

    logits = _model(x)
    probs  = torch.softmax(logits, dim=1)[0].cpu().numpy()

    return {
        "pred_label":         "spoof" if int(np.argmax(probs)) == 1 else "bonafide",
        "spoof_probability":  float(probs[1]),
        "bonafide_probability": float(probs[0]),
    }