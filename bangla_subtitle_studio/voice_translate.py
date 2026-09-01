from __future__ import annotations

import os
import re
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Callable

from .media import _startupinfo, bundled_tool
from .models import SubtitleSegment
from .transcription import transcribe_video
from .translation import translate_voice_segments


class VoiceTranslationError(RuntimeError):
    pass


VoiceProgress = Callable[[float, str], None]
VOICE_SAMPLE_RATE = 24_000
_GOOGLE_VOICE_PREFIX = "google:"
_PREFERRED_VOICES = {
    ("bn", "Female"): "bn-BD-NabanitaNeural",
    ("bn", "Male"): "bn-BD-PradeepNeural",
    ("hi", "Female"): "hi-IN-SwaraNeural",
    ("hi", "Male"): "hi-IN-MadhurNeural",
    ("en", "Female"): "en-US-JennyNeural",
    ("en", "Male"): "en-US-GuyNeural",
    ("ar", "Female"): "ar-EG-SalmaNeural",
    ("ar", "Male"): "ar-EG-ShakirNeural",
    ("ur", "Female"): "ur-PK-UzmaNeural",
    ("ur", "Male"): "ur-PK-AsadNeural",
}
TEXT_VOICE_OPTIONS = {
    "bn": [
        ("bn-BD-NabanitaNeural", "নারী কণ্ঠ"),
        ("bn-BD-PradeepNeural", "পুরুষ কণ্ঠ"),
    ],
    "en": [
        ("en-US-JennyNeural", "নারী কণ্ঠ • US"),
        ("en-US-AriaNeural", "নারী কণ্ঠ • US"),
        ("en-US-GuyNeural", "পুরুষ কণ্ঠ • US"),
        ("en-GB-SoniaNeural", "নারী কণ্ঠ • UK"),
        ("en-GB-RyanNeural", "পুরুষ কণ্ঠ • UK"),
    ],
    "hi": [
        ("hi-IN-SwaraNeural", "নারী কণ্ঠ"),
        ("hi-IN-MadhurNeural", "পুরুষ কণ্ঠ"),
    ],
    "ar": [
        ("ar-EG-SalmaNeural", "নারী কণ্ঠ"),
        ("ar-EG-ShakirNeural", "পুরুষ কণ্ঠ"),
    ],
    "ur": [
        ("ur-PK-UzmaNeural", "নারী কণ্ঠ"),
        ("ur-PK-AsadNeural", "পুরুষ কণ্ঠ"),
    ],
}
def _cancelled(cancel_event: threading.Event | None) -> bool:
    return bool(cancel_event and cancel_event.is_set())


def _select_voice(voices: list[dict[str, object]], language: str, gender: str) -> str:
    candidates = [
        voice
        for voice in voices
        if str(voice.get("Locale", "")).lower().split("-")[0] == language
        and str(voice.get("Gender", "")).casefold() == gender.casefold()
    ]
    if not candidates:
        raise VoiceTranslationError(
            "নির্বাচিত ভাষা ও কণ্ঠের Online voice পাওয়া যায়নি। অন্য Gender নির্বাচন করুন।"
        )
    preferred = _PREFERRED_VOICES.get((language, gender))
    for voice in candidates:
        if str(voice.get("ShortName", "")) == preferred:
            return preferred
    selected = str(candidates[0].get("ShortName", "")).strip()
    if not selected:
        raise VoiceTranslationError("Online voice-এর নাম পাওয়া যায়নি।")
    return selected


def _online_voice(language: str, gender: str) -> str:
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            import asyncio
            import edge_tts

            voices = asyncio.run(edge_tts.list_voices())
            return _select_voice(voices, language, gender)
        except Exception as exc:
            last_error = exc
            if attempt == 0:
                time.sleep(1.0)
    try:
        from gtts.lang import tts_langs

        if language not in tts_langs():
            raise VoiceTranslationError(
                "নির্বাচিত ভাষার Microsoft অথবা Google voice পাওয়া যায়নি।"
            )
        return f"{_GOOGLE_VOICE_PREFIX}{language}"
    except VoiceTranslationError:
        raise
    except Exception as exc:
        raise VoiceTranslationError(
            "Microsoft ও Google—দুই Natural voice service প্রস্তুত করা যায়নি।"
        ) from (last_error or exc)


def _save_google_speech(text: str, language: str, output_path: str) -> None:
    from gtts import gTTS

    Path(output_path).unlink(missing_ok=True)
    gTTS(text=text, lang=language, slow=False).save(output_path)


