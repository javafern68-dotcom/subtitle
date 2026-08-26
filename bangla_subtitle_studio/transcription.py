from __future__ import annotations

import json
import math
import mimetypes
import tempfile
import threading
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Callable

from .media import extract_audio_chunk
from .models import SubtitleSegment
from .subtitles import split_for_readability


class TranscriptionError(RuntimeError):
    pass


ProgressCallback = Callable[[float, str], None]


def _multipart_body(
    fields: list[tuple[str, str]], file_field: str, file_path: str
) -> tuple[bytes, str]:
    boundary = "----BanglaSubtitleStudio" + uuid.uuid4().hex
    marker = f"--{boundary}\r\n".encode()
    chunks: list[bytes] = []
    for name, value in fields:
        chunks.extend(
            [
                marker,
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    path = Path(file_path)
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    chunks.extend(
        [
            marker,
            (
                f'Content-Disposition: form-data; name="{file_field}"; filename="{path.name}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8"),
            path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(chunks), boundary


def validate_api_key(api_key: str, timeout: int = 30) -> None:
    secret = api_key.strip()
    if not secret:
        raise TranscriptionError("OpenAI API key দিন।")
    request = urllib.request.Request(
        "https://api.openai.com/v1/models",
        method="GET",
        headers={
            "Authorization": f"Bearer {secret}",
            "User-Agent": "BanglaSubtitleStudio/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status < 200 or response.status >= 300:
                raise TranscriptionError(f"OpenAI API পরীক্ষা ব্যর্থ হয়েছে ({response.status})।")
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise TranscriptionError("API key সঠিক নয়। নতুন বা সঠিক OpenAI API key দিন।") from exc
        if exc.code == 429:
            raise TranscriptionError("API limit শেষ হয়েছে। OpenAI billing/usage পরীক্ষা করুন।") from exc
        raise TranscriptionError(f"OpenAI API পরীক্ষা ব্যর্থ হয়েছে ({exc.code})।") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise TranscriptionError("ইন্টারনেট সংযোগ পাওয়া যায়নি অথবা OpenAI-তে সংযোগ হয়নি।") from exc


def transcribe_audio_file(
    api_key: str,
    audio_path: str,
    language: str = "bn",
    prompt: str = "",
    timeout: int = 900,
) -> list[SubtitleSegment]:
    if not api_key.strip():
        raise TranscriptionError("OpenAI API key দিন।")
    fields: list[tuple[str, str]] = [
        ("model", "whisper-1"),
        ("response_format", "verbose_json"),
        ("timestamp_granularities[]", "segment"),
    ]
    if language and language != "auto":
        fields.append(("language", language))
    if prompt.strip():
        fields.append(("prompt", prompt.strip()[:900]))
    body, boundary = _multipart_body(fields, "file", audio_path)
    request = urllib.request.Request(
        "https://api.openai.com/v1/audio/transcriptions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
            "User-Agent": "BanglaSubtitleStudio/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", "replace")
        try:
            message = json.loads(details).get("error", {}).get("message", details)
        except json.JSONDecodeError:
            message = details
        if exc.code == 401:
            message = "API key সঠিক নয়। নতুন বা সঠিক OpenAI API key দিন।"
        elif exc.code == 429:
            message = "API limit বা balance শেষ হয়েছে। OpenAI billing/usage পরীক্ষা করুন।"
        raise TranscriptionError(message or f"API error: {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise TranscriptionError("ইন্টারনেট সংযোগ পাওয়া যায়নি অথবা OpenAI-তে সংযোগ হয়নি।") from exc
    except (TimeoutError, json.JSONDecodeError) as exc:
        raise TranscriptionError("সাবটাইটেল উত্তর পাওয়া যায়নি। আবার চেষ্টা করুন।") from exc

    segments: list[SubtitleSegment] = []
    for item in payload.get("segments", []):
        text = str(item.get("text", "")).strip()
        if text:
            segments.append(
                SubtitleSegment(float(item.get("start", 0.0)), float(item.get("end", 0.0)), text).normalized()
            )
    if not segments and str(payload.get("text", "")).strip():
        duration = float(payload.get("duration", 5.0) or 5.0)
        segments.append(SubtitleSegment(0.0, max(1.0, duration), str(payload["text"]).strip()))
    return segments


def transcribe_video(
    video_path: str,
    duration: float,
    api_key: str,
    language: str = "bn",
    prompt: str = "",
    progress: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
    chunk_seconds: float = 540.0,
) -> list[SubtitleSegment]:
    total_parts = max(1, math.ceil(max(duration, 0.1) / chunk_seconds))
    combined: list[SubtitleSegment] = []
    previous_context = ""
    with tempfile.TemporaryDirectory(prefix="bangla_subtitle_") as temp_dir:
        for index in range(total_parts):
            if cancel_event and cancel_event.is_set():
                raise TranscriptionError("সাবটাইটেল তৈরি বাতিল করা হয়েছে।")
            start = index * chunk_seconds
            part_duration = min(chunk_seconds, max(0.1, duration - start))
            if progress:
                progress(index / total_parts, f"অডিও প্রস্তুত হচ্ছে—অংশ {index + 1}/{total_parts}")
            audio_path = str(Path(temp_dir) / f"audio_{index:03d}.mp3")
            extract_audio_chunk(video_path, audio_path, start, part_duration)
            if progress:
                progress((index + 0.25) / total_parts, f"বাংলা লেখা তৈরি হচ্ছে—অংশ {index + 1}/{total_parts}")
            context_prompt = prompt.strip()
            if previous_context:
                context_prompt = (context_prompt + "\nআগের অংশ: " + previous_context[-450:]).strip()
            part_segments = transcribe_audio_file(api_key, audio_path, language, context_prompt)
            for item in part_segments:
                combined.append(
                    SubtitleSegment(item.start + start, item.end + start, item.text, item.secondary_text)
                )
            if part_segments:
                previous_context = " ".join(item.text for item in part_segments[-4:])
            if progress:
                progress((index + 1) / total_parts, f"অংশ {index + 1}/{total_parts} সম্পন্ন")
    return split_for_readability(combined, max_words=12, max_duration=6.0)
