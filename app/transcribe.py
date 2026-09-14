"""Private temporary audio uploads and CPU-local Whisper transcription."""
import asyncio
from pathlib import Path
from uuid import uuid4

from app.config import settings


class AudioError(Exception):
    pass


def upload_path(upload_id: str) -> Path:
    root = Path(settings.uploads_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root / upload_id


def create_upload(filename: str, size_bytes: int) -> dict:
    if size_bytes < 1 or size_bytes > 25 * 1024 * 1024:
        raise AudioError("Audio uploads must be between 1 byte and 25 MB")
    suffix = Path(filename).suffix.lower()
    if not suffix or len(suffix) > 10:
        raise AudioError("filename must include a normal file extension")
    upload_id = f"local_audio_{uuid4().hex}{suffix}"
    return {"uploadId": upload_id, "uploadUrl": f"/v1/transcribe/uploads/{upload_id}", "maxSizeBytes": 25 * 1024 * 1024}


def write_upload(upload_id: str, content: bytes) -> None:
    if not upload_id.startswith("local_audio_") or len(content) > 25 * 1024 * 1024:
        raise AudioError("Invalid or oversized upload")
    upload_path(upload_id).write_bytes(content)


def resolve_whisper_runtime() -> tuple[str, str]:
    device = settings.transcription_device.strip().lower()
    if device not in {"cpu", "cuda", "auto"}:
        raise AudioError("N3XUS_API_TRANSCRIPTION_DEVICE must be cpu, cuda, or auto")
    if device == "auto":
        try:
            import ctranslate2

            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception as error:
            raise AudioError("Could not detect a CUDA device for auto transcription") from error
    compute_type = settings.transcription_compute_type
    if compute_type:
        compute_type = compute_type.strip()
    else:
        compute_type = "float16" if device == "cuda" else "int8"
    if device == "cuda":
        try:
            import ctranslate2

            if ctranslate2.get_cuda_device_count() < 1:
                raise AudioError("CUDA transcription requested but no GPU is available")
        except AudioError:
            raise
        except Exception as error:
            raise AudioError("CUDA transcription requested but GPU detection failed") from error
    return device, compute_type


def create_whisper_model(model_name: str, device: str, compute_type: str):
    try:
        from faster_whisper import WhisperModel
    except ImportError as error:
        raise AudioError("Install faster-whisper to enable local transcription") from error
    return WhisperModel(model_name, device=device, compute_type=compute_type)


def transcribe_file(path: Path) -> dict:
    if not path.is_file():
        raise AudioError("The audio file is missing")
    return _transcribe(path)


def _transcribe(path: Path) -> dict:
    device, compute_type = resolve_whisper_runtime()
    try:
        model = create_whisper_model(settings.transcription_model, device, compute_type)
        segments, info = model.transcribe(str(path), vad_filter=True)
        rows = [{"text": segment.text.strip(), "start": segment.start, "end": segment.end} for segment in segments]
    except AudioError:
        raise
    except Exception as error:
        message = "Audio could not be transcribed"
        if device == "cuda":
            message = "CUDA transcription failed; verify drivers, ctranslate2 CUDA build, and compute type"
        raise AudioError(message) from error
    return {"text": " ".join(row["text"] for row in rows), "language": info.language, "segments": rows}


async def transcribe(upload_id: str) -> dict:
    path = upload_path(upload_id)
    if not path.is_file():
        raise AudioError("The audio upload is missing or expired")
    try:
        return await asyncio.to_thread(_transcribe, path)
    finally:
        path.unlink(missing_ok=True)
