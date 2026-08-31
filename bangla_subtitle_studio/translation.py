from __future__ import annotations

import os
import html
import json
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
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
    "bn": "আসসালামু আলাইকুম",
    "en": "Assalamu Alaikum",
    "hi": "अस्सलामु अलैकुम",
    "ar": "السلام عليكم",
    "ur": "السلام علیکم",
}
_ANY_GREETING_RE = re.compile(
    r"আস+সালামু[য়য়]?[া ]*আলাইকুম|আসসালামু\s+আলাইকুম|"
    r"ass?alamu\s+alaikum|अस्स?लामु\s+अलैकुम|السلام\s+عليكم",
    re.IGNORECASE,
)
_TARGET_SCRIPT_PATTERNS = {
    "bn": re.compile(r"[\u0980-\u09FF]"),
    "hi": re.compile(r"[\u0900-\u097F]"),
    "ne": re.compile(r"[\u0900-\u097F]"),
    "pa": re.compile(r"[\u0A00-\u0A7F]"),
    "ta": re.compile(r"[\u0B80-\u0BFF]"),
    "te": re.compile(r"[\u0C00-\u0C7F]"),
    "gu": re.compile(r"[\u0A80-\u0AFF]"),
    "ar": re.compile(r"[\u0600-\u06FF]"),
    "ur": re.compile(r"[\u0600-\u06FF]"),
    "fa": re.compile(r"[\u0600-\u06FF]"),
    "ru": re.compile(r"[\u0400-\u04FF]"),
    "zh": re.compile(r"[\u3400-\u9FFF]"),
    "ja": re.compile(r"[\u3040-\u30FF\u3400-\u9FFF]"),
    "ko": re.compile(r"[\uAC00-\uD7AF]"),
    "en": re.compile(r"[A-Za-z]"),
}
_GOOGLE_LANGUAGE_CODES = {"zh": "zh-CN"}
_GOOGLE_TRANSLATE_ENDPOINTS = (
    "https://translate.googleapis.com/translate_a/single",
    "https://translate.google.com/translate_a/single",
)
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
    if not _ANY_GREETING_RE.search(source):
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


def _valid_target_script(source: str, translated: str, target: str) -> bool:
    clean = " ".join(str(translated).split()).strip()
    if not clean or len(clean) > 5_000 or "<html" in clean.casefold():
        return False
    pattern = _TARGET_SCRIPT_PATTERNS.get(target)
    if pattern and not pattern.search(clean):
        return False
    return _comparison_text(clean) != _comparison_text(source)


def _google_translate_text(text: str, source: str, target: str) -> str:
    parameters = {
        "client": "gtx",
        "sl": _GOOGLE_LANGUAGE_CODES.get(source, source),
        "tl": _GOOGLE_LANGUAGE_CODES.get(target, target),
        "dt": "t",
        "q": text,
    }
    last_error: Exception | None = None
    for endpoint in _GOOGLE_TRANSLATE_ENDPOINTS:
        for attempt in range(2):
            try:
                request = urllib.request.Request(
                    endpoint + "?" + urllib.parse.urlencode(parameters),
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 Chrome/151 Safari/537.36"
                        )
                    },
                )
                with urllib.request.urlopen(request, timeout=15) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                translated = "".join(
                    str(part[0])
                    for part in (payload[0] if payload and payload[0] else [])
                    if part and part[0]
                )
                translated = html.unescape(translated).strip()
                if _valid_target_script(text, translated, target):
                    return translated
                raise TranslationError("Online translation-এর ভাষার অক্ষর সঠিক হয়নি।")
            except Exception as exc:
                last_error = exc
                if attempt == 0:
                    time.sleep(0.5)
    raise TranslationError("Online Accurate translation service পাওয়া যায়নি।") from last_error


def _google_translate_texts(texts: list[str], source: str, target: str) -> list[str]:
    if not texts:
        return []
    if len(texts) == 1:
        return [_google_translate_text(texts[0], source, target)]
    markers = [f"[[[BSSSEG{index:04d}]]]" for index in range(len(texts))]
    combined = "\n".join(
        f"{markers[index]} {value}" for index, value in enumerate(texts)
    )
    translated = _google_translate_text(combined, source, target)
    marker_pattern = re.compile(r"\[\[\[\s*BSSSEG(\d{4})\s*\]\]\]", re.IGNORECASE)
    matches = list(marker_pattern.finditer(translated))
    if len(matches) != len(texts):
        raise TranslationError("Online translation বাক্যের সীমা ঠিক রাখেনি।")
    outputs = [""] * len(texts)
    for match_index, match in enumerate(matches):
        item_index = int(match.group(1))
        if item_index < 0 or item_index >= len(texts):
            raise TranslationError("Online translation বাক্যের নম্বর বদলে দিয়েছে।")
        start = match.end()
        end = matches[match_index + 1].start() if match_index + 1 < len(matches) else len(translated)
        output = translated[start:end].strip()
        if not _valid_target_script(texts[item_index], output, target):
            raise TranslationError("Online translation-এর একটি বাক্য সঠিক ভাষায় নেই।")
        outputs[item_index] = output
    if any(not value for value in outputs):
        raise TranslationError("Online translation-এর সব বাক্য পাওয়া যায়নি।")
    return outputs


