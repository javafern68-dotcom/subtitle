from __future__ import annotations

import os
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Callable

from PIL import Image

from .media import MediaError, _startupinfo, bundled_tool, extract_frame
from .models import Project, TimelineClip, TimelineMedia, TimelineTrack
from .subtitles import write_ass


class TimelineExportError(RuntimeError):
    pass


ProgressCallback = Callable[[float, str], None]


def _filter_path(path: str) -> str:
    value = str(Path(path).resolve()).replace("\\", "/")
    return (
        value.replace("'", r"\'")
        .replace(":", r"\:")
        .replace("[", r"\[")
        .replace("]", r"\]")
        .replace(",", r"\,")
        .replace(";", r"\;")
    )


def _visible_clips(project: Project, kind: str) -> list[tuple[TimelineTrack, TimelineClip, TimelineMedia]]:
    timeline = project.timeline
    result: list[tuple[TimelineTrack, TimelineClip, TimelineMedia]] = []
    for track in timeline.tracks_of_kind(kind):
        if (kind == "video" and track.hidden) or (kind == "audio" and track.muted):
            continue
        clips = sorted(
            (clip for clip in timeline.clips if clip.track_id == track.id and clip.enabled),
            key=lambda clip: (clip.start, clip.id),
        )
        for clip in clips:
            media = timeline.media_by_id(clip.media_id)
            if media is not None:
                result.append((track, clip, media))
    return result


