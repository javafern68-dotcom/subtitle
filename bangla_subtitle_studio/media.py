from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image


class MediaError(RuntimeError):
    pass


def _startupinfo() -> subprocess.STARTUPINFO | None:
    if os.name != "nt":
        return None
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return info


def bundled_tool(name: str) -> str:
    executable = name + (".exe" if os.name == "nt" else "")
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.extend(
            [
                Path(sys.executable).resolve().parent / "tools" / executable,
                Path(getattr(sys, "_MEIPASS", "")) / "tools" / executable,
            ]
        )
    candidates.append(Path(__file__).resolve().parent.parent / "tools" / executable)
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    found = shutil.which(name)
    if found:
        return found
    raise MediaError(
        f"{name} পাওয়া যায়নি। INSTALL_AND_RUN.bat আবার চালান অথবা FFmpeg ইনস্টল করুন।"
    )


def check_ffmpeg() -> tuple[str, str]:
    return bundled_tool("ffmpeg"), bundled_tool("ffprobe")


def probe_video(path: str) -> dict[str, float | int]:
    _, ffprobe = check_ffmpeg()
    command = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate:format=duration",
        "-of",
        "json",
        path,
    ]
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        startupinfo=_startupinfo(),
        check=False,
    )
    if completed.returncode != 0:
        raise MediaError(completed.stderr.decode("utf-8", "replace").strip() or "ভিডিও পড়া যায়নি।")
    try:
        data = json.loads(completed.stdout.decode("utf-8"))
        stream = data["streams"][0]
        numerator, denominator = str(stream.get("r_frame_rate", "25/1")).split("/", 1)
        fps = float(numerator) / max(float(denominator), 1e-9)
        return {
            "width": int(stream["width"]),
            "height": int(stream["height"]),
            "fps": fps,
            "duration": float(data.get("format", {}).get("duration", 0.0)),
        }
    except (KeyError, ValueError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise MediaError("ভিডিওর তথ্য পড়া যায়নি।") from exc


def extract_frame(path: str, seconds: float, width: int = 960, height: int = 540) -> Image.Image:
    ffmpeg, _ = check_ffmpeg()
    filter_text = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x101827"
    )
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{max(0.0, seconds):.3f}",
        "-i",
        path,
        "-frames:v",
        "1",
        "-vf",
        filter_text,
        "-f",
        "image2pipe",
        "-vcodec",
        "png",
        "pipe:1",
    ]
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        startupinfo=_startupinfo(),
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout:
        raise MediaError(completed.stderr.decode("utf-8", "replace").strip() or "Preview তৈরি হয়নি।")
    image = Image.open(io.BytesIO(completed.stdout))
    image.load()
    return image.convert("RGB")


def extract_audio_chunk(video_path: str, output_path: str, start: float, duration: float) -> None:
    ffmpeg, _ = check_ffmpeg()
    if Path(output_path).suffix.lower() == ".wav":
        codec_args = ["-c:a", "pcm_s16le"]
    else:
        codec_args = ["-c:a", "libmp3lame", "-b:a", "64k"]
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{max(0.0, start):.3f}",
        "-t",
        f"{max(0.1, duration):.3f}",
        "-i",
        video_path,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        *codec_args,
        output_path,
    ]
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        startupinfo=_startupinfo(),
        check=False,
    )
    if completed.returncode != 0:
        raise MediaError(completed.stderr.decode("utf-8", "replace").strip() or "অডিও তৈরি হয়নি।")
