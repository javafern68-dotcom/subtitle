import re
import sys
from pathlib import Path

from bangla_subtitle_studio.app import main
from bangla_subtitle_studio.media import probe_video
from bangla_subtitle_studio.models import SubtitleSegment
from bangla_subtitle_studio.subtitles import parse_srt
from bangla_subtitle_studio.translation import (
    _accurate_online_translate_text,
    _valid_target_script,
    translate_segments,
)
from bangla_subtitle_studio.voice_translate import (
    _save_speech,
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
    if hindi_item.start != source[0].start or english_item.end != source[0].end:
        raise RuntimeError("Translation changed subtitle timing")
    if not re.search(r"[\u0980-\u09FF]", hindi_to_bangla.text):
        raise RuntimeError(
            f"Hindi-to-Bengali translation self-test failed: {hindi_to_bangla.text}"
        )


def srt_self_test(path: str) -> None:
    segments = parse_srt(path)
    text = " ".join(item.text for item in segments)
    if not segments or not re.search(r"[\u0980-\u09FF]", text) or segments[0].start > 5.0:
        raise RuntimeError(f"Bengali SRT self-test failed: {text}")


def voice_translate_self_test(input_video: str, output_video: str) -> None:
    info = probe_video(input_video)
    segments = create_voice_translated_video(
        input_video,
        float(info["duration"]),
        "hi",
        "bn",
        "Female",
        output_video,
    )
    text = " ".join(item.text for item in segments)
    if not segments or not re.search(r"[\u0980-\u09FF]", text):
        raise RuntimeError(f"Hindi voice did not become Bengali text/voice: {text}")
    if not Path(output_video).is_file() or Path(output_video).stat().st_size < 10_000:
        raise RuntimeError("Bengali dubbed video was not created")
    output_info = probe_video(output_video)
    if float(output_info["duration"]) < 0.5:
        raise RuntimeError("Bengali dubbed video is empty")


def voice_fallback_self_test(output_audio: str) -> None:
    _save_speech("আপনি কেমন আছেন?", "google:bn", output_audio)
    if not Path(output_audio).is_file() or Path(output_audio).stat().st_size < 1_000:
        raise RuntimeError("Google Bengali fallback voice was not created")


def accurate_translation_self_test() -> None:
    directions = [
        ("bn", "en", "আপনি কেমন আছেন?", re.compile(r"\bhow\b|\byou\b", re.I)),
        ("en", "bn", "How are you?", re.compile(r"আপনি|কেমন")),
        ("bn", "hi", "আপনি কেমন আছেন?", re.compile(r"आप|कैसे")),
        ("hi", "bn", "आप कैसे हैं?", re.compile(r"আপনি|কেমন")),
        ("hi", "en", "आप कैसे हैं?", re.compile(r"\bhow\b|\byou\b", re.I)),
        ("en", "hi", "How are you?", re.compile(r"आप|कैसे")),
    ]
    for source, target, text, meaning in directions:
        translated = _accurate_online_translate_text(text, source, target)
        if not _valid_target_script(text, translated, target) or not meaning.search(translated):
            raise RuntimeError(
                f"Accurate {source}-to-{target} translation failed: {translated}"
            )


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
    elif "--accurate-translation-self-test" in sys.argv:
        try:
            accurate_translation_self_test()
        except Exception:
            sys.exit(1)
    else:
        main()