def build_timeline_export_command(
    project: Project,
    output_path: str,
    ass_path: str | None,
    quality: str = "Balanced",
) -> list[str]:
    try:
        ffmpeg = bundled_tool("ffmpeg")
    except MediaError as exc:
        raise TimelineExportError(str(exc)) from exc
    timeline = project.timeline
    duration = max(0.05, timeline.duration())
    width = max(320, int(timeline.width or project.width or 1920))
    height = max(180, int(timeline.height or project.height or 1080))
    fps = max(1.0, float(timeline.fps or project.fps or 25.0))
    video_clips = _visible_clips(project, "video")
    audio_clips = _visible_clips(project, "audio")
    command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    input_indices: dict[str, int] = {}
    input_index = 0
    all_clips = video_clips + audio_clips
    for _track, clip, media in all_clips:
        if not Path(media.path).is_file():
            raise TimelineExportError(f"Timeline media পাওয়া যায়নি: {media.path}")
        if media.kind == "image":
            command.extend(
                ["-loop", "1", "-framerate", f"{fps:.3f}", "-t", f"{clip.duration:.3f}", "-i", media.path]
            )
        else:
            command.extend(["-i", media.path])
        input_indices[clip.id] = input_index
        input_index += 1
    logo_index: int | None = None
    if project.logo.enabled and project.logo.path:
        if not Path(project.logo.path).is_file():
            raise TimelineExportError("লোগো ফাইল পাওয়া যায়নি।")
        command.extend(["-loop", "1", "-framerate", f"{fps:.3f}", "-t", f"{duration:.3f}", "-i", project.logo.path])
        logo_index = input_index

    graph: list[str] = [
        f"color=c=0x101010:s={width}x{height}:r={fps:.3f}:d={duration:.3f},format=yuv420p[vbase]"
    ]
    current_video = "vbase"
    for index, (_track, clip, _media) in enumerate(video_clips):
        source_index = input_indices[clip.id]
        opacity = max(0.0, min(1.0, clip.opacity))
        graph.append(
            f"[{source_index}:v]trim=start={max(0.0, clip.source_in):.3f}:duration={clip.duration:.3f},"
            f"setpts=PTS-STARTPTS+{clip.start:.3f}/TB,"
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,setsar=1,"
            f"format=yuva420p,colorchannelmixer=aa={opacity:.4f}[vclip{index}]"
        )
        graph.append(
            f"[{current_video}][vclip{index}]overlay=x=(main_w-overlay_w)/2:y=(main_h-overlay_h)/2:"
            f"eof_action=pass:shortest=0:enable='between(t,{clip.start:.3f},{clip.end:.3f})'[vcomp{index}]"
        )
        current_video = f"vcomp{index}"

    color = project.color
    filters = [
        "eq="
        f"brightness={max(-1.0, min(1.0, color.brightness)):.4f}:"
        f"contrast={max(0.1, min(3.0, color.contrast)):.4f}:"
        f"saturation={max(0.0, min(3.0, color.saturation)):.4f}"
    ]
    red = max(-1.0, min(1.0, color.temperature / 100.0))
    blue = -red
    green = max(-1.0, min(1.0, color.tint / 100.0))
    if abs(red) > 0.0001 or abs(green) > 0.0001:
        filters.append(f"colorbalance=rs={red:.4f}:gs={green:.4f}:bs={blue:.4f}")
    graph.append(f"[{current_video}]{','.join(filters)}[vcolor]")
    current_video = "vcolor"

    if logo_index is not None:
        logo = project.logo
        logo_width = max(16, round(width * logo.scale_percent / 100.0))
        opacity = max(0.0, min(1.0, logo.opacity / 100.0))
        end = duration if logo.end < 0 else min(duration, logo.end)
        graph.append(
            f"[{logo_index}:v]scale={logo_width}:-1,format=rgba,colorchannelmixer=aa={opacity:.4f}[logo]"
        )
        graph.append(
            f"[{current_video}][logo]overlay="
            f"x=(main_w-overlay_w)*{max(0.0, min(100.0, logo.x_percent)) / 100.0:.5f}:"
            f"y=(main_h-overlay_h)*{max(0.0, min(100.0, logo.y_percent)) / 100.0:.5f}:"
            f"enable='between(t,{max(0.0, logo.start):.3f},{max(0.0, end):.3f})'[vlogo]"
        )
        current_video = "vlogo"
    if ass_path and project.subtitles:
        graph.append(f"[{current_video}]subtitles=filename='{_filter_path(ass_path)}'[vout]")
        current_video = "vout"

    audio_labels: list[str] = []
    for index, (_track, clip, _media) in enumerate(audio_clips):
        source_index = input_indices[clip.id]
        chain = (
            f"[{source_index}:a]atrim=start={max(0.0, clip.source_in):.3f}:duration={clip.duration:.3f},"
            "asetpts=PTS-STARTPTS,"
            f"volume={max(0.0, min(4.0, clip.volume)):.4f}"
        )
        if clip.fade_in > 0:
            chain += f",afade=t=in:st=0:d={min(clip.fade_in, clip.duration):.3f}"
        if clip.fade_out > 0:
            fade_start = max(0.0, clip.duration - min(clip.fade_out, clip.duration))
            chain += f",afade=t=out:st={fade_start:.3f}:d={min(clip.fade_out, clip.duration):.3f}"
        delay_ms = max(0, round(clip.start * 1000))
        chain += f",adelay={delay_ms}:all=1[aclip{index}]"
        graph.append(chain)
        audio_labels.append(f"[aclip{index}]")
    if audio_labels:
        graph.append(
            f"{''.join(audio_labels)}amix=inputs={len(audio_labels)}:duration=longest:dropout_transition=0,"
            f"aresample=async=1:first_pts=0,atrim=duration={duration:.3f}[aout]"
        )
    else:
        graph.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={duration:.3f}[aout]")

    crf = {"High": "18", "Balanced": "21", "Small": "25", "Preview": "29"}.get(quality, "21")
    preset = "ultrafast" if quality == "Preview" else "medium"
    command.extend(
        [
            "-filter_complex",
            ";".join(graph),
            "-map",
            f"[{current_video}]",
            "-map",
            "[aout]",
            "-t",
            f"{duration:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            crf,
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-progress",
            "pipe:1",
            "-nostats",
            output_path,
        ]
    )
    return command


