from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import tempfile
import threading
import unicodedata
import wave
from pathlib import Path
from typing import Callable

from .media import _startupinfo, bundled_tool


class OrganicVoiceError(RuntimeError):
    pass


OrganicProgress = Callable[[float, str], None]

ORGANIC_MODEL_DIR = "organic-vits-rasa-13"
ORGANIC_MODEL_NAME = "vits_tts_q8.mnn"
ORGANIC_VOCAB_NAME = "vocab.json"
ORGANIC_SAMPLE_RATE = 24_000
ORGANIC_VOICE_OPTIONS = {
    "bn": [
        ("organic:bn:female", "Organic বাংলা নারী কণ্ঠ • Offline CPU"),
        ("organic:bn:male", "Organic বাংলা পুরুষ কণ্ঠ • Offline CPU"),
    ]
}

_SPEAKER_IDS = {
    "organic:bn:female": 2,
    "organic:bn:male": 3,
}
_STYLE_IDS = {
    "natural": 4,  # CONV
    "happy": 8,
    "loving": 3,  # BOOK: softer, longer-form delivery
    "angry": 1,
    "sad": 12,
    "serious": 10,  # NEWS
    "storytelling": 3,  # BOOK
}
_STYLE_PAUSES_MS = {
    "natural": 140,
    "happy": 90,
    "loving": 220,
    "angry": 80,
    "sad": 260,
    "serious": 180,
    "storytelling": 220,
}

_SESSION: "OrganicVitsSession | None" = None
_SESSION_KEY: tuple[str, str] | None = None
_SESSION_LOCK = threading.Lock()
_RUNTIME_STREAMS: list[object] = []


def _application_roots() -> list[Path]:
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
        meipass = str(getattr(sys, "_MEIPASS", "")).strip()
        if meipass:
            roots.append(Path(meipass))
    roots.append(Path(__file__).resolve().parent.parent)
    return roots


def organic_model_components() -> tuple[str, str]:
    configured_model = os.environ.get("BSS_ORGANIC_TTS_MODEL", "").strip()
    configured_vocab = os.environ.get("BSS_ORGANIC_TTS_VOCAB", "").strip()
    if configured_model and configured_vocab:
        if Path(configured_model).is_file() and Path(configured_vocab).is_file():
            return configured_model, configured_vocab
    for root in _application_roots():
        directory = root / "models" / ORGANIC_MODEL_DIR
        model = directory / ORGANIC_MODEL_NAME
        vocab = directory / ORGANIC_VOCAB_NAME
        if model.is_file() and vocab.is_file():
            return str(model), str(vocab)
    raise OrganicVoiceError(
        "Organic বাংলা AI Voice model পাওয়া যায়নি। V3.5 Organic CPU installer আবার Install করুন।"
    )


def _ensure_runtime_streams() -> None:
    """Native MNN builds may log during import even in a windowed application."""
    for name in ("stdout", "stderr"):
        if getattr(sys, name, None) is None:
            stream = open(os.devnull, "w", encoding="utf-8", errors="replace")
            _RUNTIME_STREAMS.append(stream)
            setattr(sys, name, stream)


def load_vocab(vocab_path: str | Path) -> dict[str, int]:
    try:
        with Path(vocab_path).open(encoding="utf-8") as handle:
            values = json.load(handle)
    except (OSError, ValueError) as exc:
        raise OrganicVoiceError("Organic Voice vocabulary পড়া যায়নি।") from exc
    if not isinstance(values, dict) or " " not in values or "আ" not in values:
        raise OrganicVoiceError("Organic Voice vocabulary সঠিক নয়।")
    return {str(key): int(value) for key, value in values.items()}