def _save_speech(text: str, voice: str, output_path: str) -> None:
    language = voice.removeprefix(_GOOGLE_VOICE_PREFIX).split("-", 1)[0].lower()
    if voice.startswith(_GOOGLE_VOICE_PREFIX):
        try:
            _save_google_speech(text, language, output_path)
            return
        except Exception as exc:
            raise VoiceTranslationError(
                "Google fallback voice download হয়নি। Internet, VPN ও Firewall পরীক্ষা করুন।"
            ) from exc
    try:
        import edge_tts

        edge_tts.Communicate(text=text, voice=voice).save_sync(output_path)
        return
    except Exception as edge_error:
        try:
            _save_google_speech(text, language, output_path)
            return
        except Exception as google_error:
            raise VoiceTranslationError(
                "Microsoft ও Google—দুই voice service-এই connection হয়নি। Internet, VPN ও Firewall পরীক্ষা করুন।"
            ) from google_error


def _split_text_voice_chunks(text: str, max_chars: int = 2_400) -> list[str]:
    """Split a long script at natural sentence/word boundaries for reliable TTS."""
    limit = max(200, int(max_chars))
    normalized = str(text).replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+", " ", normalized).strip()
    pieces = [
        value.strip()
        for value in re.split(r"(?<=[.!?।])\s+|\n+", normalized)
        if value.strip()
    ]
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        while len(piece) > limit:
            cut = piece.rfind(" ", 0, limit + 1)
            if cut < limit // 3:
                cut = limit
            head = piece[:cut].strip()
            if current:
                chunks.append(current)
                current = ""
            if head:
                chunks.append(head)
            piece = piece[cut:].strip()
        candidate = f"{current} {piece}".strip() if current else piece
        if current and len(candidate) > limit:
            chunks.append(current)
            current = piece
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _signed_control(value: int, suffix: str) -> str:
    number = int(value)
    return f"{number:+d}{suffix}"


def _apply_google_voice_controls(
    source_path: str,
    output_path: str,
    rate_percent: int,
    pitch_hz: int,
) -> None:
    speed = max(0.50, min(2.0, 1.0 + rate_percent / 100.0))
    pitch_factor = max(0.80, min(1.20, 1.0 + pitch_hz / 300.0))
    filters: list[str] = []
    if abs(pitch_factor - 1.0) > 0.001:
        filters.extend(
            [
                "aresample=44100",
                f"asetrate={44100 * pitch_factor:.3f}",
                "aresample=44100",
                _atempo_expression(1.0 / pitch_factor),
            ]
        )
    if abs(speed - 1.0) > 0.001:
        filters.append(_atempo_expression(speed))
    if not filters:
        os.replace(source_path, output_path)
        return
    ffmpeg = bundled_tool("ffmpeg")
    completed = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            source_path,
            "-vn",
            "-af",
            ",".join(filters),
            "-c:a",
            "libmp3lame",
            "-b:a",
            "192k",
            output_path,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        startupinfo=_startupinfo(),
        check=False,
    )
    if completed.returncode != 0 or not Path(output_path).is_file():
        raise VoiceTranslationError(
            completed.stderr.decode("utf-8", "replace").strip()
            or "Google voice-এর Speed/Pitch পরিবর্তন করা যায়নি।"
        )


def _save_text_voice_chunk(
    text: str,
    language: str,
    voice_id: str,
    output_path: str,
    rate_percent: int,
    pitch_hz: int,
) -> None:
    Path(output_path).unlink(missing_ok=True)
    try:
        import edge_tts

        edge_tts.Communicate(
            text=text,
            voice=voice_id,
            rate=_signed_control(rate_percent, "%"),
            pitch=_signed_control(pitch_hz, "Hz"),
        ).save_sync(output_path)
        if Path(output_path).is_file() and Path(output_path).stat().st_size > 500:
            return
        raise VoiceTranslationError("Microsoft voice file খালি হয়েছে।")
    except Exception as edge_error:
        raw_path = str(Path(output_path).with_suffix(".google.mp3"))
        try:
            _save_google_speech(text, language, raw_path)
            _apply_google_voice_controls(
                raw_path, output_path, rate_percent, pitch_hz
            )
        except Exception as google_error:
            raise VoiceTranslationError(
                "Text To Voice-এর Microsoft ও Google service-এ connection হয়নি। Internet, VPN ও Firewall পরীক্ষা করুন।"
            ) from google_error
        finally:
            Path(raw_path).unlink(missing_ok=True)


