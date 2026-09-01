import re
import subprocess
import sys
import tempfile
import traceback
import wave
from array import array
from pathlib import Path

from bangla_subtitle_studio.app import main
from bangla_subtitle_studio.media import bundled_tool, extract_audio_chunk, probe_media, probe_video
from bangla_subtitle_studio.models import Project, SubtitleSegment, TimelineMedia
from bangla_subtitle_studio.subtitles import parse_srt
from bangla_subtitle_studio.timeline_exporter import export_timeline_project
from bangla_subtitle_studio.translation import (
    _format_avro_text,
    _select_valid_target_candidate,
    _valid_target_script,
    translate_segments,
)
from bangla_subtitle_studio.voice_translate import (
    _save_speech,
    create_text_voice,
    create_voice_translated_video,
)


def translation_self_test() -> None:
    source = [SubtitleSegment(0, 3, "আসসালামু আলাইকুম। সবাই কেমন আছেন?")]
    hindi_item = translate_segments(source, "hi")[0]
    english_item = translate_segments(source, "en")[0]
    hindi_to_bangla = translate_segments(
        [SubtitleSegment(0, 3, "आप कैसे हैं?")],
        "bn",
        source_language="hi",
    )[0]
    avro_item = translate_segments(
        [SubtitleSegment(0, 3, "বিসমিল্লাহির রহমানির রাহিম")],
        "avro",
    )[0]
    hindi = hindi_item.text
    english = english_item.text.casefold()
    if not re.search(r"[\u0900-\u097F]", hindi) or not re.search(r"(?:आप|कैसे|सब)", hindi):
        raise RuntimeError(f"Hindi translation self-test failed: {hindi}")
    if "how" not in english or not re.search(r"(?:you|everyone|all)", english):
        raise RuntimeError(f"English translation self-test failed: {english_item.text}")
    english_words = re.findall(r"[A-Za-z]+", english_item.text)
    if not english_words or any(not word[0].isupper() for word in english_words):
        raise RuntimeError(f"English title-case self-test failed: {english_item.text}")
    avro_words = re.findall(r"[A-Za-z]+", avro_item.text)
    if (
        not avro_words
        or any(not word[0].isupper() for word in avro_words)
        or re.search(r"[\u0980-\u09FF]", avro_item.text)
        or avro_item.secondary_text
    ):
        raise RuntimeError(f"Avro Roman-only self-test failed: {avro_item}")
    dirty_avro = _format_avro_text(
        "বিসমিল্লাহির রহমানির রাহিম আসসালামু আলাইকুম ওয়া রাহমাতুল্লাহি",
        "Bismillo্Lah Rohanir Rohim Asalamu Alikeumu Rahmatullo্Lahi",
    )
    if (
        dirty_avro
        != "Bismillahir Rahmanir Rahim Assalamu Alaikum Warahmatullahi"
        or re.search(r"[^\x00-\x7F]", dirty_avro)
        or re.search(r"[\u0980-\u09FF]", dirty_avro)
    ):
        raise RuntimeError(f"Dirty Avro mark cleanup self-test failed: {dirty_avro}")
    if hindi_item.start != source[0].start or english_item.end != source[0].end:
        raise RuntimeError("Translation changed subtitle timing")
    if not re.search(r"[\u0980-\u09FF]", hindi_to_bangla.text):
        raise RuntimeError(
            f"Hindi-to-Bengali translation self-test failed: {hindi_to_bangla.text}"
        )
    recovered = _select_valid_target_candidate(
        "आप कैसे हैं?",
        ["आप कैसे हैं?", "আপনি কেমন আছেন?"],
        ["आप कैसे हैं?", "आप कैसे हैं?"],
        "bn",
    )
    if recovered != "আপনি কেমন আছেন?":
        raise RuntimeError(f"Valid offline fallback candidate was not recovered: {recovered}")
    if not _valid_target_script(
        "यह OpenAI वीडियो है",
        "এটি OpenAI দিয়ে তৈরি একটি ভিডিও",
        "bn",
    ):
        raise RuntimeError("Mixed Bengali and proper-name validation self-test failed")


def srt_self_test(path: str) -> None:
    segments = parse_srt(path)
    text = " ".join(item.text for item in segments)
    if not segments or not re.search(r"[\u0980-\u09FF]", text) or segments[0].start > 5.0:
        raise RuntimeError(f"Bengali SRT self-test failed: {text}")


