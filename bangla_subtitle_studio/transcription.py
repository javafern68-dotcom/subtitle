from __future__ import annotations

import math
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

from .media import _startupinfo, extract_audio_chunk
from .models import SubtitleSegment
from .subtitles import merge_short_segments, parse_srt, split_for_readability


class TranscriptionError(RuntimeError):
    pass


ProgressCallback = Callable[[float, str], None]
AudioProgressCallback = Callable[[float, float], None]

OFFLINE_MODEL_NAME = "ggml-bengali-medium-q4_0.bin"
MULTILINGUAL_MODEL_NAME = "ggml-large-v3-turbo-q5_0.bin"
VAD_MODEL_NAME = "ggml-silero-v6.2.0.bin"
OFFLINE_ENGINE_NAME = "whisper-cli.exe" if os.name == "nt" else "whisper-cli"
_WHISPER_PROGRESS_RE = re.compile(rb"progress\s*=\s*(\d{1,3})%", re.IGNORECASE)


def _application_roots() -> list[Path]:
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
        meipass = str(getattr(sys, "_MEIPASS", "")).strip()
        if meipass:
            roots.append(Path(meipass))
    roots.append(Path(__file__).resolve().parent.parent)
    return roots


def _resolve_offline_component(environment_name: str, relative_path: Path) -> str:
    configured = os.environ.get(environment_name, "").strip()
    if configured and Path(configured).is_file():
        return configured
    for root in _application_roots():
        candidate = root / relative_path
        if candidate.is_file():
            return str(candidate)
    raise TranscriptionError(
        "Offline বাংলা AI model পাওয়া যায়নি। Bangla Subtitle Studio Offline installer আবার Install করুন।"
    )


def offline_components() -> tuple[str, str, str]:
    engine = _resolve_offline_component(
        "BSS_WHISPER_CLI", Path("tools") / "whisper" / OFFLINE_ENGINE_NAME
    )
    model = _resolve_offline_component(
        "BSS_WHISPER_MODEL", Path("models") / OFFLINE_MODEL_NAME
    )
    vad_model = _resolve_offline_component(
        "BSS_VAD_MODEL", Path("models") / VAD_MODEL_NAME
    )
    return engine, model, vad_model


def multilingual_offline_components() -> tuple[str, str, str]:
    engine = _resolve_offline_component(
        "BSS_WHISPER_CLI", Path("tools") / "whisper" / OFFLINE_ENGINE_NAME
    )
    model = _resolve_offline_component(
        "BSS_MULTILINGUAL_WHISPER_MODEL", Path("models") / MULTILINGUAL_MODEL_NAME
    )
    vad_model = _resolve_offline_component(
        "BSS_VAD_MODEL", Path("models") / VAD_MODEL_NAME
    )
    return engine, model, vad_model


def build_whisper_command(
    engine_path: str,
    model_path: str,
    audio_path: str,
    output_prefix: str,
    language: str = "bn",
    prompt: str = "",
    threads: int | None = None,
    vad_model_path: str = "",
    force_bengali: bool = True,
) -> list[str]:
    # Use all available cores on small computers, while keeping a sensible cap
    # for laptops with many logical cores.
    thread_count = threads or max(2, min(8, os.cpu_count() or 4))
    requested_language = language.strip().lower()
    effective_language = "bn" if force_bengali else requested_language
    if not re.fullmatch(r"[a-z]{2,3}", effective_language):
        effective_language = "bn" if force_bengali else "auto"
    command = [
        engine_path,
        "-m",
        model_path,
        "-f",
        audio_path,
        "-l",
        effective_language,
        "-t",
        str(thread_count),
        "-osrt",
        "-of",
        output_prefix,
        "-ml",
        "84",
        "-sow",
        "-np",
        "-pp",
    ]
    if vad_model_path:
        command.extend(
            [
                "--vad",
                "-vm",
                vad_model_path,
                "-vt",
                "0.45",
                "-vspd",
                "120",
                "-vsd",
                "250",
                "-vmsd",
                "28",
                "-vp",
                "120",
                "-vo",
                "0.20",
            ]
        )
    # A long generic prompt can be repeated as a hallucination by a fine-tuned
    # model. Only pass the user's proper names/terms as a short vocabulary hint.
    clean_prompt = " ".join(prompt.split()).strip()
    if clean_prompt:
        command.extend(["--prompt", clean_prompt[:300]])
    return command


