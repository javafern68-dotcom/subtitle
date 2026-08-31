import re
import sys

from bangla_subtitle_studio.app import main
from bangla_subtitle_studio.models import SubtitleSegment
from bangla_subtitle_studio.subtitles import parse_srt
from bangla_subtitle_studio.translation import translate_segments


def translation_self_test() -> None:
    source = [SubtitleSegment(0, 3, "আসসালামু আলাইকুম। সবাই কেমন আছেন?")]
    hindi_item = translate_segments(source, "hi")[0]
    english_item = translate_segments(source, "en")[0]
    hindi = hindi_item.text
    english = english_item.text.casefold()
    if not re.search(r"[\u0900-\u097F]", hindi) or not re.search(r"(?:आप|कैसे|सब)", hindi):
        raise RuntimeError(f"Hindi translation self-test failed: {hindi}")
    if "how" not in english or not re.search(r"(?:you|everyone|all)", english):
        raise RuntimeError(f"English translation self-test failed: {english_item.text}")
    if hindi_item.start != source[0].start or english_item.end != source[0].end:
        raise RuntimeError("Translation changed subtitle timing")


def srt_self_test(path: str) -> None:
    segments = parse_srt(path)
    text = " ".join(item.text for item in segments)
    if not segments or not re.search(r"[\u0980-\u09FF]", text) or segments[0].start > 5.0:
        raise RuntimeError(f"Bengali SRT self-test failed: {text}")


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
    else:
        main()