def export_timeline_project(
    project: Project,
    output_path: str,
    quality: str = "Balanced",
    progress: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
) -> None:
    if not project.timeline.has_clips():
        raise TimelineExportError("Timeline-এ কোনো clip নেই।")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    temp_output = str(Path(output_path).with_name(Path(output_path).stem + ".rendering.mp4"))
    Path(temp_output).unlink(missing_ok=True)
    duration = max(0.05, project.timeline.duration())
    with tempfile.TemporaryDirectory(prefix="bangla_timeline_export_") as temp_dir:
        ass_path: str | None = None
        if project.subtitles:
            ass_path = str(Path(temp_dir) / "subtitles.ass")
            write_ass(ass_path, project.subtitles, project.subtitle_style)
        command = build_timeline_export_command(project, temp_output, ass_path, quality)
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            startupinfo=_startupinfo(),
        )
        assert process.stdout is not None
        while True:
            if cancel_event and cancel_event.is_set():
                process.terminate()
                process.wait(timeout=10)
                Path(temp_output).unlink(missing_ok=True)
                raise TimelineExportError("Timeline Export বাতিল করা হয়েছে।")
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            key, _, value = line.strip().partition("=")
            if key in {"out_time_us", "out_time_ms"}:
                try:
                    seconds = float(value) / 1_000_000.0
                    ratio = min(0.995, seconds / duration)
                    if progress:
                        progress(ratio, f"Professional Timeline Export—{ratio * 100:.0f}%")
                except ValueError:
                    pass
        stderr = process.stderr.read() if process.stderr else ""
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()
        if process.returncode != 0:
            Path(temp_output).unlink(missing_ok=True)
            raise TimelineExportError(stderr.strip() or "Timeline Export করা যায়নি।")
    Path(output_path).unlink(missing_ok=True)
    os.replace(temp_output, output_path)
    if progress:
        progress(1.0, "Professional Timeline Export সম্পন্ন হয়েছে।")


def render_timeline_frame(project: Project, seconds: float, width: int = 960, height: int = 540) -> Image.Image:
    canvas = Image.new("RGB", (width, height), "#101010")
    timeline = project.timeline
    for track in timeline.tracks_of_kind("video"):
        if track.hidden:
            continue
        active = sorted(
            (
                clip
                for clip in timeline.clips
                if clip.track_id == track.id and clip.enabled and clip.start <= seconds < clip.end
            ),
            key=lambda clip: clip.id,
        )
        for clip in active:
            media = timeline.media_by_id(clip.media_id)
            if media is None or not Path(media.path).is_file():
                continue
            try:
                if media.kind == "image":
                    source = Image.open(media.path).convert("RGBA")
                    source.thumbnail((width, height), Image.Resampling.LANCZOS)
                    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                    layer.alpha_composite(source, ((width - source.width) // 2, (height - source.height) // 2))
                else:
                    source_time = clip.source_in + max(0.0, seconds - clip.start)
                    source_ratio = (media.width / media.height) if media.width and media.height else (width / height)
                    if source_ratio >= width / height:
                        frame_width = width
                        frame_height = max(1, round(width / source_ratio))
                    else:
                        frame_height = height
                        frame_width = max(1, round(height * source_ratio))
                    frame = extract_frame(
                        media.path,
                        source_time,
                        frame_width,
                        frame_height,
                    ).convert("RGBA")
                    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                    layer.alpha_composite(
                        frame,
                        ((width - frame.width) // 2, (height - frame.height) // 2),
                    )
                if clip.opacity < 1.0:
                    alpha = layer.getchannel("A").point(
                        lambda value: round(value * max(0.0, min(1.0, clip.opacity)))
                    )
                    layer.putalpha(alpha)
                canvas = Image.alpha_composite(canvas.convert("RGBA"), layer).convert("RGB")
            except (OSError, MediaError, ValueError):
                continue
    return canvas