def create_text_voice(
    text: str,
    language: str,
    voice_id: str,
    output_path: str,
    rate_percent: int = 0,
    pitch_hz: int = 0,
    progress: VoiceProgress | None = None,
    cancel_event: threading.Event | None = None,
) -> None:
    """Create an MP3 voice from a typed script with voice, speed and pitch control."""
    script = str(text).strip()
    lang = language.strip().lower()
    voice = voice_id.strip()
    if not script:
        raise VoiceTranslationError("প্রথমে Text To Voice ঘরে লেখা দিন।")
    if len(script) > 100_000:
        raise VoiceTranslationError("একবারে সর্বোচ্চ ১,০০,০০০ অক্ষরের script দিন।")
    if lang not in TEXT_VOICE_OPTIONS:
        raise VoiceTranslationError("নির্বাচিত Text To Voice ভাষাটি সমর্থিত নয়।")
    allowed_voices = {item[0] for item in TEXT_VOICE_OPTIONS[lang]}
    if voice not in allowed_voices:
        raise VoiceTranslationError("নির্বাচিত Voice ID ভাষাটির সঙ্গে মিলছে না।")
    rate = max(-50, min(100, int(round(rate_percent))))
    pitch = max(-50, min(50, int(round(pitch_hz))))
    destination = Path(output_path)
    if destination.suffix.lower() != ".mp3":
        destination = destination.with_suffix(".mp3")
    destination.parent.mkdir(parents=True, exist_ok=True)
    chunks = _split_text_voice_chunks(script)
    if not chunks:
        raise VoiceTranslationError("Voice তৈরি করার মতো লেখা পাওয়া যায়নি।")
    if progress:
        progress(0.02, "Text To Voice প্রস্তুত হচ্ছে…")

    with tempfile.TemporaryDirectory(
        prefix="bangla_text_voice_", dir=str(destination.parent)
    ) as temp_dir:
        part_paths: list[str] = []
        for index, chunk in enumerate(chunks):
            if _cancelled(cancel_event):
                raise VoiceTranslationError("Text To Voice বাতিল করা হয়েছে।")
            part_path = str(Path(temp_dir) / f"voice_{index:04d}.mp3")
            _save_text_voice_chunk(
                chunk, lang, voice, part_path, rate, pitch
            )
            part_paths.append(part_path)
            if progress:
                progress(
                    0.05 + 0.85 * (index + 1) / len(chunks),
                    f"Voice তৈরি হচ্ছে—{index + 1}/{len(chunks)} অংশ",
                )

        final_temp = str(Path(temp_dir) / "complete_voice.mp3")
        if len(part_paths) == 1:
            os.replace(part_paths[0], final_temp)
        else:
            concat_path = Path(temp_dir) / "voice_parts.txt"
            concat_lines = []
            for part_path in part_paths:
                safe_path = Path(part_path).as_posix().replace("'", "'\\''")
                concat_lines.append(f"file '{safe_path}'")
            concat_path.write_text("\n".join(concat_lines), encoding="utf-8")
            ffmpeg = bundled_tool("ffmpeg")
            completed = subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_path),
                    "-vn",
                    "-c:a",
                    "libmp3lame",
                    "-b:a",
                    "192k",
                    final_temp,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=_startupinfo(),
                check=False,
            )
            if completed.returncode != 0 or not Path(final_temp).is_file():
                raise VoiceTranslationError(
                    completed.stderr.decode("utf-8", "replace").strip()
                    or "Text To Voice-এর অংশগুলো একসঙ্গে করা যায়নি।"
                )
        if _cancelled(cancel_event):
            raise VoiceTranslationError("Text To Voice বাতিল করা হয়েছে।")
        destination.unlink(missing_ok=True)
        os.replace(final_temp, destination)
    if not destination.is_file() or destination.stat().st_size < 500:
        raise VoiceTranslationError("Text To Voice MP3 তৈরি হয়নি।")
    if progress:
        progress(1.0, "Text To Voice MP3 তৈরি হয়েছে।")


def _probe_audio_duration(path: str) -> float:
    ffprobe = bundled_tool("ffprobe")
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        startupinfo=_startupinfo(),
        check=False,
    )
    try:
        return max(0.05, float(completed.stdout.decode("utf-8", "replace").strip()))
    except ValueError as exc:
        raise VoiceTranslationError("তৈরি হওয়া voice-এর সময় পড়া যায়নি।") from exc


def _atempo_expression(tempo: float) -> str:
    """Create a compatible FFmpeg atempo chain without cutting translated words."""
    remaining = max(0.50, float(tempo))
    factors: list[float] = []
    while remaining > 2.0:
        factors.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5
    factors.append(remaining)
    return ",".join(f"atempo={factor:.5f}" for factor in factors)