def translate_voice_segments(
    segments: list[SubtitleSegment],
    target_language: str,
    progress: TranslationProgress | None = None,
    cancel_event: threading.Event | None = None,
    source_language: str = "bn",
) -> list[SubtitleSegment]:
    """Use fast high-quality online translation, with the bundled model as fallback."""
    target = target_language.strip().lower()
    source = source_language.strip().lower()
    if target == source:
        return [SubtitleSegment(item.start, item.end, item.text, "") for item in segments]
    if progress:
        progress(0.02, "Accurate Online Translation প্রস্তুত হচ্ছে…")
    translated: list[str] = []
    try:
        source_texts = [item.text.strip() for item in segments]
        batches: list[tuple[int, list[str]]] = []
        start = 0
        while start < len(source_texts):
            end = start
            used = 0
            while end < len(source_texts):
                additional = len(source_texts[end]) + 24
                if end > start and used + additional > 3_000:
                    break
                used += additional
                end += 1
            batches.append((start, source_texts[start:end]))
            start = end
        for batch_index, (batch_start, batch) in enumerate(batches):
            if cancel_event and cancel_event.is_set():
                raise TranslationError("Voice Translation বাতিল করা হয়েছে।")
            outputs = _google_translate_texts(batch, source, target)
            for local_index, output in enumerate(outputs):
                source_text = batch[local_index]
                output = _preserve_greeting(source_text, output, target)
                if target == "en":
                    output = _title_case_latin_words(output)
                translated.append(output)
            if progress:
                completed = batch_start + len(batch)
                progress(
                    completed / max(1, len(segments)),
                    f"Accurate Online Translation—{completed}/{len(segments)} বাক্য",
                )
            if batch_index + 1 < len(batches):
                time.sleep(1.5)
        return [
            SubtitleSegment(item.start, item.end, translated[index], item.text)
            for index, item in enumerate(segments)
        ]
    except TranslationError:
        if progress:
            progress(0.05, "Online Translation পাওয়া যায়নি—Offline AI fallback চলছে…")

        def offline_progress(value: float, message: str) -> None:
            if progress:
                progress(0.05 + value * 0.95, message)

        return translate_segments(
            segments,
            target,
            offline_progress,
            cancel_event,
            source_language=source,
        )


def _decode_hypothesis(tokenizer: object, tokens: list[str], prefix: str) -> str:
    output_tokens = tokens[1:] if tokens and tokens[0] == prefix else tokens
    token_ids = tokenizer.convert_tokens_to_ids(output_tokens)
    return tokenizer.decode(token_ids, skip_special_tokens=True).strip()


def translate_segments(
    segments: list[SubtitleSegment],
    target_language: str,
    progress: TranslationProgress | None = None,
    cancel_event: threading.Event | None = None,
    source_language: str = "bn",
) -> list[SubtitleSegment]:
    target = target_language.strip().lower()
    source = source_language.strip().lower()
    if target == source:
        return [SubtitleSegment(item.start, item.end, item.text, "") for item in segments]

    source_texts = [item.text.strip() for item in segments]
    if target == "avro":
        if source != "bn":
            raise TranslationError("Avro/Banglish শুধু বাংলা source voice-এর জন্য ব্যবহার করুন।")
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
        if source not in tokenizer.lang_code_to_token:
            raise TranslationError("মূল voice-এর নির্বাচিত ভাষাটি Translation model-এ নেই।")
        tokenizer.src_lang = source
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

            # Translate both candidates back to the selected source language.
            # The candidate that reconstructs the original meaning most closely
            # is selected. This reduces fluent-looking but unrelated dubbing.
            tokenizer.src_lang = target
            flat_candidates = [candidate for row in candidate_rows for candidate in row]
            back_encoded = [
                tokenizer.convert_ids_to_tokens(tokenizer.encode(text))
                for text in flat_candidates
            ]
            source_token = tokenizer.lang_code_to_token[source]
            back_results = translator.translate_batch(
                back_encoded,
                target_prefix=[[source_token]] * len(back_encoded),
                beam_size=4,
                max_decoding_length=160,
                repetition_penalty=1.05,
                no_repeat_ngram_size=3,
                disable_unk=True,
            )
            back_texts = [
                _decode_hypothesis(tokenizer, result.hypotheses[0], source_token)
                for result in back_results
            ]
            tokenizer.src_lang = source
            back_index = 0
            for local_index, candidates in enumerate(candidate_rows):
                candidate_backs = back_texts[back_index : back_index + len(candidates)]
                chosen = _select_semantic_candidate(
                    batch[local_index], candidates, candidate_backs
                )
                output = (
                    _preserve_greeting(batch[local_index], chosen, target)
                    if source == "bn"
                    else chosen
                )
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
