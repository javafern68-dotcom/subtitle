from __future__ import annotations

import re
from pathlib import Path

from .models import SubtitleSegment, SubtitleStyle


TIMECODE_RE = re.compile(
    r"(?P<h>\d{1,2}):(?P<m>\d{2}):(?P<s>\d{2})[,.](?P<ms>\d{1,3})"
)


def parse_timecode(value: str) -> float:
    match = TIMECODE_RE.search(value.strip())
    if not match:
        raise ValueError(f"Invalid subtitle time: {value}")
    parts = {key: int(number) for key, number in match.groupdict().items()}
    return parts["h"] * 3600 + parts["m"] * 60 + parts["s"] + parts["ms"] / (10 ** len(match.group("ms")))


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


def parse_srt(path: str | Path) -> list[SubtitleSegment]:
    text = Path(path).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    blocks = re.split(r"\n\s*\n", text.strip()) if text.strip() else []
    result: list[SubtitleSegment] = []
    for block in blocks:
        lines = [line.rstrip() for line in block.splitlines()]
        time_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if time_index is None:
            continue
        start_text, end_text = lines[time_index].split("-->", 1)
        body = "\n".join(lines[time_index + 1 :]).strip()
        if not body:
            continue
        result.append(
            SubtitleSegment(
                parse_timecode(start_text),
                parse_timecode(end_text),
                body,
                "",
            ).normalized()
        )
    return result


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