def _fit_speech_to_cue(source_path: str, output_path: str, cue_duration: float) -> float:
    """Fit the complete utterance inside a cue without slowing or truncating it."""
    ffmpeg = bundled_tool("ffmpeg")
    source_duration = _probe_audio_duration(source_path)
    target_duration = max(0.35, cue_duration - 0.06)
    # A shorter translated phrase must keep its natural voice rate. Only speed
    # up a phrase that would otherwise cross into the next source phrase.
    tempo = max(1.0, source_duration / target_duration * 1.025)
    output_duration = source_duration
    for _attempt in range(2):
        completed = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                source_path,
                "-vn",
                "-af",
                _atempo_expression(tempo),
                "-ac",
                "1",
                "-ar",
                str(VOICE_SAMPLE_RATE),
                "-c:a",
                "pcm_s16le",
                output_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=_startupinfo(),
            check=False,
        )
        if completed.returncode != 0:
            raise VoiceTranslationError(
                completed.stderr.decode("utf-8", "replace").strip()
                or "Translated voice-এর গতি মূল কথার সঙ্গে মেলানো যায়নি।"
            )
        output_duration = _probe_audio_duration(output_path)
        if output_duration <= target_duration + 0.025:
            return output_duration
        # FFmpeg/MP3 padding can leave a small overrun. Refit from the original
        # speech instead of cutting the end of the translated sentence.
        tempo *= output_duration / target_duration * 1.02
    return output_duration


def _write_silence(writer: wave.Wave_write, frame_count: int) -> None:
    remaining = max(0, int(frame_count))
    empty_chunk = b"\x00\x00" * 24_000
    while remaining:
        count = min(remaining, 24_000)
        writer.writeframesraw(empty_chunk[: count * 2])
        remaining -= count


def _build_timed_voice_track(
    segments: list[SubtitleSegment],
    voice: str,
    duration: float,
    output_path: str,
    working_dir: str,
    progress: VoiceProgress | None = None,
    cancel_event: threading.Event | None = None,
) -> None:
    ordered = sorted((item.normalized() for item in segments), key=lambda item: item.start)
    current_frame = 0
    with wave.open(output_path, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(VOICE_SAMPLE_RATE)
        for index, item in enumerate(ordered):
            if _cancelled(cancel_event):
                raise VoiceTranslationError("Voice Translate বাতিল করা হয়েছে।")
            text = " ".join(item.text.split()).strip()
            if not text:
                continue
            mp3_path = str(Path(working_dir) / f"voice_{index:05d}.mp3")
            wav_path = str(Path(working_dir) / f"voice_{index:05d}.wav")
            last_error: Exception | None = None
            for attempt in range(2):
                try:
                    _save_speech(text, voice, mp3_path)
                    last_error = None
                    break
                except VoiceTranslationError as exc:
                    last_error = exc
                    if attempt == 0:
                        time.sleep(1.0)
            if last_error:
                raise last_error
            next_start = (
                ordered[index + 1].start
                if index + 1 < len(ordered)
                else max(duration, item.end)
            )
            # The phrase may use the source pause after it, but must finish just
            # before the next phrase starts. This avoids both word cutting and
            # voices speaking on top of one another.
            available_duration = max(
                0.35,
                next_start - item.start - 0.04,
            )
            _fit_speech_to_cue(mp3_path, wav_path, available_duration)
            start_frame = max(0, round(item.start * VOICE_SAMPLE_RATE))
            if start_frame > current_frame:
                _write_silence(writer, start_frame - current_frame)
                current_frame = start_frame
            with wave.open(wav_path, "rb") as reader:
                data = reader.readframes(reader.getnframes())
            if data:
                writer.writeframesraw(data)
                current_frame += len(data) // 2
            if progress:
                progress(
                    (index + 1) / max(1, len(ordered)),
                    f"Natural translated voice তৈরি হচ্ছে—{index + 1}/{len(ordered)} phrase",
                )
        final_frame = max(current_frame, round(max(0.1, duration) * VOICE_SAMPLE_RATE))
        if current_frame < final_frame:
            _write_silence(writer, final_frame - current_frame)


def _video_has_audio(video_path: str) -> bool:
    ffprobe = bundled_tool("ffprobe")
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            video_path,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        startupinfo=_startupinfo(),
        check=False,
    )
    return completed.returncode == 0 and bool(completed.stdout.strip())


