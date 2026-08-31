from __future__ import annotations

import os
import re
import sys
import threading
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable

from .models import SubtitleSegment


class TranslationError(RuntimeError):
    pass


TranslationProgress = Callable[[float, str], None]
TRANSLATION_MODEL_DIR = "m2m100-418M-int8"
_BANGLA_GREETING_RE = re.compile(
    r"আস+সালামু[য়য়]?[া ]*আলাইকুম|আসসালামু\s+আলাইকুম",
    re.IGNORECASE,
)
_TARGET_GREETINGS = {
    "en": "Assalamu Alaikum",
    "hi": "अस्सलामु अलैकुम",
    "ar": "السلام عليكم",
    "ur": "السلام علیکم",
}
_AVRO_BISMILLAH_RE = re.compile(
    r"^\s*বিসমিল্লাহির?\s+র[া]?হমান(?:ির|ের)\s+রাহিম",
    re.IGNORECASE,
)
_AVRO_SALAM_RE = re.compile(
    r"^\s*আস+সালামু[য়য়]?[া ]*আলাইকুম|^\s*আসসালামু\s+আলাইকুম",
    re.IGNORECASE,
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


def translation_model_path() -> str:
    configured = os.environ.get("BSS_TRANSLATION_MODEL", "").strip()
    if configured and Path(configured).is_dir():
        return configured
    for root in _application_roots():
        candidate = root / "models" / TRANSLATION_MODEL_DIR
        if (candidate / "model.bin").is_file():
            return str(candidate)
    raise TranslationError(
        "Offline ভাষা Translation model পাওয়া যায়নি। Multilanguage installer আবার Install করুন।"
    )


def shift_segments_earlier(
    segments: list[SubtitleSegment], lead_seconds: float = 0.35
) -> list[SubtitleSegment]:
    lead = max(0.0, min(2.0, float(lead_seconds)))
    return shift_segments(segments, -lead)


def shift_segments(
    segments: list[SubtitleSegment], offset_seconds: float
) -> list[SubtitleSegment]:
    """Move every subtitle by the same signed offset without changing language."""
    offset = max(-30.0, min(30.0, float(offset_seconds)))
    shifted: list[SubtitleSegment] = []
    for item in segments:
        start = max(0.0, item.start + offset)
        end = max(start + 0.05, item.end + offset)
        shifted.append(SubtitleSegment(start, end, item.text, item.secondary_text))
    return shifted


def _avro_reverse(texts: list[str]) -> list[str]:
    try:
        import avro
    except ImportError as exc:
        raise TranslationError("Avro converter পাওয়া যায়নি। Software আবার Install করুন।") from exc
    return [str(value).strip() for value in avro.reverse_iter(texts)]


def _title_case_latin_words(text: str) -> str:
    """Capitalize every Roman-script word while keeping punctuation intact."""
    def title_word(match: re.Match[str]) -> str:
        word = match.group(0).lower()
        return word[:1].upper() + word[1:]

    return re.sub(r"[A-Za-z]+(?:['’][A-Za-z]+)*", title_word, text.strip())


def _format_avro_text(source: str, converted: str) -> str:
    """Produce predictable Roman Bangla for important spoken openings."""
    output = _title_case_latin_words(converted)
    if _AVRO_BISMILLAH_RE.search(source):
        output = re.sub(
            r"^\s*\S+(?:\s+\S+){0,2}",
            "Bismillahir Rahmanir Rahim",
            output,
            count=1,
        )
    if _AVRO_SALAM_RE.search(source):
        output = re.sub(
            r"^\s*\S+(?:\s+\S+){0,1}",
            "Assalamu Alaikum",
            output,
            count=1,
        )
    return output.strip()


def _comparison_text(value: str) -> str:
    return re.sub(r"[^\w\u0980-\u09FF]+", "", value.casefold())


def _select_semantic_candidate(
    source: str, candidates: list[str], back_translations: list[str]
) -> str:
    """Pick the target sentence whose Bengali back-translation keeps most meaning."""
    if not candidates:
        return ""
    source_key = _comparison_text(source)
    best_index = 0
    best_score = -1.0
    for index, candidate in enumerate(candidates):
        back = back_translations[index] if index < len(back_translations) else ""
        score = SequenceMatcher(None, source_key, _comparison_text(back)).ratio()
        if score > best_score:
            best_index = index
            best_score = score
    return candidates[best_index].strip()


def _preserve_greeting(source: str, translated: str, target: str) -> str:
    if not _BANGLA_GREETING_RE.search(source):
        return translated.strip()
    greeting = _TARGET_GREETINGS.get(target, "Assalamu Alaikum")
    lowered = translated.casefold()
    greeting_is_present = (
        "salam" in lowered
        or "सलाम" in translated
        or "अस्स" in translated
        or "سلام" in translated
    )
    if greeting_is_present:
        return translated.strip()
    rest = translated.strip()
    return greeting + ("। " + rest if rest else "")


def _decode_hypothesis(tokenizer: object, tokens: list[str], prefix: str) -> str:
    output_tokens = tokens[1:] if tokens and tokens[0] == prefix else tokens
    token_ids = tokenizer.convert_tokens_to_ids(output_tokens)
    return tokenizer.decode(token_ids, skip_special_tokens=True).strip()


def translate_segments(
    segments: list[SubtitleSegment],
    target_language: str,
    progress: TranslationProgress | None = None,
    cancel_event: threading.Event | None = None,
) -> list[SubtitleSegment]:
    target = target_language.strip().lower()
    if target == "bn":
        return [SubtitleSegment(item.start, item.end, item.text, "") for item in segments]

    source_texts = [item.text.strip() for item in segments]
    if target == "avro":
        if progress:
            progress(0.15, "বাংলা লেখা Avro/Banglish করা হচ্ছে…")
        converted = [
            _format_avro_text(source_texts[index], value)
            for index, value in enumerate(_avro_reverse(source_texts))
        ]
        if progress:
            progress(1.0, "Avro/Banglish subtitle তৈরি হয়েছে")
        return [
            SubtitleSegment(item.start, item.end, converted[index] or item.text, "")
            for index, item in enumerate(segments)
        ]

    model_dir = translation_model_path()
    try:
        import ctranslate2
        from transformers import M2M100Tokenizer

        if progress:
            progress(0.03, "Offline Translation AI চালু হচ্ছে…")
        tokenizer = M2M100Tokenizer.from_pretrained(
            model_dir,
            local_files_only=True,
            clean_up_tokenization_spaces=True,
        )
        tokenizer.src_lang = "bn"
        target_token = tokenizer.lang_code_to_token.get(target)
        if not target_token:
            raise TranslationError("নির্বাচিত ভাষাটি Offline Translation model-এ নেই।")
        translator = ctranslate2.Translator(
            model_dir,
            device="cpu",
            compute_type="int8",
            inter_threads=1,
            intra_threads=max(2, min(8, os.cpu_count() or 4)),
        )

        translated: list[str] = []
        batch_size = 12
        for start in range(0, len(source_texts), batch_size):
            if cancel_event and cancel_event.is_set():
                raise TranslationError("Subtitle Translation বাতিল করা হয়েছে।")
            batch = source_texts[start : start + batch_size]
            encoded = [
                tokenizer.convert_ids_to_tokens(tokenizer.encode(text)) for text in batch
            ]
            results = translator.translate_batch(
                encoded,
                target_prefix=[[target_token]] * len(encoded),
                beam_size=6,
                num_hypotheses=2,
                patience=1.2,
                max_decoding_length=160,
                repetition_penalty=1.08,
                no_repeat_ngram_size=3,
                disable_unk=True,
            )
            candidate_rows = [
                [
                    _decode_hypothesis(tokenizer, hypothesis, target_token)
                    for hypothesis in result.hypotheses
                ]
                for result in results
            ]

            # A second, cheap check translates both candidates back to Bengali.
            # The target line that reconstructs the source meaning most closely
            # is selected. This reduces fluent-looking but unrelated subtitles.
            tokenizer.src_lang = target
            flat_candidates = [candidate for row in candidate_rows for candidate in row]
            back_encoded = [
                tokenizer.convert_ids_to_tokens(tokenizer.encode(text))
                for text in flat_candidates
            ]
            bengali_token = tokenizer.lang_code_to_token["bn"]
            back_results = translator.translate_batch(
                back_encoded,
                target_prefix=[[bengali_token]] * len(back_encoded),
                beam_size=4,
                max_decoding_length=160,
                repetition_penalty=1.05,
                no_repeat_ngram_size=3,
                disable_unk=True,
            )
            back_texts = [
                _decode_hypothesis(tokenizer, result.hypotheses[0], bengali_token)
                for result in back_results
            ]
            tokenizer.src_lang = "bn"
            back_index = 0
            for local_index, candidates in enumerate(candidate_rows):
                candidate_backs = back_texts[back_index : back_index + len(candidates)]
                chosen = _select_semantic_candidate(
                    batch[local_index], candidates, candidate_backs
                )
                output = _preserve_greeting(batch[local_index], chosen, target)
                translated.append(
                    _title_case_latin_words(output) if target == "en" else output
                )
                back_index += len(candidates)
            if progress:
                completed = min(len(source_texts), start + len(batch))
                progress(
                    completed / max(1, len(source_texts)),
                    f"Offline Translation চলছে—{completed}/{len(source_texts)} line",
                )
    except TranslationError:
        raise
    except Exception as exc:
        raise TranslationError(
            "Offline Translation সম্পন্ন হয়নি। অন্য ভারী Software বন্ধ করে আবার চেষ্টা করুন।"
        ) from exc

    if translated and all(_comparison_text(value) == _comparison_text(source_texts[index]) for index, value in enumerate(translated)):
        raise TranslationError(
            "নির্বাচিত ভাষায় অর্থপূর্ণ Translation তৈরি হয়নি। আবার চেষ্টা করুন।"
        )

    return [
        SubtitleSegment(item.start, item.end, translated[index] or item.text, item.text)
        for index, item in enumerate(segments)
    ]