def normalize_organic_text(text: str, vocab: dict[str, int]) -> str:
    normalized = unicodedata.normalize("NFC", str(text)).lower()
    normalized = "".join(char if char in vocab else " " for char in normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def tokenize_organic_text(text: str, vocab: dict[str, int]) -> "object":
    import numpy as np

    filtered = normalize_organic_text(text, vocab)
    if not filtered:
        raise OrganicVoiceError(
            "Organic Voice-এর জন্য বাংলা অক্ষরে script লিখুন।"
        )
    token_ids = [vocab[char] for char in filtered]
    interspersed = [0] * (len(token_ids) * 2 + 1)
    interspersed[1::2] = token_ids
    return np.asarray([interspersed], dtype=np.int32)


def split_organic_text(text: str, max_chars: int = 220) -> list[str]:
    limit = max(80, min(320, int(max_chars)))
    normalized = re.sub(r"[ \t]+", " ", str(text).replace("\r", "\n")).strip()
    pieces = [
        item.strip()
        for item in re.split(r"(?<=[.!?।])\s+|\n+", normalized)
        if item.strip()
    ]
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        while len(piece) > limit:
            cut = piece.rfind(" ", 0, limit + 1)
            if cut < limit // 3:
                cut = limit
            prefix, piece = piece[:cut].strip(), piece[cut:].strip()
            if current:
                chunks.append(current)
                current = ""
            if prefix:
                chunks.append(prefix)
        candidate = f"{current} {piece}".strip() if current else piece
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = piece
    if current:
        chunks.append(current)
    return chunks


class OrganicVitsSession:
    def __init__(self, model_path: str, vocab_path: str) -> None:
        _ensure_runtime_streams()
        try:
            import MNN.expr as expr
            import MNN.nn as nn
        except Exception as exc:
            raise OrganicVoiceError(
                "Organic CPU Voice engine চালু হয়নি। V3.5 installer আবার Install করুন।"
            ) from exc
        self.expr = expr
        self.vocab = load_vocab(vocab_path)
        try:
            self.graph_vars = expr.load_as_dict(model_path)
            required = {"input_ids", "attention_mask", "speaker_id", "emotion_id"}
            missing = required.difference(self.graph_vars)
            if missing:
                raise ValueError(f"missing MNN inputs: {sorted(missing)}")
            self.module = nn.load_module_from_file(
                model_path,
                ["input_ids", "attention_mask", "speaker_id", "emotion_id"],
                ["waveform"],
                dynamic=True,
            )
        except Exception as exc:
            raise OrganicVoiceError(
                "Organic বাংলা AI model load হয়নি। Installer আবার Install করুন।"
            ) from exc

    def _placeholder(self, value: "object", input_name: str) -> "object":
        reference = self.graph_vars[input_name]
        placeholder = self.expr.placeholder(
            list(value.shape), reference.data_format, reference.dtype
        )
        placeholder.write(value)
        return placeholder

    def synthesize(self, text: str, speaker_id: int, style_id: int) -> "object":
        import numpy as np

        input_ids = tokenize_organic_text(text, self.vocab)
        attention_mask = np.ones_like(input_ids, dtype=np.int32)
        speaker = np.asarray([speaker_id], dtype=np.int32)
        emotion = np.asarray([style_id], dtype=np.int32)
        try:
            outputs = self.module.forward(
                [
                    self._placeholder(input_ids, "input_ids"),
                    self._placeholder(attention_mask, "attention_mask"),
                    self._placeholder(speaker, "speaker_id"),
                    self._placeholder(emotion, "emotion_id"),
                ]
            )
            if not outputs:
                raise RuntimeError("MNN returned no audio")
            waveform = np.asarray(outputs[0].read(), dtype=np.float32).reshape(-1)
        except Exception as exc:
            raise OrganicVoiceError(
                "Organic Voice এই বাক্যটি তৈরি করতে পারেনি। বাক্য একটু ছোট করে আবার চেষ্টা করুন।"
            ) from exc
        waveform = np.nan_to_num(waveform, nan=0.0, posinf=1.0, neginf=-1.0)
        if waveform.size < ORGANIC_SAMPLE_RATE // 20:
            raise OrganicVoiceError("Organic Voice থেকে কোনো শব্দ তৈরি হয়নি।")
        return np.clip(waveform, -1.0, 1.0)


def _get_session() -> OrganicVitsSession:
    global _SESSION, _SESSION_KEY
    model_path, vocab_path = organic_model_components()
    key = (str(Path(model_path).resolve()), str(Path(vocab_path).resolve()))
    with _SESSION_LOCK:
        if _SESSION is None or _SESSION_KEY != key:
            _SESSION = OrganicVitsSession(model_path, vocab_path)
            _SESSION_KEY = key
        return _SESSION


def _write_wav(path: str | Path, waveform: "object") -> None:
    import numpy as np

    pcm = (np.clip(waveform, -1.0, 1.0) * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(ORGANIC_SAMPLE_RATE)
        writer.writeframes(pcm.tobytes())


def _atempo_expression(speed: float) -> str:
    value = max(0.25, min(4.0, float(speed)))
    factors: list[float] = []
    while value < 0.5:
        factors.append(0.5)
        value /= 0.5
    while value > 2.0:
        factors.append(2.0)
        value /= 2.0
    factors.append(value)
    return ",".join(f"atempo={factor:.5f}" for factor in factors)


def _encode_organic_mp3(
    source_wav: str,
    destination_mp3: str,
    rate_percent: int,
    pitch_hz: int,
) -> None:
    ffmpeg = bundled_tool("ffmpeg")
    speed = max(0.50, min(2.0, 1.0 + int(rate_percent) / 100.0))
    pitch_factor = max(0.85, min(1.15, 1.0 + int(pitch_hz) / 300.0))
    filters: list[str] = []
    if abs(pitch_factor - 1.0) > 0.001:
        filters.extend(
            [
                f"asetrate={ORGANIC_SAMPLE_RATE}*{pitch_factor:.6f}",
                f"aresample={ORGANIC_SAMPLE_RATE}",
            ]
        )
    effective_atempo = speed / pitch_factor
    if abs(effective_atempo - 1.0) > 0.001:
        filters.append(_atempo_expression(effective_atempo))
    filters.append("loudnorm=I=-18:TP=-2:LRA=11")
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        source_wav,
        "-af",
        ",".join(filters),
        "-ac",
        "1",
        "-ar",
        str(ORGANIC_SAMPLE_RATE),
        "-c:a",
        "libmp3lame",
        "-b:a",
        "192k",
        destination_mp3,
    ]
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        startupinfo=_startupinfo(),
        check=False,
    )
    if completed.returncode != 0 or not Path(destination_mp3).is_file():
        raise OrganicVoiceError(
            completed.stderr.decode("utf-8", "replace").strip()
            or "Organic Voice MP3 encode হয়নি।"
        )


