from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from .media import MediaError, probe_media
from .models import Project, TimelineClip, TimelineMedia, TimelineTrack


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".mts", ".m2ts"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".wma"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


class TimelineEditor(ttk.Frame):
    RULER_HEIGHT = 30
    TRACK_HEIGHT = 58
    HEADER_WIDTH = 132

    def __init__(
        self,
        parent: tk.Misc,
        project: Project,
        *,
        on_change: Callable[[str], None] | None = None,
        on_seek: Callable[[float], None] | None = None,
        on_primary_video: Callable[[str], None] | None = None,
        on_export: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent, style="Panel.TFrame", padding=(8, 6))
        self.project = project
        self.on_change = on_change
        self.on_seek = on_seek
        self.on_primary_video = on_primary_video
        self.on_export = on_export
        self.project.timeline.ensure_default_tracks()
        self.selected_media_id = ""
        self.selected_clip_id = ""
        self.selected_track_id = ""
        self.playhead = 0.0
        self.pixels_per_second = 35.0
        self.drag_mode = ""
        self.drag_origin_x = 0.0
        self.drag_origin_start = 0.0
        self.drag_clip_id = ""
        self._track_rows: list[tuple[TimelineTrack, float, float]] = []

        self.zoom_var = tk.DoubleVar(value=self.pixels_per_second)
        self.ripple_var = tk.BooleanVar(value=False)
        self.clip_start_var = tk.StringVar(value="0.00")
        self.clip_in_var = tk.StringVar(value="0.00")
        self.clip_duration_var = tk.StringVar(value="0.00")
        self.clip_volume_var = tk.StringVar(value="100")
        self.clip_fade_in_var = tk.StringVar(value="0.00")
        self.clip_fade_out_var = tk.StringVar(value="0.00")
        self.selection_var = tk.StringVar(value="কোনো clip নির্বাচন করা হয়নি")
        self.timeline_time_var = tk.StringVar(value="00:00:00.000")

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        title_row = ttk.Frame(self, style="Panel.TFrame")
        title_row.pack(fill="x", pady=(0, 5))
        ttk.Label(
            title_row,
            text="V4 PROFESSIONAL TIMELINE",
            font=("Nirmala UI", 11, "bold"),
            foreground="#66D9EF",
        ).pack(side="left")
        ttk.Label(
            title_row,
            text="Video/Audio Layer • Drag • Trim • Split • Delete • Mix",
            style="Muted.TLabel",
        ).pack(side="left", padx=(12, 0))
        self.export_button = ttk.Button(
            title_row,
            text="Final Timeline Export",
            style="Accent.TButton",
            command=self.on_export,
        )
        self.export_button.pack(side="right")

        toolbar = ttk.Frame(self, style="Card.TFrame", padding=5)
        toolbar.pack(fill="x", pady=(0, 5))
        ttk.Button(toolbar, text="+ Video", command=lambda: self.import_media("video")).pack(side="left", padx=2)
        ttk.Button(toolbar, text="+ Audio", command=lambda: self.import_media("audio")).pack(side="left", padx=2)
        ttk.Button(toolbar, text="+ Image", command=lambda: self.import_media("image")).pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(toolbar, text="Add Sequential", command=self.add_selected_sequential).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Add New Layer", command=self.add_selected_new_layer).pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(toolbar, text="✂ Split", command=self.split_selected).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Delete", style="Danger.TButton", command=self.delete_selected).pack(side="left", padx=2)
        ttk.Checkbutton(toolbar, text="Ripple Delete", variable=self.ripple_var).pack(side="left", padx=(6, 2))
        ttk.Label(toolbar, text="Zoom", style="Muted.TLabel").pack(side="right", padx=(6, 2))
        ttk.Scale(
            toolbar,
            from_=10,
            to=120,
            variable=self.zoom_var,
            command=self._zoom_changed,
            length=150,
        ).pack(side="right")

        content = ttk.Panedwindow(self, orient="horizontal")
        content.pack(fill="both", expand=True)
        media_panel = ttk.Frame(content, style="Card.TFrame", padding=6, width=275)
        timeline_panel = ttk.Frame(content, style="Panel.TFrame")
        content.add(media_panel, weight=1)
        content.add(timeline_panel, weight=5)

        ttk.Label(media_panel, text="Media Bin", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 4))
        self.media_tree = ttk.Treeview(media_panel, columns=("type", "duration"), show="tree headings", height=8)
        self.media_tree.heading("#0", text="File")
        self.media_tree.heading("type", text="Type")
        self.media_tree.heading("duration", text="Time")
        self.media_tree.column("#0", width=150, stretch=True)
        self.media_tree.column("type", width=54, anchor="center", stretch=False)
        self.media_tree.column("duration", width=58, anchor="e", stretch=False)
        self.media_tree.pack(fill="both", expand=True)
        self.media_tree.bind("<<TreeviewSelect>>", self._select_media)
        self.media_tree.bind("<Double-1>", lambda _event: self.add_selected_sequential())

        inspector = ttk.Frame(media_panel, style="Card.TFrame")
        inspector.pack(fill="x", pady=(6, 0))
        ttk.Label(inspector, textvariable=self.selection_var, style="Muted.TLabel", wraplength=245).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 4)
        )
        fields = [
            ("Start", self.clip_start_var),
            ("Source In", self.clip_in_var),
            ("Duration", self.clip_duration_var),
            ("Volume %", self.clip_volume_var),
            ("Fade In", self.clip_fade_in_var),
            ("Fade Out", self.clip_fade_out_var),
        ]
        for index, (label, variable) in enumerate(fields):
            row = 1 + index // 2
            column = (index % 2) * 2
            ttk.Label(inspector, text=label, style="Muted.TLabel").grid(row=row, column=column, sticky="w", padx=(0, 3), pady=2)
            ttk.Entry(inspector, textvariable=variable, width=8).grid(row=row, column=column + 1, sticky="ew", padx=(0, 5), pady=2)
        inspector.columnconfigure(1, weight=1)
        inspector.columnconfigure(3, weight=1)
        ttk.Button(inspector, text="Clip Settings Apply", command=self.apply_clip_settings).grid(
            row=4, column=0, columnspan=4, sticky="ew", pady=(5, 0)
        )

        track_tools = ttk.Frame(timeline_panel, style="Card.TFrame", padding=4)
        track_tools.pack(fill="x", pady=(0, 4))
        ttk.Button(track_tools, text="+ Video Layer", command=lambda: self.add_track("video")).pack(side="left", padx=2)
        ttk.Button(track_tools, text="+ Audio Layer", command=lambda: self.add_track("audio")).pack(side="left", padx=2)
        ttk.Button(track_tools, text="Remove Layer", command=self.remove_selected_track).pack(side="left", padx=2)
        ttk.Button(track_tools, text="🔒 Lock", command=self.toggle_track_lock).pack(side="left", padx=(8, 2))
        ttk.Button(track_tools, text="👁 Hide", command=self.toggle_track_hidden).pack(side="left", padx=2)
        ttk.Button(track_tools, text="🔊 Mute", command=self.toggle_track_mute).pack(side="left", padx=2)
        ttk.Label(track_tools, textvariable=self.timeline_time_var, font=("Consolas", 10, "bold")).pack(side="right", padx=6)

        canvas_holder = ttk.Frame(timeline_panel, style="Panel.TFrame")
        canvas_holder.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(
            canvas_holder,
            bg="#0B1220",
            highlightthickness=1,
            highlightbackground="#2A3D5C",
            xscrollincrement=1,
        )
        hscroll = ttk.Scrollbar(canvas_holder, orient="horizontal", command=self.canvas.xview)
        vscroll = ttk.Scrollbar(canvas_holder, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=hscroll.set, yscrollcommand=vscroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")
        hscroll.grid(row=1, column=0, sticky="ew")
        canvas_holder.columnconfigure(0, weight=1)
        canvas_holder.rowconfigure(0, weight=1)
        self.canvas.bind("<ButtonPress-1>", self._canvas_press)
        self.canvas.bind("<B1-Motion>", self._canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._canvas_release)
        self.canvas.bind("<Configure>", lambda _event: self.draw_timeline())
        self.canvas.bind("<Delete>", lambda _event: self.delete_selected())
        self.canvas.bind("<MouseWheel>", self._canvas_mousewheel)

    def set_project(self, project: Project) -> None:
        self.project = project
        self.project.timeline.ensure_default_tracks()
        self.selected_media_id = ""
        self.selected_clip_id = ""
        self.selected_track_id = ""
        self.playhead = 0.0
        self.refresh()

    def set_busy(self, busy: bool) -> None:
        self.export_button.configure(state="disabled" if busy else "normal")

    def _notify(self, message: str) -> None:
        if self.on_change:
            self.on_change(message)

    @staticmethod
    def _clock(seconds: float) -> str:
        seconds = max(0.0, seconds)
        hours = int(seconds // 3600)
        minutes = int(seconds % 3600 // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

    def import_media(self, kind: str) -> None:
        if kind == "video":
            filetypes = [("Video", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.mts *.m2ts"), ("সব ফাইল", "*.*")]
        elif kind == "audio":
            filetypes = [("Audio", "*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.wma"), ("সব ফাইল", "*.*")]
        else:
            filetypes = [("Image", "*.png *.jpg *.jpeg *.webp *.bmp"), ("সব ফাইল", "*.*")]
        paths = filedialog.askopenfilenames(title="Timeline Media Import", filetypes=filetypes)
        if paths:
            self.add_paths(list(paths), auto_place=True)

    def add_paths(self, paths: list[str], *, auto_place: bool = True) -> list[TimelineMedia]:
        added: list[TimelineMedia] = []
        first_video_was_empty = not any(media.has_video for media in self.project.timeline.media)
        for raw_path in paths:
            path = str(Path(raw_path).resolve())
            suffix = Path(path).suffix.lower()
            try:
                if suffix in IMAGE_EXTENSIONS:
                    item = TimelineMedia(
                        path=path,
                        name=Path(path).name,
                        kind="image",
                        duration=5.0,
                        has_video=True,
                        has_audio=False,
                    )
                else:
                    info = probe_media(path)
                    has_video = bool(info["has_video"])
                    has_audio = bool(info["has_audio"])
                    if suffix in AUDIO_EXTENSIONS:
                        has_video = False
                    if not has_video and not has_audio:
                        raise MediaError("ফাইলটিতে video বা audio stream নেই।")
                    item = TimelineMedia(
                        path=path,
                        name=Path(path).name,
                        kind="video" if has_video else "audio",
                        duration=max(0.05, float(info["duration"])),
                        width=int(info["width"]),
                        height=int(info["height"]),
                        fps=float(info["fps"]),
                        has_video=has_video,
                        has_audio=has_audio,
                    )
                stored = self.project.timeline.add_media(item)
                added.append(stored)
                if auto_place:
                    if stored.kind == "audio":
                        audio_tracks = self.project.timeline.tracks_of_kind("audio")
                        empty = next(
                            (
                                track
                                for track in audio_tracks
                                if not any(clip.track_id == track.id for clip in self.project.timeline.clips)
                            ),
                            None,
                        )
                        target = empty or self.project.timeline.add_track("audio")
                        self.project.timeline.add_clip(
                            stored.id,
                            target.id,
                            self.playhead,
                            add_linked_audio=False,
                        )
                    elif stored.kind == "image":
                        self.project.timeline.add_clip(
                            stored.id,
                            start=self.playhead,
                            new_layer=bool(self.project.timeline.clips),
                            add_linked_audio=False,
                        )
                    else:
                        self.project.timeline.add_clip(stored.id)
            except (OSError, MediaError, ValueError) as exc:
                messagebox.showerror("Media Import হয়নি", f"{Path(path).name}\n\n{exc}", parent=self)
        if added and first_video_was_empty:
            first_video = next((media for media in added if media.kind == "video"), None)
            if first_video and self.on_primary_video:
                self.on_primary_video(first_video.path)
            if first_video:
                timeline = self.project.timeline
                timeline.width = first_video.width or timeline.width
                timeline.height = first_video.height or timeline.height
                timeline.fps = first_video.fps or timeline.fps
        if added:
            self.selected_media_id = added[-1].id
            self.refresh()
            self._notify(f"{len(added)}টি media Import হয়ে Timeline-এ বসেছে।")
        return added

    def _select_media(self, _event: tk.Event | None = None) -> None:
        selection = self.media_tree.selection()
        if selection:
            self.selected_media_id = selection[0]

    def add_selected_sequential(self) -> None:
        if not self.selected_media_id:
            messagebox.showinfo("Timeline", "Media Bin থেকে একটি file নির্বাচন করুন।", parent=self)
            return
        created = self.project.timeline.add_clip(self.selected_media_id)
        self.selected_clip_id = created[0].id
        self.refresh()
        self._notify("নির্বাচিত media একই layer-এর শেষে যোগ হয়েছে।")

    def add_selected_new_layer(self) -> None:
        if not self.selected_media_id:
            messagebox.showinfo("Timeline", "Media Bin থেকে একটি file নির্বাচন করুন।", parent=self)
            return
        created = self.project.timeline.add_clip(
            self.selected_media_id,
            start=self.playhead,
            new_layer=True,
        )
        self.selected_clip_id = created[0].id
        self.refresh()
        self._notify("নির্বাচিত media নতুন layer-এ যোগ হয়েছে।")

    def add_track(self, kind: str) -> None:
        track = self.project.timeline.add_track(kind)
        self.selected_track_id = track.id
        self.refresh()
        self._notify(f"নতুন {track.name} layer যোগ হয়েছে।")

    def _selected_track(self) -> TimelineTrack | None:
        if self.selected_clip_id:
            clip = self.project.timeline.clip_by_id(self.selected_clip_id)
            if clip:
                return self.project.timeline.track_by_id(clip.track_id)
        return self.project.timeline.track_by_id(self.selected_track_id)

    def remove_selected_track(self) -> None:
        track = self._selected_track()
        if not track:
            return
        if not messagebox.askyesno("Layer Remove", f"{track.name} এবং এর সব clip মুছবেন?", parent=self):
            return
        self.project.timeline.remove_track(track.id)
        self.selected_track_id = ""
        self.selected_clip_id = ""
        self.refresh()
        self._notify(f"{track.name} layer মুছে ফেলা হয়েছে।")

    def toggle_track_lock(self) -> None:
        track = self._selected_track()
        if track:
            track.locked = not track.locked
            self.refresh()
            self._notify(f"{track.name} {'Lock' if track.locked else 'Unlock'} হয়েছে।")

    def toggle_track_hidden(self) -> None:
        track = self._selected_track()
        if track and track.kind == "video":
            track.hidden = not track.hidden
            self.refresh()
            self._notify(f"{track.name} {'Hide' if track.hidden else 'Show'} হয়েছে।")

    def toggle_track_mute(self) -> None:
        track = self._selected_track()
        if track and track.kind == "audio":
            track.muted = not track.muted
            self.refresh()
            self._notify(f"{track.name} {'Mute' if track.muted else 'Unmute'} হয়েছে।")

    def split_selected(self) -> None:
        if not self.selected_clip_id:
            messagebox.showinfo("Split", "আগে একটি clip নির্বাচন করুন।", parent=self)
            return
        created = self.project.timeline.split_group(self.selected_clip_id, self.playhead)
        if not created:
            messagebox.showinfo("Split", "Playhead clip-এর মাঝখানে রাখুন।", parent=self)
            return
        self.selected_clip_id = created[0].id
        self.refresh()
        self._notify("Playhead-এর জায়গায় Video/Audio clip Split হয়েছে।")

    def delete_selected(self) -> None:
        if not self.selected_clip_id:
            return
        self.project.timeline.delete_group(self.selected_clip_id, self.ripple_var.get())
        self.selected_clip_id = ""
        self.refresh()
        self._notify("Clip Delete হয়েছে" + (" এবং gap বন্ধ হয়েছে।" if self.ripple_var.get() else "।"))

    def apply_clip_settings(self) -> None:
        clip = self.project.timeline.clip_by_id(self.selected_clip_id)
        media = self.project.timeline.media_by_id(clip.media_id) if clip else None
        if clip is None or media is None:
            return
        try:
            new_start = max(0.0, float(self.clip_start_var.get()))
            source_in = max(0.0, float(self.clip_in_var.get()))
            duration = max(0.05, float(self.clip_duration_var.get()))
            duration = min(duration, max(0.05, media.duration - source_in))
            volume = max(0.0, min(400.0, float(self.clip_volume_var.get()))) / 100.0
            fade_in = max(0.0, min(duration, float(self.clip_fade_in_var.get())))
            fade_out = max(0.0, min(duration, float(self.clip_fade_out_var.get())))
        except ValueError:
            messagebox.showerror("Clip Settings", "সব ঘরে সঠিক সংখ্যা দিন।", parent=self)
            return
        self.project.timeline.move_group(clip.id, new_start)
        group = [
            item
            for item in self.project.timeline.clips
            if item.id == clip.id or (clip.group_id and item.group_id == clip.group_id)
        ]
        for item in group:
            item.source_in = source_in
            item.duration = duration
            item.fade_in = fade_in
            item.fade_out = fade_out
            track = self.project.timeline.track_by_id(item.track_id)
            if track and track.kind == "audio":
                item.volume = volume
        self.refresh()
        self._notify("Clip-এর time, trim, volume ও fade Apply হয়েছে।")

    def _zoom_changed(self, _value: str) -> None:
        self.pixels_per_second = float(self.zoom_var.get())
        self.draw_timeline()

    def _display_tracks(self) -> list[TimelineTrack]:
        videos = list(reversed(self.project.timeline.tracks_of_kind("video")))
        audios = self.project.timeline.tracks_of_kind("audio")
        return videos + audios

    def draw_timeline(self) -> None:
        if not hasattr(self, "canvas"):
            return
        self.canvas.delete("all")
        tracks = self._display_tracks()
        duration = max(30.0, self.project.timeline.duration() + 5.0)
        content_width = self.HEADER_WIDTH + duration * self.pixels_per_second
        content_height = self.RULER_HEIGHT + len(tracks) * self.TRACK_HEIGHT
        self.canvas.configure(scrollregion=(0, 0, content_width, content_height))
        self.canvas.create_rectangle(0, 0, content_width, self.RULER_HEIGHT, fill="#152033", outline="")
        tick_step = 1 if self.pixels_per_second >= 55 else 2 if self.pixels_per_second >= 25 else 5
        for second in range(0, int(duration) + 1, tick_step):
            x = self.HEADER_WIDTH + second * self.pixels_per_second
            self.canvas.create_line(x, 17, x, self.RULER_HEIGHT, fill="#70829B")
            self.canvas.create_text(x + 3, 8, text=self._clock(second)[3:8], fill="#AFC0D8", anchor="w", font=("Consolas", 8))
        self._track_rows.clear()
        for index, track in enumerate(tracks):
            y0 = self.RULER_HEIGHT + index * self.TRACK_HEIGHT
            y1 = y0 + self.TRACK_HEIGHT
            self._track_rows.append((track, y0, y1))
            fill = "#17243A" if index % 2 == 0 else "#111D30"
            if track.id == self.selected_track_id:
                fill = "#203A5C"
            self.canvas.create_rectangle(0, y0, content_width, y1, fill=fill, outline="#263A59")
            self.canvas.create_rectangle(0, y0, self.HEADER_WIDTH, y1, fill="#1B2940", outline="#314664", tags=(f"track:{track.id}",))
            state = []
            if track.locked:
                state.append("🔒")
            if track.hidden:
                state.append("HIDE")
            if track.muted:
                state.append("MUTE")
            icon = "🎬" if track.kind == "video" else "🔊"
            self.canvas.create_text(10, (y0 + y1) / 2 - 8, text=f"{icon}  {track.name}", fill="#FFFFFF", anchor="w", font=("Nirmala UI", 10, "bold"), tags=(f"track:{track.id}",))
            self.canvas.create_text(10, (y0 + y1) / 2 + 11, text=" • ".join(state) or "Active", fill="#7F93AF", anchor="w", font=("Nirmala UI", 8), tags=(f"track:{track.id}",))
            clips = sorted(
                (clip for clip in self.project.timeline.clips if clip.track_id == track.id and clip.enabled),
                key=lambda clip: (clip.start, clip.id),
            )
            for clip in clips:
                self._draw_clip(track, clip, y0, y1)
        playhead_x = self.HEADER_WIDTH + self.playhead * self.pixels_per_second
        self.canvas.create_line(playhead_x, 0, playhead_x, content_height, fill="#FF4D5A", width=2, tags=("playhead",))
        self.canvas.create_polygon(playhead_x - 6, 0, playhead_x + 6, 0, playhead_x, 9, fill="#FF4D5A", outline="", tags=("playhead",))

    def _draw_clip(self, track: TimelineTrack, clip: TimelineClip, y0: float, y1: float) -> None:
        media = self.project.timeline.media_by_id(clip.media_id)
        if media is None:
            return
        x0 = self.HEADER_WIDTH + clip.start * self.pixels_per_second
        x1 = max(x0 + 5, self.HEADER_WIDTH + clip.end * self.pixels_per_second)
        clip_tag = f"clip:{clip.id}"
        selected = clip.id == self.selected_clip_id
        if track.kind == "audio":
            fill = "#246B61"
            accent = "#65E6A3"
        elif media.kind == "image":
            fill = "#714A87"
            accent = "#DDA6F7"
        else:
            fill = "#285EAA"
            accent = "#66B2FF"
        outline = "#FFD966" if selected else accent
        width = 3 if selected else 1
        self.canvas.create_rectangle(x0 + 1, y0 + 5, x1 - 1, y1 - 5, fill=fill, outline=outline, width=width, tags=(clip_tag, "clip"))
        self.canvas.create_rectangle(x0 + 1, y0 + 5, min(x0 + 6, x1 - 1), y1 - 5, fill=accent, outline="", tags=(clip_tag, "clip", "left_handle"))
        self.canvas.create_rectangle(max(x0 + 1, x1 - 6), y0 + 5, x1 - 1, y1 - 5, fill=accent, outline="", tags=(clip_tag, "clip", "right_handle"))
        available = max(0, int((x1 - x0 - 16) / 7))
        label = media.name if len(media.name) <= available else media.name[: max(1, available - 1)] + "…"
        self.canvas.create_text(x0 + 9, y0 + 18, text=label, fill="#FFFFFF", anchor="w", font=("Nirmala UI", 9, "bold"), tags=(clip_tag, "clip"))
        detail = f"{clip.duration:.2f}s"
        if track.kind == "audio":
            detail += f" • {clip.volume * 100:.0f}%"
        self.canvas.create_text(x0 + 9, y0 + 38, text=detail, fill="#D7E4F4", anchor="w", font=("Consolas", 8), tags=(clip_tag, "clip"))

    def _hit_track(self, y: float) -> TimelineTrack | None:
        return next((track for track, y0, y1 in self._track_rows if y0 <= y < y1), None)

    @staticmethod
    def _tag_id(tags: tuple[str, ...], prefix: str) -> str:
        return next((tag.split(":", 1)[1] for tag in tags if tag.startswith(prefix + ":")), "")

    def _canvas_press(self, event: tk.Event) -> None:
        self.canvas.focus_set()
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        current = self.canvas.find_withtag("current")
        tags = self.canvas.gettags(current[0]) if current else ()
        clip_id = self._tag_id(tags, "clip")
        if clip_id:
            clip = self.project.timeline.clip_by_id(clip_id)
            track = self.project.timeline.track_by_id(clip.track_id) if clip else None
            if clip is None:
                return
            self.selected_clip_id = clip_id
            self.selected_track_id = clip.track_id
            self.drag_clip_id = clip_id
            self.drag_origin_x = x
            self.drag_origin_start = clip.start
            if track and track.locked:
                self.drag_mode = ""
            elif "left_handle" in tags:
                self.drag_mode = "trim_left"
            elif "right_handle" in tags:
                self.drag_mode = "trim_right"
            else:
                self.drag_mode = "move"
            self._load_clip_inspector()
            self.draw_timeline()
            return
        track_id = self._tag_id(tags, "track")
        if track_id:
            self.selected_track_id = track_id
            self.selected_clip_id = ""
            self.draw_timeline()
            return
        if y <= self.RULER_HEIGHT or x >= self.HEADER_WIDTH:
            self.playhead = max(0.0, (x - self.HEADER_WIDTH) / self.pixels_per_second)
            self.timeline_time_var.set(self._clock(self.playhead))
            self.draw_timeline()
            if self.on_seek:
                self.on_seek(self.playhead)

    def _canvas_drag(self, event: tk.Event) -> None:
        if not self.drag_mode or not self.drag_clip_id:
            return
        x = self.canvas.canvasx(event.x)
        clip = self.project.timeline.clip_by_id(self.drag_clip_id)
        if clip is None:
            return
        if self.drag_mode == "move":
            delta = (x - self.drag_origin_x) / self.pixels_per_second
            new_start = round(max(0.0, self.drag_origin_start + delta) * 20) / 20
            self.project.timeline.move_group(clip.id, new_start)
        elif self.drag_mode == "trim_left":
            timeline_time = round(max(0.0, (x - self.HEADER_WIDTH) / self.pixels_per_second) * 20) / 20
            self.project.timeline.trim_clip(clip.id, "left", timeline_time)
        else:
            timeline_time = round(max(0.0, (x - self.HEADER_WIDTH) / self.pixels_per_second) * 20) / 20
            self.project.timeline.trim_clip(clip.id, "right", timeline_time)
        self._load_clip_inspector()
        self.draw_timeline()

    def _canvas_release(self, _event: tk.Event) -> None:
        if self.drag_mode:
            self._notify("Timeline clip-এর অবস্থান/trim পরিবর্তন হয়েছে।")
            if self.on_seek:
                self.on_seek(self.playhead)
        self.drag_mode = ""
        self.drag_clip_id = ""

    def _canvas_mousewheel(self, event: tk.Event) -> None:
        if event.state & 0x0004:
            self.canvas.xview_scroll(int(-event.delta / 120), "units")
        else:
            self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _load_clip_inspector(self) -> None:
        clip = self.project.timeline.clip_by_id(self.selected_clip_id)
        media = self.project.timeline.media_by_id(clip.media_id) if clip else None
        if clip is None or media is None:
            self.selection_var.set("কোনো clip নির্বাচন করা হয়নি")
            return
        track = self.project.timeline.track_by_id(clip.track_id)
        self.selection_var.set(f"{track.name if track else ''} • {media.name}")
        self.clip_start_var.set(f"{clip.start:.2f}")
        self.clip_in_var.set(f"{clip.source_in:.2f}")
        self.clip_duration_var.set(f"{clip.duration:.2f}")
        self.clip_volume_var.set(f"{clip.volume * 100:.0f}")
        self.clip_fade_in_var.set(f"{clip.fade_in:.2f}")
        self.clip_fade_out_var.set(f"{clip.fade_out:.2f}")

    def refresh(self) -> None:
        self.project.timeline.ensure_default_tracks()
        if hasattr(self, "media_tree"):
            self.media_tree.delete(*self.media_tree.get_children())
            for media in self.project.timeline.media:
                kind = {"video": "Video", "audio": "Audio", "image": "Image"}.get(media.kind, media.kind)
                self.media_tree.insert("", "end", iid=media.id, text=media.name, values=(kind, self._clock(media.duration)[3:]))
            if self.selected_media_id and self.media_tree.exists(self.selected_media_id):
                self.media_tree.selection_set(self.selected_media_id)
        self._load_clip_inspector()
        self.timeline_time_var.set(self._clock(self.playhead))
        self.draw_timeline()
