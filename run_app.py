import re
import sys

from bangla_subtitle_studio.app import main
from bangla_subtitle_studio.models import SubtitleSegment
from bangla_subtitle_studio.subtitles import parse_srt
from bangla_subtitle_studio.translation import translate_segments


def translation_self_test() -> None:
    source = [SubtitleSegment(0, 2, "বাংলাদেশ একটি সুন্দর দেশ।")]
    hindi = translate_segments(source, "hi")[0].text
    if not re.search(r"[\u0900-\u097F]", hindi):
        raise RuntimeError(f"Hindi translation self-test failed: {hindi}")


def srt_self_test(path: str) -> None:
    segments = parse_srt(path)
    text = " ".join(item.text for item in segments)
    if not segments or not re.search(r"[\u0980-\u09FF]", text):
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
