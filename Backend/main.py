from pathlib import Path
import shutil
import uuid
from typing import Annotated, Literal

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from services.pipeline_a import predict_file
from services.pipeline_b import analyze as pipeline_b_analyze

app = FastAPI(title="FYP Speaking Skills Backend", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

SUPPORTED_AUDIO_FORMATS = [".wav", ".flac", ".mp3", ".ogg", ".m4a", ".mp4"]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(
    file: Annotated[UploadFile, File(...)],
    mode: Annotated[Literal["academic", "public_speaking"], Query()] = "academic",
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_AUDIO_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{ext}'. Accepted: {', '.join(SUPPORTED_AUDIO_FORMATS)}"
        )

    temp_filename = f"{uuid.uuid4()}{ext}"
    temp_path = UPLOAD_DIR / temp_filename

    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        pa_result = predict_file(str(temp_path))

        authenticity = {
            "label": pa_result["pred_label"],
            "bonafide_prob": pa_result["bonafide_probability"],
            "spoof_prob": pa_result["spoof_probability"],
            "confidence": max(
                pa_result["bonafide_probability"],
                pa_result["spoof_probability"]
            ),
        }

        if pa_result["pred_label"] == "spoof":
            return {
                "status": "spoof_detected",
                "authenticity": authenticity,
                "delivery": None,
                "feedback": [
                    "This audio may be AI-generated or synthetic. Please re-record using your real voice."
                ],
                "mode": mode,
            }

        pb_result = pipeline_b_analyze(str(temp_path), mode=mode)

        return {
            "status": "ok",
            "authenticity": authenticity,
            "delivery": {
                "features": pb_result["features"],
                "assessment": pb_result["assessment"],
            },
            "feedback": pb_result["assessment"]["feedback"],
            "mode": mode,
        }

    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"File error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
    finally:
        if temp_path.exists():
            temp_path.unlink()