def transcribe_audio_file(
    audio_path: str,
    language: str = "bn",
    prompt: str = "",
    cancel_event: threading.Event | None = None,
    output_prefix: str | None = None,
    progress: AudioProgressCallback | None = None,
    components: tuple[str, str, str] | None = None,
    force_bengali: bool = True,
) -> list[SubtitleSegment]:
    engine, model, vad_model = components or offline_components()
    prefix = output_prefix or str(Path(audio_path).with_suffix("")) + "_subtitle"
    srt_path = Path(prefix + ".srt")
    log_path = Path(prefix + ".log")
    command = build_whisper_command(
        engine,
        model,
        audio_path,
        prefix,
        language,
        prompt,
        vad_model_path=vad_model,
        force_bengali=force_bengali,
    )

    try:
        with log_path.open("wb") as log_file:
            process = subprocess.Popen(
                command,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                startupinfo=_startupinfo(),
            )
            log_position = 0
            progress_tail = b""
            last_percent = -1
            started_at = time.monotonic()
            last_callback_at = started_at
            while process.poll() is None:
                now = time.monotonic()
                if progress:
                    try:
                        with log_path.open("rb") as progress_log:
                            progress_log.seek(log_position)
                            new_output = progress_log.read()
                            log_position = progress_log.tell()
                        progress_tail = (progress_tail + new_output)[-512:]
                        matches = _WHISPER_PROGRESS_RE.findall(progress_tail)
                        if matches:
                            percent = max(0, min(100, int(matches[-1])))
                            if percent > last_percent:
                                last_percent = percent
                                progress(percent / 100.0, now - started_at)
                                last_callback_at = now
                    except (OSError, ValueError):
                        pass
                    # Some CPUs take a while before whisper.cpp prints the next
                    # percentage. Keep the UI visibly alive without inventing a
                    # higher model percentage.
                    if now - last_callback_at >= 1.0:
                        progress(max(0, last_percent) / 100.0, now - started_at)
                        last_callback_at = now
                if cancel_event and cancel_event.is_set():
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    raise TranscriptionError("সাবটাইটেল তৈরি বাতিল করা হয়েছে।")
                time.sleep(0.15)
            return_code = int(process.returncode or 0)
            if progress and return_code == 0:
                progress(1.0, time.monotonic() - started_at)
    except OSError as exc:
        raise TranscriptionError(
            "Offline AI engine চালু করা যায়নি। Software আবার Install করুন।"
        ) from exc

    if return_code != 0:
        details = ""
        try:
            details = log_path.read_text(encoding="utf-8", errors="replace").strip()[-1200:]
        except OSError:
            pass
        raise TranscriptionError(
            "Offline subtitle তৈরি হয়নি। কম্পিউটারে পর্যাপ্ত RAM আছে কি না পরীক্ষা করুন।"
            + (f"\n\n{details}" if details else "")
        )
    if not srt_path.is_file():
        raise TranscriptionError("Offline AI কোনো subtitle তৈরি করেনি। ভিডিওতে স্পষ্ট কথা আছে কি না দেখুন।")
    try:
        segments = parse_srt(srt_path)
    except OSError as exc:
        raise TranscriptionError("তৈরি হওয়া Offline subtitle পড়া যায়নি।") from exc
    if not segments:
        raise TranscriptionError(
            "ভিডিওতে স্পষ্ট বাংলা কথা পাওয়া যায়নি। অন্য একটি পরিষ্কার অডিও/ভিডিও দিয়ে চেষ্টা করুন।"
        )
    return segments


