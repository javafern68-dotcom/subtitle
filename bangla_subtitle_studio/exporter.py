from __future__ import annotations

import os
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Callable

from .media import MediaError, _startupinfo, bundled_tool
from .models import Project
from .subtitles import write_ass


class ExportError(RuntimeError):
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


def build_filter_graph(project: Project, ass_path: str | None = None) -> tuple[str, str]:
    color = project.color
    video_filters = [
        (
            "eq="
            f"brightness={max(-1.0, min(1.0, color.brightness)):.4f}:"
            f"contrast={max(0.1, min(3.0, color.contrast)):.4f}:"
            f"saturation={max(0.0, min(3.0, color.saturation)):.4f}"
        )
    ]
    red = max(-1.0, min(1.0, color.temperature / 100.0))
    blue = -red
    green = max(-1.0, min(1.0, color.tint / 100.0))
    if abs(red) > 0.0001 or abs(green) > 0.0001:
        video_filters.append(f"colorbalance=rs={red:.4f}:gs={green:.4f}:bs={blue:.4f}")
    graph: list[str] = [f"[0:v]{','.join(video_filters)}[base]"]
    current = "base"
    logo = project.logo
    if logo.enabled and logo.path:
        target_width = max(16, round(project.width * logo.scale_percent / 100.0))
        opacity = max(0.0, min(1.0, logo.opacity / 100.0))
        end = project.duration if logo.end < 0 else min(project.duration, logo.end)
        graph.append(
            f"[1:v]scale={target_width}:-1,format=rgba,colorchannelmixer=aa={opacity:.4f}[logo]"
        )
        graph.append(
            f"[{current}][logo]overlay="
            f"x=(main_w-overlay_w)*{max(0.0, min(100.0, logo.x_percent)) / 100.0:.5f}:"
            f"y=(main_h-overlay_h)*{max(0.0, min(100.0, logo.y_percent)) / 100.0:.5f}:"
            f"enable='between(t,{max(0.0, logo.start):.3f},{max(0.0, end):.3f})'[withlogo]"
        )
        current = "withlogo"
    if ass_path and project.subtitles:
        graph.append(f"[{current}]subtitles=filename='{_filter_path(ass_path)}'[vout]")
        current = "vout"
    return ";".join(graph), current


def build_export_command(project: Project, output_path: str, ass_path: str | None) -> list[str]:
    try:
        ffmpeg = bundled_tool("ffmpeg")
    except MediaError as exc:
        raise ExportError(str(exc)) from exc
    command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", project.video_path]
    if project.logo.enabled and project.logo.path:
        command.extend(["-loop", "1", "-i", project.logo.path])
    graph, output_label = build_filter_graph(project, ass_path)
    quality = getattr(project, "export_quality", "Balanced")
    crf = {"High": "18", "Balanced": "21", "Small": "25"}.get(quality, "21")
    command.extend(
        [
            "-filter_complex",
            graph,
            "-map",
            f"[{output_label}]",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
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
            "-shortest",
            "-progress",
            "pipe:1",
            "-nostats",
            output_path,
        ]
    )
    return command


def export_project(
    project: Project,
    output_path: str,
    quality: str = "Balanced",
    progress: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
) -> None:
    if project.timeline.has_clips():
        from .timeline_exporter import export_timeline_project

        export_timeline_project(project, output_path, quality, progress, cancel_event)
        return
    if not project.video_path or not Path(project.video_path).is_file():
        raise ExportError("প্রথমে একটি ভিডিও নির্বাচন করুন।")
    if project.logo.enabled and project.logo.path and not Path(project.logo.path).is_file():
        raise ExportError("লোগো ফাইল পাওয়া যায়নি।")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    temp_output = str(Path(output_path).with_name(Path(output_path).stem + ".rendering.mp4"))
    if Path(temp_output).exists():
        Path(temp_output).unlink()
    with tempfile.TemporaryDirectory(prefix="bangla_export_") as temp_dir:
        ass_path: str | None = None
        if project.subtitles:
            ass_path = str(Path(temp_dir) / "subtitles.ass")
            write_ass(ass_path, project.subtitles, project.subtitle_style)
        project.export_quality = quality  # transient runtime setting
        command = build_export_command(project, temp_output, ass_path)
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
                if Path(temp_output).exists():
                    Path(temp_output).unlink()
                raise ExportError("ভিডিও Export বাতিল করা হয়েছে।")
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            key, _, value = line.strip().partition("=")
            if key in {"out_time_us", "out_time_ms"}:
                try:
                    raw = float(value)
                    seconds = raw / 1_000_000.0
                    ratio = min(0.995, seconds / max(project.duration, 0.1))
                    if progress:
                        progress(ratio, f"ভিডিও তৈরি হচ্ছে—{ratio * 100:.0f}%")
                except ValueError:
                    pass
        stderr = process.stderr.read() if process.stderr else ""
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()
        if process.returncode != 0:
            if Path(temp_output).exists():
                Path(temp_output).unlink()
            raise ExportError(stderr.strip() or "ভিডিও Export করা যায়নি।")
    if Path(output_path).exists():
        Path(output_path).unlink()
    os.replace(temp_output, output_path)
    if progress:
        progress(1.0, "ভিডিও Export সম্পন্ন হয়েছে।")
