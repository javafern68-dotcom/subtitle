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
from .subtitles import parse_srt, split_for_readability


class TranscriptionError(RuntimeError):
    pass


ProgressCallback = Callable[[float, str], None]
AudioProgressCallback = Callable[[float, float], None]

OFFLINE_MODEL_NAME = "ggml-banglaasr-small-q5_0.bin"
OFFLINE_ENGINE_NAME = "whisper-cli.exe" if os.name == "nt" else "whisper-cli"
_WHISPER_PROGRESS_RE = re.compile(rb"progress\s*=\s*(\d{1,3})%", re.IGNORECASE)
BANGLA_SCRIPT_PROMPT = (
    "আমি বাংলাদেশের বাংলা ভাষায় কথা বলছি। সব কথা বাংলা অক্ষরে হুবহু লেখা হচ্ছে। "
    "বাংলা বাক্য, বাংলা বানান এবং বাংলা যতিচিহ্ন ব্যবহার করা হচ্ছে।"
)


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


def offline_components() -> tuple[str, str]:
    engine = _resolve_offline_component(
        "BSS_WHISPER_CLI", Path("tools") / "whisper" / OFFLINE_ENGINE_NAME
    )
    model = _resolve_offline_component(
        "BSS_WHISPER_MODEL", Path("models") / OFFLINE_MODEL_NAME
    )
    return engine, model


def build_whisper_command(
    engine_path: str,
    model_path: str,
    audio_path: str,
    output_prefix: str,
    language: str = "bn",
    prompt: str = "",
    threads: int | None = None,
) -> list[str]:
    # Use all available cores on small computers, while keeping a sensible cap
    # for laptops with many logical cores.
    thread_count = threads or max(2, min(8, os.cpu_count() or 4))
    command = [
        engine_path,
        "-m",
        model_path,
        "-f",
        audio_path,
        "-l",
        "bn",
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
    clean_prompt = " ".join(f"{BANGLA_SCRIPT_PROMPT} {prompt}".split()).strip()
    if clean_prompt:
        command.extend(["--prompt", clean_prompt[:700], "--carry-initial-prompt"])
    return command


def transcribe_audio_file(
    audio_path: str,
    language: str = "bn",
    prompt: str = "",
    cancel_event: threading.Event | None = None,
    output_prefix: str | None = None,
    progress: AudioProgressCallback | None = None,
) -> list[SubtitleSegment]:
    engine, model = offline_components()
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
    chunk_seconds: float = 300.0,
) -> list[SubtitleSegment]:
    # Resolve before extracting audio so a damaged installation fails immediately.
    offline_components()
    # This edition intentionally creates Bengali-script subtitles only. Keeping the
    # language token fixed prevents accidental auto-detection or translation.
    language = "bn"
    total_parts = max(1, math.ceil(max(duration, 0.1) / chunk_seconds))
    combined: list[SubtitleSegment] = []
    previous_context = ""
    with tempfile.TemporaryDirectory(prefix="bangla_subtitle_offline_") as temp_dir:
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
                    f"কম্পিউটারে বাংলা লেখা তৈরি হচ্ছে—অংশ {index + 1}/{total_parts}। সময় লাগতে পারে…",
                )
            context_prompt = prompt.strip()
            if previous_context:
                context_prompt = (context_prompt + "\nআগের অংশ: " + previous_context[-450:]).strip()
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
                audio_path,
                language,
                context_prompt,
                cancel_event,
                output_prefix,
                part_progress,
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
    return split_for_readability(combined, max_words=12, max_duration=6.0)