def _mux_dubbed_video(
    video_path: str,
    voice_track: str,
    output_path: str,
    duration: float,
    original_volume: float,
    progress: VoiceProgress | None = None,
    cancel_event: threading.Event | None = None,
) -> None:
    ffmpeg = bundled_tool("ffmpeg")
    temp_output = str(Path(output_path).with_name(Path(output_path).stem + ".dubbing.mp4"))
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    if Path(temp_output).exists():
        Path(temp_output).unlink()
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        video_path,
        "-i",
        voice_track,
    ]
    keep_original = original_volume > 0.001 and _video_has_audio(video_path)
    if keep_original:
        command.extend(
            [
                "-filter_complex",
                f"[0:a]volume={max(0.0, min(1.0, original_volume)):.4f}[old];"
                "[old][1:a]amix=inputs=2:duration=longest:normalize=0[aout]",
                "-map",
                "0:v:0",
                "-map",
                "[aout]",
            ]
        )
    else:
        command.extend(["-map", "0:v:0", "-map", "1:a:0"])
    command.extend(
        [
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-t",
            f"{max(0.1, duration):.3f}",
            "-movflags",
            "+faststart",
            "-progress",
            "pipe:1",
            "-nostats",
            temp_output,
        ]
    )
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        startupinfo=_startupinfo(),
    )
    assert process.stdout is not None
    while True:
        if _cancelled(cancel_event):
            process.terminate()
            process.wait(timeout=10)
            if Path(temp_output).exists():
                Path(temp_output).unlink()
            raise VoiceTranslationError("Voice Translate বাতিল করা হয়েছে।")
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        key, _, value = line.strip().partition("=")
        if key in {"out_time_us", "out_time_ms"} and progress:
            try:
                seconds = float(value) / 1_000_000.0
                ratio = min(0.995, seconds / max(duration, 0.1))
                progress(ratio, f"Translated voice ভিডিওতে বসছে—{ratio * 100:.0f}%")
            except ValueError:
                pass
    stderr = process.stderr.read() if process.stderr else ""
    if process.returncode != 0:
        if Path(temp_output).exists():
            Path(temp_output).unlink()
        raise VoiceTranslationError(stderr.strip() or "Translated voice ভিডিও তৈরি হয়নি।")
    if Path(output_path).exists():
        Path(output_path).unlink()
    os.replace(temp_output, output_path)


def create_voice_translated_video(
    video_path: str,
    duration: float,
    source_language: str,
    target_language: str,
    gender: str,
    output_path: str,
    original_volume: float = 0.0,
    progress: VoiceProgress | None = None,
    cancel_event: threading.Event | None = None,
) -> list[SubtitleSegment]:
    source = source_language.strip().lower()
    target = target_language.strip().lower()
    if not video_path or not Path(video_path).is_file():
        raise VoiceTranslationError("প্রথমে একটি ভিডিও দিন।")
    if source == target:
        raise VoiceTranslationError("মূল voice ও নতুন voice-এর ভাষা আলাদা নির্বাচন করুন।")

    def transcribe_progress(value: float, message: str) -> None:
        if progress:
            progress(value * 0.34, message)

    source_segments = transcribe_video(
        video_path,
        duration,
        source,
        "",
        transcribe_progress,
        cancel_event,
        multilingual=True,
        # Dubbing needs short, timed phrases. V3.1 joined these again into
        # twelve-second lines, which produced long silences and clipped speech.
        segment_max_words=10,
        segment_max_chars=76,
        segment_max_duration=5.5,
        segment_max_gap=0.38,
    )

    def translation_progress(value: float, message: str) -> None:
        if progress:
            progress(0.34 + value * 0.22, message)

    translated = translate_voice_segments(
        source_segments,
        target,
        translation_progress,
        cancel_event,
        source_language=source,
    )
    translated = [
        SubtitleSegment(item.start, item.end, item.text, "") for item in translated
    ]
    if _cancelled(cancel_event):
        raise VoiceTranslationError("Voice Translate বাতিল করা হয়েছে।")
    if progress:
        progress(0.57, "Online natural voice নির্বাচন হচ্ছে…")
    voice = _online_voice(target, gender)

    with tempfile.TemporaryDirectory(prefix="bangla_voice_translate_") as temp_dir:
        voice_track = str(Path(temp_dir) / "translated_voice.wav")

        def voice_progress(value: float, message: str) -> None:
            if progress:
                progress(0.58 + value * 0.32, message)

        _build_timed_voice_track(
            translated,
            voice,
            duration,
            voice_track,
            temp_dir,
            voice_progress,
            cancel_event,
        )

        def mux_progress(value: float, message: str) -> None:
            if progress:
                progress(0.90 + value * 0.10, message)

        _mux_dubbed_video(
            video_path,
            voice_track,
            output_path,
            duration,
            original_volume,
            mux_progress,
            cancel_event,
        )
    if progress:
        progress(1.0, "Voice Translate সম্পন্ন হয়েছে।")
    return translated
