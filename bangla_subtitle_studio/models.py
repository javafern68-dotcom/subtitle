from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4


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
    max_chars: int = 70
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


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


@dataclass
class TimelineMedia:
    id: str = field(default_factory=lambda: _new_id("media"))
    path: str = ""
    name: str = ""
    kind: str = "video"
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    has_video: bool = True
    has_audio: bool = False


@dataclass
class TimelineTrack:
    id: str = field(default_factory=lambda: _new_id("track"))
    kind: str = "video"
    name: str = "V1"
    order: int = 0
    muted: bool = False
    hidden: bool = False
    locked: bool = False


@dataclass
class TimelineClip:
    id: str = field(default_factory=lambda: _new_id("clip"))
    media_id: str = ""
    track_id: str = ""
    start: float = 0.0
    source_in: float = 0.0
    duration: float = 1.0
    volume: float = 1.0
    opacity: float = 1.0
    fade_in: float = 0.0
    fade_out: float = 0.0
    enabled: bool = True
    group_id: str = ""

    @property
    def end(self) -> float:
        return self.start + self.duration


@dataclass
class TimelineSettings:
    width: int = 1920
    height: int = 1080
    fps: float = 25.0
    media: list[TimelineMedia] = field(default_factory=list)
    tracks: list[TimelineTrack] = field(default_factory=list)
    clips: list[TimelineClip] = field(default_factory=list)

    def ensure_default_tracks(self) -> None:
        if not any(track.kind == "video" for track in self.tracks):
            self.add_track("video")
        if not any(track.kind == "audio" for track in self.tracks):
            self.add_track("audio")

    def add_track(self, kind: str, name: str = "") -> TimelineTrack:
        kind = "audio" if kind == "audio" else "video"
        same_kind = [track for track in self.tracks if track.kind == kind]
        track = TimelineTrack(
            kind=kind,
            name=name or f"{'A' if kind == 'audio' else 'V'}{len(same_kind) + 1}",
            order=len(same_kind),
        )
        self.tracks.append(track)
        return track

    def media_by_id(self, media_id: str) -> TimelineMedia | None:
        return next((item for item in self.media if item.id == media_id), None)

    def track_by_id(self, track_id: str) -> TimelineTrack | None:
        return next((item for item in self.tracks if item.id == track_id), None)

    def clip_by_id(self, clip_id: str) -> TimelineClip | None:
        return next((item for item in self.clips if item.id == clip_id), None)

    def add_media(self, item: TimelineMedia) -> TimelineMedia:
        resolved = str(Path(item.path).resolve()) if item.path else ""
        existing = next(
            (
                media
                for media in self.media
                if media.path and str(Path(media.path).resolve()) == resolved
            ),
            None,
        )
        if existing:
            return existing
        if not item.name:
            item.name = Path(item.path).name
        self.media.append(item)
        return item

    def tracks_of_kind(self, kind: str) -> list[TimelineTrack]:
        return sorted(
            (track for track in self.tracks if track.kind == kind),
            key=lambda track: track.order,
        )

    def next_start(self, track_id: str) -> float:
        return max(
            (clip.end for clip in self.clips if clip.track_id == track_id and clip.enabled),
            default=0.0,
        )

    def _matching_audio_track(self, video_track: TimelineTrack) -> TimelineTrack:
        audio_tracks = self.tracks_of_kind("audio")
        while len(audio_tracks) <= video_track.order:
            audio_tracks.append(self.add_track("audio"))
        return audio_tracks[video_track.order]

    def add_clip(
        self,
        media_id: str,
        track_id: str | None = None,
        start: float | None = None,
        *,
        new_layer: bool = False,
        add_linked_audio: bool = True,
    ) -> list[TimelineClip]:
        media = self.media_by_id(media_id)
        if media is None:
            raise ValueError("Timeline media পাওয়া যায়নি।")
        self.ensure_default_tracks()
        clip_kind = "video" if media.has_video else "audio"
        track = self.track_by_id(track_id or "")
        if track is None or track.kind != clip_kind or new_layer:
            tracks = self.tracks_of_kind(clip_kind)
            track = self.add_track(clip_kind) if new_layer else tracks[0]
        assert track is not None
        clip_start = self.next_start(track.id) if start is None else max(0.0, float(start))
        duration = max(0.05, float(media.duration or (5.0 if media.kind == "image" else 1.0)))
        group_id = _new_id("group")
        primary = TimelineClip(
            media_id=media.id,
            track_id=track.id,
            start=clip_start,
            duration=duration,
            group_id=group_id,
        )
        self.clips.append(primary)
        created = [primary]
        if media.has_video and media.has_audio and add_linked_audio:
            audio_track = self._matching_audio_track(track)
            audio_clip = TimelineClip(
                media_id=media.id,
                track_id=audio_track.id,
                start=clip_start,
                duration=duration,
                group_id=group_id,
            )
            self.clips.append(audio_clip)
            created.append(audio_clip)
        return created

    def move_group(self, clip_id: str, start: float, track_id: str | None = None) -> None:
        clip = self.clip_by_id(clip_id)
        if clip is None:
            return
        group = [item for item in self.clips if item.group_id and item.group_id == clip.group_id]
        if not group:
            group = [clip]
        delta = max(0.0, float(start)) - clip.start
        for item in group:
            item.start = max(0.0, item.start + delta)
        if track_id and len(group) == 1:
            target = self.track_by_id(track_id)
            source = self.track_by_id(clip.track_id)
            if target and source and target.kind == source.kind:
                clip.track_id = target.id

    def trim_clip(self, clip_id: str, edge: str, timeline_time: float) -> None:
        clip = self.clip_by_id(clip_id)
        media = self.media_by_id(clip.media_id) if clip else None
        track = self.track_by_id(clip.track_id) if clip else None
        if clip is None or media is None or (track and track.locked):
            return
        old_start, old_duration = clip.start, clip.duration
        if edge == "left":
            new_start = max(0.0, min(float(timeline_time), clip.end - 0.05))
            delta = new_start - clip.start
            clip.start = new_start
            clip.source_in = max(0.0, clip.source_in + delta)
            clip.duration = max(0.05, clip.duration - delta)
        else:
            maximum = max(0.05, media.duration - clip.source_in)
            clip.duration = max(0.05, min(float(timeline_time) - clip.start, maximum))
        if clip.group_id:
            for mate in self.clips:
                if mate.id != clip.id and mate.group_id == clip.group_id:
                    mate.start = clip.start
                    mate.source_in = clip.source_in
                    mate.duration = clip.duration
        if clip.duration < 0.05:
            clip.start, clip.duration = old_start, old_duration

    def split_group(self, clip_id: str, timeline_time: float) -> list[TimelineClip]:
        clip = self.clip_by_id(clip_id)
        if clip is None or not (clip.start + 0.05 < timeline_time < clip.end - 0.05):
            return []
        group = [item for item in self.clips if item.group_id and item.group_id == clip.group_id]
        if not group:
            group = [clip]
        left_group_id = clip.group_id or _new_id("group")
        right_group_id = _new_id("group")
        new_items: list[TimelineClip] = []
        for item in group:
            offset = timeline_time - item.start
            if not (0.05 < offset < item.duration - 0.05):
                continue
            right = TimelineClip(
                media_id=item.media_id,
                track_id=item.track_id,
                start=timeline_time,
                source_in=item.source_in + offset,
                duration=item.duration - offset,
                volume=item.volume,
                opacity=item.opacity,
                fade_in=0.0,
                fade_out=item.fade_out,
                enabled=item.enabled,
                group_id=right_group_id,
            )
            item.duration = offset
            item.fade_out = 0.0
            item.group_id = left_group_id
            self.clips.append(right)
            new_items.append(right)
        return new_items

    def delete_group(self, clip_id: str, ripple: bool = False) -> None:
        clip = self.clip_by_id(clip_id)
        if clip is None:
            return
        group = [item for item in self.clips if item.group_id and item.group_id == clip.group_id]
        if not group:
            group = [clip]
        removed = {item.id for item in group}
        ripple_by_track = {item.track_id: (item.start, item.duration) for item in group}
        self.clips = [item for item in self.clips if item.id not in removed]
        if ripple:
            for item in self.clips:
                if item.track_id in ripple_by_track:
                    start, duration = ripple_by_track[item.track_id]
                    if item.start >= start + duration - 0.001:
                        item.start = max(start, item.start - duration)

    def remove_track(self, track_id: str) -> None:
        track = self.track_by_id(track_id)
        if track is None:
            return
        same_kind = self.tracks_of_kind(track.kind)
        if len(same_kind) <= 1:
            return
        removed_groups = {
            clip.group_id
            for clip in self.clips
            if clip.track_id == track_id and clip.group_id
        }
        self.clips = [
            clip
            for clip in self.clips
            if clip.track_id != track_id and clip.group_id not in removed_groups
        ]
        self.tracks = [item for item in self.tracks if item.id != track_id]
        for index, item in enumerate(self.tracks_of_kind(track.kind)):
            item.order = index
            item.name = f"{'A' if item.kind == 'audio' else 'V'}{index + 1}"

    def duration(self) -> float:
        return max((clip.end for clip in self.clips if clip.enabled), default=0.0)

    def has_clips(self) -> bool:
        return any(clip.enabled for clip in self.clips)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimelineSettings":
        timeline = cls(
            width=int(data.get("width", 1920)),
            height=int(data.get("height", 1080)),
            fps=float(data.get("fps", 25.0)),
        )
        timeline.media = [TimelineMedia(**item) for item in data.get("media", [])]
        timeline.tracks = [TimelineTrack(**item) for item in data.get("tracks", [])]
        timeline.clips = [TimelineClip(**item) for item in data.get("clips", [])]
        timeline.ensure_default_tracks()
        return timeline


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
    timeline: TimelineSettings = field(default_factory=TimelineSettings)

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
        project.timeline = TimelineSettings.from_dict(data.get("timeline", {}))
        return project

    def default_output_path(self) -> str:
        source_path = self.video_path or next(
            (media.path for media in self.timeline.media if media.path),
            "",
        )
        if not source_path:
            return ""
        source = Path(source_path)
        suffix = "প্রফেশনাল_টাইমলাইন" if self.timeline.has_clips() else "বাংলা_সাবটাইটেল"
        return str(source.with_name(f"{source.stem}_{suffix}.mp4"))
