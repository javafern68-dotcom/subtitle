from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SubtitleSegment:
    start: float
    end: float
    text: str
    secondary_text: str = ""

    def normalized(self) -> "SubtitleSegment":
        start = max(0.0, float(self.start))
        end = max(start + 0.05, float(self.end))
        return SubtitleSegment(start, end, self.text.strip(), self.secondary_text.strip())


@dataclass
class SubtitleStyle:
    font_name: str = "Nirmala UI"
    font_size: int = 58
    primary_color: str = "#FFFFFF"
    secondary_color: str = "#FFD966"
    outline_color: str = "#000000"
    background_color: str = "#000000"
    outline: int = 4
    shadow: int = 1
    bold: bool = True
    background: bool = False
    position: str = "bottom"
    margin_v: int = 70
    max_chars: int = 42
    show_secondary: bool = True


@dataclass
class LogoSettings:
    path: str = ""
    enabled: bool = False
    scale_percent: float = 18.0
    x_percent: float = 78.0
    y_percent: float = 5.0
    opacity: float = 90.0
    start: float = 0.0
    end: float = -1.0


@dataclass
class ColorSettings:
    preset: str = "Natural"
    brightness: float = 0.0
    contrast: float = 1.0
    saturation: float = 1.0
    temperature: float = 0.0
    tint: float = 0.0


@dataclass
class Project:
    video_path: str = ""
    output_path: str = ""
    duration: float = 0.0
    width: int = 1920
    height: int = 1080
    fps: float = 25.0
    subtitles: list[SubtitleSegment] = field(default_factory=list)
    subtitle_style: SubtitleStyle = field(default_factory=SubtitleStyle)
    logo: LogoSettings = field(default_factory=LogoSettings)
    color: ColorSettings = field(default_factory=ColorSettings)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        project = cls(
            video_path=str(data.get("video_path", "")),
            output_path=str(data.get("output_path", "")),
            duration=float(data.get("duration", 0.0)),
            width=int(data.get("width", 1920)),
            height=int(data.get("height", 1080)),
            fps=float(data.get("fps", 25.0)),
        )
        project.subtitles = [SubtitleSegment(**item).normalized() for item in data.get("subtitles", [])]
        project.subtitle_style = SubtitleStyle(**data.get("subtitle_style", {}))
        project.logo = LogoSettings(**data.get("logo", {}))
        project.color = ColorSettings(**data.get("color", {}))
        return project

    def default_output_path(self) -> str:
        if not self.video_path:
            return ""
        source = Path(self.video_path)
        return str(source.with_name(f"{source.stem}_বাংলা_সাবটাইটেল.mp4"))

