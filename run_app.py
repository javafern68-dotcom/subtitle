import re
import sys

from bangla_subtitle_studio.app import main
from bangla_subtitle_studio.models import SubtitleSegment
from bangla_subtitle_studio.translation import translate_segments


def translation_self_test() -> None:
    source = [SubtitleSegment(0, 2, "বাংলাদেশ একটি সুন্দর দেশ।")]
    hindi = translate_segments(source, "hi")[0].text
    if not re.search(r"[\u0900-\u097F]", hindi):
        raise RuntimeError(f"Hindi translation self-test failed: {hindi}")


if __name__ == "__main__":
    if "--translation-self-test" in sys.argv:
        try:
            translation_self_test()
        except Exception:
            sys.exit(1)
    else:
        main()
