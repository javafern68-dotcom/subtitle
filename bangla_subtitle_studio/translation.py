from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Callable

from .models import SubtitleSegment


class TranslationError(RuntimeError):
    pass


TranslationProgress = Callable[[float, str], None]
TRANSLATION_MODEL_DIR = "m2m100-418M-int8"


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
    shifted: list[SubtitleSegment] = []
    for item in segments:
        start = max(0.0, item.start - lead)
        end = max(start + 0.05, item.end - lead)
        shifted.append(SubtitleSegment(start, end, item.text, item.secondary_text))
    return shifted


def _avro_reverse(texts: list[str]) -> list[str]:
    try:
        import avro
    except ImportError as exc:
        raise TranslationError("Avro converter পাওয়া যায়নি। Software আবার Install করুন।") from exc
    return [str(value).strip() for value in avro.reverse_iter(texts)]


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
        converted = _avro_reverse(source_texts)
        if progress:
            progress(1.0, "Avro/Banglish subtitle তৈরি হয়েছে")
        return [
            SubtitleSegment(item.start, item.end, converted[index] or item.text, item.text)
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
        batch_size = 24
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
                beam_size=5,
                patience=1.0,
                max_decoding_length=128,
            )
            for result in results:
                token_ids = tokenizer.convert_tokens_to_ids(result.hypotheses[0][1:])
                translated.append(tokenizer.decode(token_ids, skip_special_tokens=True).strip())
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

    return [
        SubtitleSegment(item.start, item.end, translated[index] or item.text, item.text)
        for index, item in enumerate(segments)
    ]