def _longest_internal_silence(video_path: str, duration: float) -> float:
    """Measure silence between the first and last spoken TTS windows."""
    with tempfile.TemporaryDirectory(prefix="dub_silence_test_") as temp_dir:
        audio_path = str(Path(temp_dir) / "dub.wav")
        extract_audio_chunk(video_path, audio_path, 0.0, duration)
        with wave.open(audio_path, "rb") as reader:
            rate = reader.getframerate()
            window_frames = max(1, rate // 10)
            active: list[bool] = []
            while True:
                chunk = reader.readframes(window_frames)
                if not chunk:
                    break
                samples = array("h")
                samples.frombytes(chunk)
                if sys.byteorder != "little":
                    samples.byteswap()
                rms = (
                    (sum(sample * sample for sample in samples) / len(samples)) ** 0.5
                    if samples
                    else 0.0
                )
                active.append(rms >= 120.0)
    spoken = [index for index, value in enumerate(active) if value]
    if not spoken:
        return duration
    longest = 0
    current = 0
    for value in active[spoken[0] : spoken[-1] + 1]:
        if value:
            longest = max(longest, current)
            current = 0
        else:
            current += 1
    return longest * 0.1


def voice_translate_self_test(input_video: str, output_video: str) -> None:
    log_path = Path(output_video + ".test.log")
    progress_lines: list[str] = []

    def record_progress(value: float, message: str) -> None:
        line = f"{value * 100:.1f}% {message}"
        progress_lines.append(line)
        log_path.write_text("\n".join(progress_lines), encoding="utf-8")

    try:
        info = probe_video(input_video)
        segments = create_voice_translated_video(
            input_video,
            float(info["duration"]),
            "hi",
            "bn",
            "Female",
            output_video,
            progress=record_progress,
        )
        text = " ".join(item.text for item in segments)
        progress_lines.append(f"Translated text: {text}")
        if not segments or not re.search(r"[\u0980-\u09FF]", text):
            raise RuntimeError(f"Hindi voice did not become Bengali text/voice: {text}")
        if not Path(output_video).is_file() or Path(output_video).stat().st_size < 10_000:
            raise RuntimeError("Bengali dubbed video was not created")
        meaning_hits = sum(
            bool(re.search(pattern, text))
            for pattern in (r"কেমন|কীভাবে", r"ভালো|ঠিক", r"দিন")
        )
        if meaning_hits < 2:
            raise RuntimeError(f"Hindi-to-Bengali meaning test failed: {text}")
        if len(segments) < 2 or any(item.end - item.start > 6.0 for item in segments):
            raise RuntimeError(f"Dubbing was not split into short timed phrases: {segments}")
        output_info = probe_video(output_video)
        if float(output_info["duration"]) < 0.5:
            raise RuntimeError("Bengali dubbed video is empty")
        longest_silence = _longest_internal_silence(
            output_video, float(output_info["duration"])
        )
        progress_lines.append(f"Longest internal silence: {longest_silence:.2f}s")
        if longest_silence > 2.2:
            raise RuntimeError(
                f"Dubbed voice contains a long internal silence: {longest_silence:.2f}s"
            )
        progress_lines.append(f"Output duration: {output_info['duration']}")
        log_path.write_text("\n".join(progress_lines), encoding="utf-8")
    except Exception:
        progress_lines.append(traceback.format_exc())
        log_path.write_text("\n".join(progress_lines), encoding="utf-8")
        raise


def voice_fallback_self_test(output_audio: str) -> None:
    engine = create_text_voice(
        "আপনি কেমন আছেন? এটি Text To Voice পরীক্ষা।",
        "bn",
        "bn-BD-NabanitaNeural",
        output_audio,
        rate_percent=20,
        pitch_hz=8,
        emotion="loving",
        emotion_strength=75,
        allow_basic_fallback=True,
    )
    if not Path(output_audio).is_file() or Path(output_audio).stat().st_size < 1_000:
        raise RuntimeError("Controlled Bengali Text To Voice MP3 was not created")
    if engine not in {"microsoft", "google", "mixed"}:
        raise RuntimeError(f"Text To Voice engine status is invalid: {engine}")


def organic_voice_self_test(output_audio: str) -> None:
    engine = create_text_voice(
        "আসসালামু আলাইকুম। আপনারা সবাই কেমন আছেন? আজ আমরা একটি সুন্দর গল্প শুনবো।",
        "bn",
        "organic:bn:female",
        output_audio,
        emotion="storytelling",
        emotion_strength=80,
        natural_pauses=True,
        engine_mode="organic",
    )
    output = Path(output_audio)
    if not output.is_file() or output.stat().st_size < 5_000:
        raise RuntimeError("Offline Organic Bengali Voice MP3 was not created")
    if engine != "organic":
        raise RuntimeError(f"Organic engine status is invalid: {engine}")


def timeline_self_test(output_video: str) -> None:
    log_path = Path(output_video + ".test.log")
    lines: list[str] = []
    try:
        ffmpeg = bundled_tool("ffmpeg")
        with tempfile.TemporaryDirectory(prefix="timeline_self_test_") as temp_dir:
            root = Path(temp_dir)
            source_paths = [root / "video-one.mp4", root / "video-two.mp4"]
            colors = ["0xD64B4B", "0x246BCE"]
            tones = [440, 660]
            for source, color, tone in zip(source_paths, colors, tones):
                completed = subprocess.run(
                    [
                        ffmpeg,
                        "-y",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-f",
                        "lavfi",
                        "-i",
                        f"color=c={color}:s=640x360:r=25:d=1.1",
                        "-f",
                        "lavfi",
                        "-i",
                        f"sine=frequency={tone}:duration=1.1",
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-c:a",
                        "aac",
                        "-shortest",
                        str(source),
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                if completed.returncode != 0:
                    raise RuntimeError(completed.stderr.decode("utf-8", "replace"))
            music = root / "music.wav"
            completed = subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=220:duration=2.2",
                    str(music),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.decode("utf-8", "replace"))
            project = Project(width=640, height=360, fps=25)
            project.timeline.width = 640
            project.timeline.height = 360
            for source in source_paths:
                info = probe_media(str(source))
                media = project.timeline.add_media(
                    TimelineMedia(
                        path=str(source),
                        name=source.name,
                        kind="video",
                        duration=float(info["duration"]),
                        width=int(info["width"]),
                        height=int(info["height"]),
                        fps=float(info["fps"]),
                        has_video=True,
                        has_audio=True,
                    )
                )
                project.timeline.add_clip(media.id)
            music_info = probe_media(str(music))
            music_media = project.timeline.add_media(
                TimelineMedia(
                    path=str(music),
                    name=music.name,
                    kind="audio",
                    duration=float(music_info["duration"]),
                    has_video=False,
                    has_audio=True,
                )
            )
            music_track = project.timeline.add_track("audio")
            music_clip = project.timeline.add_clip(
                music_media.id,
                music_track.id,
                start=0.0,
                add_linked_audio=False,
            )[0]
            music_clip.volume = 0.20
            music_clip.fade_in = 0.15
            music_clip.fade_out = 0.15
            export_timeline_project(project, output_video, "Preview")
            result = probe_media(output_video)
            if not Path(output_video).is_file() or Path(output_video).stat().st_size < 10_000:
                raise RuntimeError("Packaged Timeline MP4 was not created")
            if not result["has_video"] or not result["has_audio"]:
                raise RuntimeError(f"Timeline streams are incomplete: {result}")
            if float(result["duration"]) < 2.0:
                raise RuntimeError(f"Timeline output is too short: {result}")
            lines.extend(
                [
                    f"Timeline clips: {len(project.timeline.clips)}",
                    f"Timeline tracks: {len(project.timeline.tracks)}",
                    f"Output: {result}",
                    "Verified two sequential videos, linked source audio and a separate mixed audio layer.",
                ]
            )
            log_path.write_text("\n".join(lines), encoding="utf-8")
    except Exception:
        lines.append(traceback.format_exc())
        log_path.write_text("\n".join(lines), encoding="utf-8")
        raise


if __name__ == "__main__":
    if "--srt-self-test" in sys.argv:
        try:
            option_index = sys.argv.index("--srt-self-test")
            srt_self_test(sys.argv[option_index + 1])
        except Exception:
            sys.exit(1)
    elif "--translation-self-test" in sys.argv:
        try:
            translation_self_test()
        except Exception:
            sys.exit(1)
    elif "--voice-translate-self-test" in sys.argv:
        try:
            option_index = sys.argv.index("--voice-translate-self-test")
            voice_translate_self_test(
                sys.argv[option_index + 1],
                sys.argv[option_index + 2],
            )
        except Exception:
            sys.exit(1)
    elif "--voice-fallback-self-test" in sys.argv:
        try:
            option_index = sys.argv.index("--voice-fallback-self-test")
            voice_fallback_self_test(sys.argv[option_index + 1])
        except Exception:
            sys.exit(1)
    elif "--organic-voice-self-test" in sys.argv:
        try:
            option_index = sys.argv.index("--organic-voice-self-test")
            organic_voice_self_test(sys.argv[option_index + 1])
        except Exception:
            traceback.print_exc()
            sys.exit(1)
    elif "--timeline-self-test" in sys.argv:
        try:
            option_index = sys.argv.index("--timeline-self-test")
            timeline_self_test(sys.argv[option_index + 1])
        except Exception:
            traceback.print_exc()
            sys.exit(1)
    else:
        main()
