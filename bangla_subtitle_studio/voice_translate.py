from __future__ import annotations

import os
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
from .subtitles import merge_short_segments
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
_SOURCE_SCRIPT_PROMPTS = {
    "hi": "यह हिंदी भाषा में बोला गया वाक्य है।",
    "ar": "هذا نص منطوق باللغة العربية.",
    "ur": "یہ اردو زبان میں بولا گیا جملہ ہے۔",
    "bn": "এটি বাংলা ভাষায় বলা বাক্য।",
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


def _fit_speech_to_cue(source_path: str, output_path: str, cue_duration: float) -> None:
    ffmpeg = bundled_tool("ffmpeg")
    source_duration = _probe_audio_duration(source_path)
    target_duration = max(0.35, cue_duration - 0.04)
    tempo = max(0.80, source_duration / target_duration)
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
            _fit_speech_to_cue(mp3_path, wav_path, item.end - item.start)
            start_frame = max(0, round(item.start * VOICE_SAMPLE_RATE))
            end_frame = max(start_frame + 1, round(item.end * VOICE_SAMPLE_RATE))
            if start_frame > current_frame:
                _write_silence(writer, start_frame - current_frame)
                current_frame = start_frame
            with wave.open(wav_path, "rb") as reader:
                data = reader.readframes(max(0, end_frame - current_frame))
            allowed_bytes = max(0, end_frame - current_frame) * 2
            data = data[:allowed_bytes]
            if data:
                writer.writeframesraw(data)
                current_frame += len(data) // 2
            if current_frame < end_frame:
                _write_silence(writer, end_frame - current_frame)
                current_frame = end_frame
            if progress:
                progress(
                    (index + 1) / max(1, len(ordered)),
                    f"Natural translated voice তৈরি হচ্ছে—{index + 1}/{len(ordered)} line",
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
        _SOURCE_SCRIPT_PROMPTS.get(source, ""),
        transcribe_progress,
        cancel_event,
        multilingual=True,
    )
    source_segments = merge_short_segments(
        source_segments,
        max_words=20,
        max_chars=150,
        max_duration=12.0,
        max_gap=0.70,
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
