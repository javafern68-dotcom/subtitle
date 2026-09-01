import re
import sys
import tempfile
import traceback
import wave
from array import array
from pathlib import Path

from bangla_subtitle_studio.app import main
from bangla_subtitle_studio.media import extract_audio_chunk, probe_video
from bangla_subtitle_studio.models import SubtitleSegment
from bangla_subtitle_studio.subtitles import parse_srt
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
    create_text_voice(
        "আপনি কেমন আছেন? এটি Text To Voice পরীক্ষা।",
        "bn",
        "bn-BD-NabanitaNeural",
        output_audio,
        rate_percent=20,
        pitch_hz=8,
    )
    if not Path(output_audio).is_file() or Path(output_audio).stat().st_size < 1_000:
        raise RuntimeError("Controlled Bengali Text To Voice MP3 was not created")


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
    else:
        main()
