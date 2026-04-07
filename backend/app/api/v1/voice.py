"""
Voice endpoints: Speech-to-Text (transcription) and Text-to-Speech (synthesis).

Endpoints:
  POST /voice/transcribe   — upload audio file → returns transcript text
  POST /voice/synthesize   — send text → returns audio/mpeg stream

Both rely on OpenAI's Whisper (STT) and TTS APIs.  A Gemini key also works
for the synthesis path once Google exposes a compatible TTS endpoint.

Config (backend/.env):
  VOICE_ENABLED=true          — master switch (default: true when OPENAI_API_KEY is set)
  VOICE_STT_MODEL=whisper-1   — transcription model
  VOICE_TTS_MODEL=tts-1       — synthesis model (tts-1 or tts-1-hd)
  VOICE_TTS_VOICE=alloy       — alloy | echo | fable | onyx | nova | shimmer

Max audio file size for transcription: 25 MB (OpenAI limit).
Supported formats: mp3, mp4, mpeg, mpga, m4a, wav, webm.
"""

import io

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.exceptions import AIProviderError, BadRequestError
from app.models.user import User

router = APIRouter(prefix="/voice", tags=["voice"])

_ALLOWED_AUDIO_TYPES = {
    "audio/mpeg", "audio/mp4", "audio/wav", "audio/webm",
    "audio/ogg", "audio/x-m4a", "audio/mp3", "audio/x-wav",
    "video/mp4", "video/webm",  # browsers often report video/webm for MediaRecorder output
}
_MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB — OpenAI hard limit


def _require_voice() -> None:
    """Guard: voice requires at least OpenAI key configured."""
    if not settings.has_openai:
        raise AIProviderError(
            "Voice features require OPENAI_API_KEY in backend/.env. "
            "Whisper and TTS are OpenAI services."
        )


@router.post(
    "/transcribe",
    summary="Transcribe audio to text (Speech-to-Text)",
    status_code=status.HTTP_200_OK,
)
async def transcribe(
    audio: UploadFile = File(..., description="Audio file (mp3/wav/webm/m4a, max 25 MB)"),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Transcribes uploaded audio using OpenAI Whisper.

    Returns:
      {text: str, language: str | null, duration: float | null}

    The frontend sends the raw bytes recorded by the browser's MediaRecorder API
    (usually audio/webm;codecs=opus). Whisper handles this natively.
    """
    _require_voice()

    # Validate content-type loosely — browser MediaRecorder may send unusual MIME types
    content_type = (audio.content_type or "").split(";")[0].strip()
    if content_type and content_type not in _ALLOWED_AUDIO_TYPES:
        raise BadRequestError(
            f"Unsupported audio format: {content_type}. "
            "Use mp3, wav, webm, m4a, or let the browser default."
        )

    audio_bytes = await audio.read()
    if len(audio_bytes) == 0:
        raise BadRequestError("Audio file is empty")
    if len(audio_bytes) > _MAX_AUDIO_BYTES:
        raise BadRequestError(f"Audio file exceeds 25 MB limit ({len(audio_bytes)} bytes)")

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        # Wrap bytes in a file-like object with a filename so OpenAI knows the format
        filename = audio.filename or "recording.webm"
        audio_file = (filename, io.BytesIO(audio_bytes), content_type or "audio/webm")

        transcript = await client.audio.transcriptions.create(
            model=settings.VOICE_STT_MODEL,
            file=audio_file,
            response_format="verbose_json",
        )

        return {
            "text": transcript.text,
            "language": getattr(transcript, "language", None),
            "duration": getattr(transcript, "duration", None),
        }
    except Exception as e:
        raise AIProviderError(f"Transcription failed: {e}") from e


@router.post(
    "/synthesize",
    summary="Convert text to speech (Text-to-Speech)",
    response_class=StreamingResponse,
)
async def synthesize(
    body: dict,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    Converts text to speech using OpenAI TTS.

    Request body:
      {text: str, voice?: "alloy"|"echo"|"fable"|"onyx"|"nova"|"shimmer"}

    Returns an audio/mpeg stream suitable for `<audio>` playback.
    Max text length: 4096 characters (OpenAI limit).
    """
    _require_voice()

    text = (body.get("text") or "").strip()
    if not text:
        raise BadRequestError("text is required")
    if len(text) > 4096:
        raise BadRequestError("Text exceeds 4096 character limit for TTS")

    voice = body.get("voice") or settings.VOICE_TTS_VOICE
    _VALID_VOICES = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}
    if voice not in _VALID_VOICES:
        voice = settings.VOICE_TTS_VOICE

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        response = await client.audio.speech.create(
            model=settings.VOICE_TTS_MODEL,
            voice=voice,           # type: ignore[arg-type]
            input=text,
            response_format="mp3",
        )

        audio_bytes = response.content

        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": 'inline; filename="speech.mp3"',
                "Cache-Control": "no-cache",
            },
        )
    except Exception as e:
        raise AIProviderError(f"Speech synthesis failed: {e}") from e
