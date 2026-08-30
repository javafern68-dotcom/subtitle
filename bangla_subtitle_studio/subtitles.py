from __future__ import annotations

import re
from pathlib import Path

from .models import SubtitleSegment, SubtitleStyle


TIMECODE_RE = re.compile(
    r"(?<!\d)(?:(?P<h>\d{1,4})\s*:\s*)?"
    r"(?P<m>\d{1,2})\s*:\s*(?P<s>\d{1,2})"
    r"(?:\s*[,.]\s*(?P<ms>\d{1,3}))?(?!\d)"
)
ARROW_RE = re.compile(r"\s*(?:-->|-+\s*>|→)\s*")


def parse_timecode(value: str) -> float:
    match = TIMECODE_RE.search(value.strip())
    if not match:
        raise ValueError(f"Invalid subtitle time: {value}")
    hours = int(match.group("h") or 0)
    minutes = int(match.group("m"))
    seconds = int(match.group("s"))
    fraction = match.group("ms") or "0"
    return hours * 3600 + minutes * 60 + seconds + int(fraction) / (10 ** len(fraction))


def format_srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def format_ass_time(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, centiseconds = divmod(centiseconds, 360_000)
    minutes, centiseconds = divmod(centiseconds, 6_000)
    secs, centiseconds = divmod(centiseconds, 100)
    return f"{hours:d}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def _decode_subtitle(data: bytes) -> str:
    """Decode subtitle output without rejecting a whole job for one bad byte."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    return data.decode("utf-8-sig", errors="replace")


def _timeline(line: str) -> tuple[float, float] | None:
    parts = ARROW_RE.split(line.strip(), maxsplit=1)
    if len(parts) != 2:
        return None
    try:
        start = parse_timecode(parts[0])
        end = parse_timecode(parts[1])
    except ValueError:
        return None
    return start, max(start + 0.05, end)


def parse_srt_text(text: str) -> list[SubtitleSegment]:
    """Read standard and mildly malformed Whisper SRT output.

    Some Whisper/model combinations omit blank lines, use a dot for
    milliseconds, or produce one damaged timestamp. Valid neighbouring cues
    must still be kept instead of rejecting the complete transcription.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    cue_rows: list[tuple[int, tuple[float, float] | None]] = []
    for index, line in enumerate(lines):
        if len(ARROW_RE.split(line.strip(), maxsplit=1)) == 2:
            cue_rows.append((index, _timeline(line)))

    result: list[SubtitleSegment] = []
    for cue_index, (line_index, timing) in enumerate(cue_rows):
        if timing is None:
            continue
        start, end = timing
        next_line_index = cue_rows[cue_index + 1][0] if cue_index + 1 < len(cue_rows) else len(lines)
        body_lines = [line.strip() for line in lines[line_index + 1 : next_line_index]]
        while body_lines and not body_lines[0]:
            body_lines.pop(0)
        while body_lines and not body_lines[-1]:
            body_lines.pop()
        # The next cue number belongs to the following timeline when SRT blocks
        # are not separated by a blank line.
        if body_lines and body_lines[-1].isdigit():
            body_lines.pop()
            while body_lines and not body_lines[-1]:
                body_lines.pop()
        body = "\n".join(line for line in body_lines if line).strip()
        if body:
            result.append(SubtitleSegment(start, end, body, "").normalized())
    return result


def parse_srt(path: str | Path) -> list[SubtitleSegment]:
    return parse_srt_text(_decode_subtitle(Path(path).read_bytes()))


def write_srt(path: str | Path, segments: list[SubtitleSegment], include_secondary: bool = True) -> None:
    blocks: list[str] = []
    for index, segment in enumerate(segments, 1):
        item = segment.normalized()
        body = item.text
        if include_secondary and item.secondary_text:
            body += "\n" + item.secondary_text
        blocks.append(
            f"{index}\n{format_srt_time(item.start)} --> {format_srt_time(item.end)}\n{body}"
        )
    Path(path).write_text("\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8-sig")


def _ass_color(hex_color: str, alpha: int = 0) -> str:
    value = hex_color.strip().lstrip("#")
    if len(value) != 6:
        value = "FFFFFF"
    red, green, blue = value[0:2], value[2:4], value[4:6]
    return f"&H{max(0, min(255, alpha)):02X}{blue}{green}{red}"


def _escape_ass(text: str) -> str:
    return (
        text.replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("\r", " ")
        .replace("\n", r"\N")
    )


def wrap_words(text: str, max_chars: int) -> str:
    words = text.replace("\n", " ").split()
    if not words or max_chars <= 0:
        return text.strip()
    lines: list[str] = []
    current: list[str] = []
    length = 0
    for word in words:
        next_length = length + (1 if current else 0) + len(word)
        if current and next_length > max_chars:
            lines.append(" ".join(current))
            current = [word]
            length = len(word)
        else:
            current.append(word)
            length = next_length
    if current:
        lines.append(" ".join(current))
    return "\n".join(lines)


def write_ass(
    path: str | Path,
    segments: list[SubtitleSegment],
    style: SubtitleStyle,
    play_res_x: int = 1920,
    play_res_y: int = 1080,
) -> None:
    alignment = {"top": 8, "middle": 5, "bottom": 2}.get(style.position, 2)
    border_style = 3 if style.background else 1
    back_alpha = 100 if style.background else 0
    outline = max(0, int(style.outline))
    bold = -1 if style.bold else 0
    header = f"""[Script Info]
ScriptType: v4.00+
Collisions: Normal
PlayResX: {play_res_x}
PlayResY: {play_res_y}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style.font_name},{int(style.font_size)},{_ass_color(style.primary_color)},{_ass_color(style.secondary_color)},{_ass_color(style.outline_color)},{_ass_color(style.background_color, back_alpha)},{bold},0,0,0,100,100,0,0,{border_style},{outline},{max(0, int(style.shadow))},{alignment},40,40,{max(0, int(style.margin_v))},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines: list[str] = [header.rstrip()]
    for segment in segments:
        item = segment.normalized()
        primary = _escape_ass(wrap_words(item.text, style.max_chars)).replace("\n", r"\N")
        body = primary
        if style.show_secondary and item.secondary_text:
            secondary = _escape_ass(wrap_words(item.secondary_text, style.max_chars)).replace("\n", r"\N")
            secondary_bgr = _ass_color(style.secondary_color)[4:]
            body += rf"\N{{\c&H{secondary_bgr}&}}{secondary}"
        lines.append(
            f"Dialogue: 0,{format_ass_time(item.start)},{format_ass_time(item.end)},Default,,0,0,0,,{body}"
        )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def split_for_readability(
    segments: list[SubtitleSegment], max_words: int = 12, max_duration: float = 6.0
) -> list[SubtitleSegment]:
    result: list[SubtitleSegment] = []
    for segment in segments:
        item = segment.normalized()
        words = item.text.split()
        desired_parts = max(
            1,
            (len(words) + max_words - 1) // max_words,
            int((item.end - item.start + max_duration - 0.001) // max_duration),
        )
        desired_parts = min(desired_parts, max(1, len(words)))
        if desired_parts <= 1:
            result.append(item)
            continue
        for part in range(desired_parts):
            word_start = round(part * len(words) / desired_parts)
            word_end = round((part + 1) * len(words) / desired_parts)
            start = item.start + (item.end - item.start) * word_start / len(words)
            end = item.start + (item.end - item.start) * word_end / len(words)
            result.append(SubtitleSegment(start, end, " ".join(words[word_start:word_end])))
    return [item for item in result if item.text.strip()]