def organic_voice_settings(
    language: str,
    voice_id: str,
    emotion: str,
    emotion_strength: int = 65,
) -> tuple[int, int, int]:
    if str(language).strip().lower() != "bn":
        raise OrganicVoiceError(
            "Organic CPU Voice বর্তমানে বাংলা script-এর জন্য। English/Hindi/Arabic/Urdu-তে Microsoft Natural Online নির্বাচন করুন।"
        )
    voice = str(voice_id).strip().lower()
    if voice not in _SPEAKER_IDS:
        raise OrganicVoiceError("Organic বাংলা নারী অথবা পুরুষ কণ্ঠ নির্বাচন করুন।")
    style = str(emotion).strip().lower() or "natural"
    if style not in _STYLE_IDS:
        raise OrganicVoiceError("নির্বাচিত Organic Emotion সমর্থিত নয়।")
    strength = max(0, min(100, int(round(emotion_strength))))
    # At very low strength retain the conversational style. Native categorical
    # styles are used from medium strength upward; they are not fake pitch-only
    # effects like the online free endpoint.
    style_id = _STYLE_IDS[style] if strength >= 30 else _STYLE_IDS["natural"]
    pause_ms = int(
        round(120 + (_STYLE_PAUSES_MS[style] - 120) * (strength / 100.0))
    )
    return _SPEAKER_IDS[voice], style_id, max(60, min(300, pause_ms))


def create_organic_text_voice(
    text: str,
    language: str,
    voice_id: str,
    output_path: str,
    rate_percent: int = 0,
    pitch_hz: int = 0,
    emotion: str = "natural",
    emotion_strength: int = 65,
    natural_pauses: bool = True,
    progress: OrganicProgress | None = None,
    cancel_event: threading.Event | None = None,
) -> str:
    import numpy as np

    script = str(text).strip()
    if not script:
        raise OrganicVoiceError("Text To Voice ঘরে বাংলা script লিখুন।")
    if len(script) > 50_000:
        raise OrganicVoiceError(
            "Organic CPU Voice-এ একবারে সর্বোচ্চ ৫০,০০০ অক্ষরের script দিন।"
        )
    speaker_id, style_id, pause_ms = organic_voice_settings(
        language, voice_id, emotion, emotion_strength
    )
    chunks = split_organic_text(script)
    if not chunks:
        raise OrganicVoiceError("Organic Voice তৈরি করার মতো বাংলা লেখা পাওয়া যায়নি।")
    destination = Path(output_path)
    if destination.suffix.lower() != ".mp3":
        destination = destination.with_suffix(".mp3")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if progress:
        progress(0.02, "Organic CPU AI model load হচ্ছে—প্রথমবার একটু সময় লাগবে…")
    session = _get_session()
    waveforms: list[object] = []
    silence = np.zeros(
        int(ORGANIC_SAMPLE_RATE * pause_ms / 1000.0), dtype=np.float32
    )
    for index, chunk in enumerate(chunks):
        if cancel_event and cancel_event.is_set():
            raise OrganicVoiceError("Organic Text To Voice বাতিল করা হয়েছে।")
        waveform = session.synthesize(chunk, speaker_id, style_id)
        waveforms.append(waveform)
        if natural_pauses and index + 1 < len(chunks):
            waveforms.append(silence)
        if progress:
            progress(
                0.08 + 0.80 * (index + 1) / len(chunks),
                f"Organic CPU Voice—{index + 1}/{len(chunks)} বাক্য তৈরি হয়েছে",
            )
    combined = np.concatenate(waveforms)
    if not combined.size or not math.isfinite(float(np.max(np.abs(combined)))):
        raise OrganicVoiceError("Organic Voice audio সঠিক হয়নি।")
    with tempfile.TemporaryDirectory(
        prefix="bangla_organic_voice_", dir=str(destination.parent)
    ) as temp_dir:
        wav_path = str(Path(temp_dir) / "organic_complete.wav")
        mp3_path = str(Path(temp_dir) / "organic_complete.mp3")
        _write_wav(wav_path, combined)
        if progress:
            progress(0.90, "Organic Voice-এর Speed, Pitch ও loudness ঠিক হচ্ছে…")
        _encode_organic_mp3(
            wav_path,
            mp3_path,
            max(-50, min(100, int(round(rate_percent)))),
            max(-50, min(50, int(round(pitch_hz)))),
        )
        os.replace(mp3_path, destination)
    if not destination.is_file() or destination.stat().st_size < 1_000:
        raise OrganicVoiceError("Organic Voice MP3 তৈরি হয়নি।")
    if progress:
        progress(1.0, "Offline Organic বাংলা Voice MP3 তৈরি হয়েছে।")
    return "organic"