def transcribe_video(
    video_path: str,
    duration: float,
    language: str = "bn",
    prompt: str = "",
    progress: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
    chunk_seconds: float = 180.0,
    multilingual: bool = False,
) -> list[SubtitleSegment]:
    # Resolve before extracting audio so a damaged installation fails immediately.
    requested_language = language.strip().lower()
    use_multilingual_model = multilingual and requested_language != "bn"
    components = (
        multilingual_offline_components() if use_multilingual_model else offline_components()
    )
    # Normal subtitle generation keeps the proven Bengali-only model. Voice
    # Translate opts into the multilingual model for non-Bengali source audio.
    if not use_multilingual_model:
        language = "bn"
    total_parts = max(1, math.ceil(max(duration, 0.1) / chunk_seconds))
    combined: list[SubtitleSegment] = []
    previous_context = ""
    with tempfile.TemporaryDirectory(prefix="subtitle_voice_offline_") as temp_dir:
        for index in range(total_parts):
            if cancel_event and cancel_event.is_set():
                raise TranscriptionError("সাবটাইটেল তৈরি বাতিল করা হয়েছে।")
            start = index * chunk_seconds
            part_duration = min(chunk_seconds, max(0.1, duration - start))
            if progress:
                progress(
                    index / total_parts,
                    f"Offline অডিও প্রস্তুত হচ্ছে—অংশ {index + 1}/{total_parts}",
                )
            audio_path = str(Path(temp_dir) / f"audio_{index:03d}.wav")
            extract_audio_chunk(video_path, audio_path, start, part_duration)
            if progress:
                progress(
                    (index + 0.15) / total_parts,
                    f"কম্পিউটারে কথার লেখা তৈরি হচ্ছে—অংশ {index + 1}/{total_parts}। সময় লাগতে পারে…",
                )
            context_prompt = prompt.strip()
            if previous_context:
                context_label = "আগের অংশ:" if language == "bn" else "Previous context:"
                context_prompt = (context_prompt + f"\n{context_label} " + previous_context[-450:]).strip()
            output_prefix = str(Path(temp_dir) / f"subtitle_{index:03d}")

            def part_progress(value: float, elapsed_seconds: float) -> None:
                overall = (index + 0.15 + max(0.0, min(1.0, value)) * 0.80) / total_parts
                elapsed_total = max(0, int(elapsed_seconds))
                elapsed_minutes, elapsed_remainder = divmod(elapsed_total, 60)
                if elapsed_minutes:
                    elapsed_text = f"{elapsed_minutes} মিনিট {elapsed_remainder} সেকেন্ড"
                else:
                    elapsed_text = f"{elapsed_remainder} সেকেন্ড"
                if progress:
                    progress(
                        overall,
                        f"কাজ চলছে—{round(overall * 100)}% • {elapsed_text} • অংশ {index + 1}/{total_parts}",
                    )

            part_segments = transcribe_audio_file(
                audio_path=audio_path,
                language=language,
                prompt=context_prompt,
                cancel_event=cancel_event,
                output_prefix=output_prefix,
                progress=part_progress,
                components=components,
                force_bengali=not use_multilingual_model,
            )
            for item in part_segments:
                combined.append(
                    SubtitleSegment(
                        item.start + start,
                        item.end + start,
                        item.text,
                        item.secondary_text,
                    )
                )
            if part_segments:
                previous_context = " ".join(item.text for item in part_segments[-4:])
            if progress:
                progress(
                    (index + 1) / total_parts,
                    f"Offline অংশ {index + 1}/{total_parts} সম্পন্ন",
                )
    sentence_segments = merge_short_segments(
        combined,
        max_words=12,
        max_chars=88,
        max_duration=7.0,
        max_gap=0.55,
    )
    return split_for_readability(sentence_segments, max_words=12, max_duration=7.0)
