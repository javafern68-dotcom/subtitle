from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from PIL import Image, ImageEnhance, ImageTk

from .exporter import ExportError, export_project
from .media import MediaError, _startupinfo, bundled_tool, extract_frame, probe_video
from .models import ColorSettings, Project, SubtitleSegment
from .subtitles import format_srt_time, parse_srt, parse_timecode, write_srt
from .transcription import transcribe_video
from .translation import shift_segments, shift_segments_earlier, translate_segments
from .voice_translate import create_voice_translated_video


APP_NAME = "Bangla Subtitle Studio"
APP_VERSION = "3.0.0"
PREVIEW_SIZE = (960, 540)
LANGUAGES = {
    "বাংলা (বাংলা অক্ষর)": "bn",
    "বাংলা (Avro / Banglish)": "avro",
    "हिन्दी (Hindi)": "hi",
    "English": "en",
    "العربية (Arabic)": "ar",
    "اردو (Urdu)": "ur",
    "नेपाली (Nepali)": "ne",
    "ਪੰਜਾਬੀ (Punjabi)": "pa",
    "தமிழ் (Tamil)": "ta",
    "తెలుగు (Telugu)": "te",
    "ગુજરાતી (Gujarati)": "gu",
    "فارسی (Persian)": "fa",
    "Español (Spanish)": "es",
    "Français (French)": "fr",
    "Deutsch (German)": "de",
    "Italiano (Italian)": "it",
    "Português (Portuguese)": "pt",
    "Русский (Russian)": "ru",
    "Türkçe (Turkish)": "tr",
    "中文 (Chinese)": "zh",
    "日本語 (Japanese)": "ja",
    "한국어 (Korean)": "ko",
}
VOICE_LANGUAGES = {
    label: code for label, code in LANGUAGES.items() if code != "avro"
}
class ScrollableTab(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.canvas = tk.Canvas(self, bg="#152033", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.body = ttk.Frame(self.canvas, style="Panel.TFrame")
        self.window_id = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.body.bind("<Configure>", self._on_body_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel, add="+")

    def _on_body_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> None:
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget == self:
                self.canvas.yview_scroll(int(-event.delta / 120), "units")
                return
            widget = getattr(widget, "master", None)


class BanglaSubtitleStudio(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} V{APP_VERSION}")
        self.geometry("1460x900")
        self.minsize(1180, 720)
        self.configure(bg="#0B1220")
        self.project = Project()
        self.project_path = ""
        self.current_time = 0.0
        self.last_frame: Image.Image | None = None
        self.preview_photo: ImageTk.PhotoImage | None = None
        self.logo_photo: ImageTk.PhotoImage | None = None
        self.preview_job: str | None = None
        self.preview_serial = 0
        self.busy_cancel = threading.Event()
        self.busy = False
        self.playing = False
        self.play_process: subprocess.Popen | None = None
        self.audio_process: subprocess.Popen | None = None
        self.play_queue: queue.Queue[tuple[Image.Image, float] | None] = queue.Queue(maxsize=2)
        self.logo_drag_offset = (0.0, 0.0)
        self._sync_baseline: list[SubtitleSegment] = []
        self._global_sync_offset = 0.0

        self._configure_theme()
        self._create_variables()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(150, self._draw_placeholder)

    def _configure_theme(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background="#152033", foreground="#E8EEF8", font=("Nirmala UI", 10))
        style.configure("TFrame", background="#0B1220")
        style.configure("Panel.TFrame", background="#152033")
        style.configure("Card.TFrame", background="#1B2940")
        style.configure("TLabel", background="#152033", foreground="#DCE7F7")
        style.configure("Title.TLabel", background="#0B1220", foreground="#FFFFFF", font=("Nirmala UI", 18, "bold"))
        style.configure("Muted.TLabel", background="#152033", foreground="#91A3BD")
        style.configure("CardTitle.TLabel", background="#1B2940", foreground="#FFFFFF", font=("Nirmala UI", 11, "bold"))
        style.configure("TButton", background="#263A59", foreground="#FFFFFF", padding=(10, 7), borderwidth=0)
        style.map("TButton", background=[("active", "#315079"), ("disabled", "#273246")])
        style.configure("Accent.TButton", background="#2B7FFF", foreground="#FFFFFF", font=("Nirmala UI", 10, "bold"), padding=(12, 8))
        style.map("Accent.TButton", background=[("active", "#4B94FF"), ("disabled", "#39526F")])
        style.configure("Danger.TButton", background="#8F3046", foreground="#FFFFFF")
        style.map("Danger.TButton", background=[("active", "#B13C56")])
        style.configure("TNotebook", background="#0B1220", borderwidth=0)
        style.configure("TNotebook.Tab", background="#1B2940", foreground="#AFC0D8", padding=(10, 9), borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", "#2B7FFF")], foreground=[("selected", "#FFFFFF")])
        style.configure("Treeview", background="#111C2E", fieldbackground="#111C2E", foreground="#E8EEF8", rowheight=30, borderwidth=0)
        style.map("Treeview", background=[("selected", "#285EAA")])
        style.configure("Treeview.Heading", background="#243854", foreground="#FFFFFF", font=("Nirmala UI", 9, "bold"), borderwidth=0)
        style.configure("TEntry", fieldbackground="#0F1A2C", foreground="#FFFFFF", insertcolor="#FFFFFF", padding=6)
        style.configure("TCombobox", fieldbackground="#0F1A2C", background="#0F1A2C", foreground="#FFFFFF", arrowcolor="#FFFFFF", padding=5)
        style.map("TCombobox", fieldbackground=[("readonly", "#0F1A2C")], foreground=[("readonly", "#FFFFFF")])
        style.configure("TCheckbutton", background="#152033", foreground="#DCE7F7")
        style.map("TCheckbutton", background=[("active", "#152033")])
        style.configure("Horizontal.TScale", background="#152033", troughcolor="#263A59")
        style.configure("TProgressbar", troughcolor="#0F1A2C", background="#2B7FFF")

    def _create_variables(self) -> None:
        self.status_var = tk.StringVar(value="একটি ভিডিও নির্বাচন করে শুরু করুন।")
        self.progress_var = tk.DoubleVar(value=0.0)
        self.seek_var = tk.DoubleVar(value=0.0)
        self.time_var = tk.StringVar(value="00:00:00 / 00:00:00")
        self.video_name_var = tk.StringVar(value="কোনো ভিডিও নির্বাচন করা হয়নি")
        self.offline_status_var = tk.StringVar(
            value="✓ সম্পূর্ণ Offline • API Key ও Internet লাগবে না • প্রতি ভিডিও ০ টাকা"
        )
        self.language_var = tk.StringVar(value="বাংলা (বাংলা অক্ষর)")
        self.voice_source_var = tk.StringVar(value="বাংলা (বাংলা অক্ষর)")
        self.voice_target_var = tk.StringVar(value="English")
        self.voice_gender_var = tk.StringVar(value="নারী কণ্ঠ")
        self.voice_original_volume_var = tk.DoubleVar(value=0.0)
        self.voice_add_subtitles_var = tk.BooleanVar(value=True)
        self.voice_output_var = tk.StringVar(value="")
        self.subtitle_lead_var = tk.DoubleVar(value=0.35)
        self.sync_step_var = tk.DoubleVar(value=0.10)
        self.sync_status_var = tk.StringVar(value="বর্তমান পরিবর্তন: 0.00 সেকেন্ড")
        self.prompt_var = tk.StringVar(value="")
        self.font_var = tk.StringVar(value="Nirmala UI")
        self.font_size_var = tk.DoubleVar(value=58)
        self.outline_var = tk.DoubleVar(value=4)
        self.shadow_var = tk.DoubleVar(value=1)
        self.bold_var = tk.BooleanVar(value=True)
        self.background_var = tk.BooleanVar(value=False)
        self.position_var = tk.StringVar(value="নিচে")
        self.margin_var = tk.DoubleVar(value=70)
        self.max_chars_var = tk.DoubleVar(value=70)
        self.show_secondary_var = tk.BooleanVar(value=True)
        self.logo_scale_var = tk.DoubleVar(value=18)
        self.logo_opacity_var = tk.DoubleVar(value=90)
        self.logo_start_var = tk.StringVar(value="00:00:00,000")
        self.logo_end_var = tk.StringVar(value="ভিডিওর শেষ পর্যন্ত")
        self.brightness_var = tk.DoubleVar(value=0)
        self.contrast_var = tk.DoubleVar(value=1)
        self.saturation_var = tk.DoubleVar(value=1)
        self.temperature_var = tk.DoubleVar(value=0)
        self.tint_var = tk.DoubleVar(value=0)
        self.preset_var = tk.StringVar(value="Natural")
        self.output_var = tk.StringVar(value="")
        self.quality_var = tk.StringVar(value="Balanced")

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=(18, 12), style="TFrame")
        top.pack(fill="x")
        ttk.Label(top, text=APP_NAME, style="Title.TLabel").pack(side="left")
        ttk.Label(top, text=f"  V{APP_VERSION} • Offline বাংলা Auto Subtitle", style="Muted.TLabel").pack(side="left", pady=(7, 0))
        ttk.Button(top, text="Project খুলুন", command=self.open_project).pack(side="right", padx=4)
        ttk.Button(top, text="Project Save", command=self.save_project).pack(side="right", padx=4)
        ttk.Button(top, text="ভিডিও দিন", style="Accent.TButton", command=self.open_video).pack(side="right", padx=4)

        main = ttk.Panedwindow(self, orient="horizontal")
        main.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        preview_panel = ttk.Frame(main, style="Panel.TFrame", padding=12)
        controls_panel = ttk.Frame(main, style="Panel.TFrame", padding=4, width=470)
        main.add(preview_panel, weight=3)
        main.add(controls_panel, weight=2)

        video_header = ttk.Frame(preview_panel, style="Panel.TFrame")
        video_header.pack(fill="x", pady=(0, 8))
        ttk.Label(video_header, textvariable=self.video_name_var, font=("Nirmala UI", 11, "bold")).pack(side="left")
        ttk.Label(video_header, textvariable=self.time_var, style="Muted.TLabel").pack(side="right")

        canvas_holder = tk.Frame(preview_panel, bg="#050A12", highlightbackground="#2A3D5C", highlightthickness=1)
        canvas_holder.pack(fill="both", expand=True)
        self.preview_canvas = tk.Canvas(canvas_holder, bg="#050A12", highlightthickness=0, cursor="arrow")
        self.preview_canvas.pack(fill="both", expand=True, padx=1, pady=1)
        self.preview_canvas.bind("<Configure>", lambda _event: self._redraw_preview())
        self.preview_canvas.tag_bind("logo", "<ButtonPress-1>", self._start_logo_drag)
        self.preview_canvas.tag_bind("logo", "<B1-Motion>", self._drag_logo)

        transport = ttk.Frame(preview_panel, style="Panel.TFrame")
        transport.pack(fill="x", pady=(8, 0))
        self.play_button = ttk.Button(transport, text="▶ Preview", command=self.toggle_playback)
        self.play_button.pack(side="left", padx=(0, 8))
        self.seek_scale = ttk.Scale(transport, from_=0, to=1, variable=self.seek_var, command=self._on_seek)
        self.seek_scale.pack(side="left", fill="x", expand=True)
        ttk.Button(transport, text="Frame", command=lambda: self.request_preview(self.current_time)).pack(side="left", padx=(8, 0))

        hint = "Preview-তে লোগো মাউস দিয়ে টেনে নিন • Subtitle লাইনে double-click করলে Edit হবে"
        ttk.Label(preview_panel, text=hint, style="Muted.TLabel").pack(anchor="w", pady=(7, 0))

        self.notebook = ttk.Notebook(controls_panel)
        self.notebook.pack(fill="both", expand=True)
        self.subtitle_tab = ttk.Frame(self.notebook, style="Panel.TFrame", padding=10)
        self.voice_tab = ScrollableTab(self.notebook)
        self.style_tab = ScrollableTab(self.notebook)
        self.logo_tab = ScrollableTab(self.notebook)
        self.color_tab = ScrollableTab(self.notebook)
        self.export_tab = ScrollableTab(self.notebook)
        self.notebook.add(self.subtitle_tab, text="সাবটাইটেল")
        self.notebook.add(self.voice_tab, text="Voice Translate")
        self.notebook.add(self.style_tab, text="স্টাইল")
        self.notebook.add(self.logo_tab, text="লোগো")
        self.notebook.add(self.color_tab, text="কালার")
        self.notebook.add(self.export_tab, text="Export")
        self._build_subtitle_tab()
        self._build_voice_tab(self.voice_tab.body)
        self._build_style_tab(self.style_tab.body)
        self._build_logo_tab(self.logo_tab.body)
        self._build_color_tab(self.color_tab.body)
        self._build_export_tab(self.export_tab.body)

        bottom = ttk.Frame(self, style="Panel.TFrame", padding=(14, 7))
        bottom.pack(fill="x")
        ttk.Label(bottom, textvariable=self.status_var).pack(side="left", fill="x", expand=True)
        self.progress = ttk.Progressbar(bottom, variable=self.progress_var, maximum=100, length=270)
        self.progress.pack(side="right", padx=(8, 0))

    def _section(self, parent: tk.Misc, title: str) -> ttk.Frame:
        card = ttk.Frame(parent, style="Card.TFrame", padding=12)
        card.pack(fill="x", pady=(0, 10), padx=2)
        ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))
        return card

    def _build_subtitle_tab(self) -> None:
        generator = self._section(self.subtitle_tab, "খরচ ছাড়া Offline বাংলা Subtitle তৈরি")
        ttk.Label(
            generator,
            textvariable=self.offline_status_var,
            foreground="#65E6A3",
            background="#1B2940",
            font=("Nirmala UI", 10, "bold"),
            wraplength=390,
        ).pack(anchor="w", fill="x", pady=(0, 5))
        ttk.Label(
            generator,
            text="AI Model: V2.2 Accurate Bangla + Voice Timing + Meaning-Checked Translation",
            style="Muted.TLabel",
            wraplength=390,
        ).pack(anchor="w", fill="x", pady=(0, 10))
        lang_row = ttk.Frame(generator, style="Card.TFrame")
        lang_row.pack(fill="x", pady=(0, 8))
        ttk.Label(lang_row, text="সাবটাইটেলের ভাষা", style="CardTitle.TLabel").pack(side="left")
        ttk.Combobox(lang_row, textvariable=self.language_var, values=list(LANGUAGES), state="readonly", width=24).pack(side="right")
        sync_row = ttk.Frame(generator, style="Card.TFrame")
        sync_row.pack(fill="x", pady=(0, 8))
        ttk.Label(sync_row, text="তৈরির সময় Subtitle আগে (সেকেন্ড)").pack(side="left")
        ttk.Spinbox(
            sync_row,
            from_=0.0,
            to=2.0,
            increment=0.05,
            textvariable=self.subtitle_lead_var,
            width=7,
        ).pack(side="right")
        ttk.Label(generator, text="বিশেষ নাম/শব্দ (ঐচ্ছিক)", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Entry(generator, textvariable=self.prompt_var).pack(fill="x", pady=(4, 8))
        action_row = ttk.Frame(generator, style="Card.TFrame")
        action_row.pack(fill="x")
        self.generate_button = ttk.Button(action_row, text="Offline Generate Subtitle", style="Accent.TButton", command=self.generate_subtitles)
        self.generate_button.pack(side="left", fill="x", expand=True)
        self.cancel_button = ttk.Button(action_row, text="বাতিল", style="Danger.TButton", command=self.cancel_task, state="disabled")
        self.cancel_button.pack(side="left", padx=(6, 0))

        tools = ttk.Frame(self.subtitle_tab, style="Panel.TFrame")
        tools.pack(fill="x", pady=(0, 8))
        ttk.Button(tools, text="SRT Import", command=self.import_srt).pack(side="left", padx=(0, 4))
        ttk.Button(tools, text="SRT Save", command=self.export_srt).pack(side="left", padx=4)
        ttk.Button(tools, text="+ Line", command=self.add_segment).pack(side="left", padx=4)
        ttk.Button(tools, text="Delete", style="Danger.TButton", command=self.delete_segment).pack(side="right")

        sync_tools = ttk.Frame(self.subtitle_tab, style="Card.TFrame", padding=9)
        sync_tools.pack(fill="x", pady=(0, 8))
        sync_header = ttk.Frame(sync_tools, style="Card.TFrame")
        sync_header.pack(fill="x", pady=(0, 6))
        ttk.Label(sync_header, text="সব Subtitle-এর Global Sync", style="CardTitle.TLabel").pack(side="left")
        ttk.Label(sync_header, textvariable=self.sync_status_var, style="CardTitle.TLabel").pack(side="right")
        sync_controls = ttk.Frame(sync_tools, style="Card.TFrame")
        sync_controls.pack(fill="x")
        ttk.Label(sync_controls, text="প্রতি ক্লিক").pack(side="left")
        ttk.Spinbox(
            sync_controls,
            from_=0.05,
            to=2.0,
            increment=0.05,
            textvariable=self.sync_step_var,
            width=5,
        ).pack(side="left", padx=(4, 7))
        ttk.Button(sync_controls, text="◀ আগে", command=lambda: self._adjust_global_sync(-1)).pack(side="left", padx=2)
        ttk.Button(sync_controls, text="পরে ▶", command=lambda: self._adjust_global_sync(1)).pack(side="left", padx=2)
        ttk.Button(sync_controls, text="Reset", command=self._reset_global_sync).pack(side="right", padx=2)

        tree_holder = ttk.Frame(self.subtitle_tab, style="Panel.TFrame")
        tree_holder.pack(fill="both", expand=True)
        self.subtitle_tree = ttk.Treeview(tree_holder, columns=("start", "end", "text"), show="headings", selectmode="browse")
        self.subtitle_tree.heading("start", text="শুরু")
        self.subtitle_tree.heading("end", text="শেষ")
        self.subtitle_tree.heading("text", text="লেখা")
        self.subtitle_tree.column("start", width=74, stretch=False)
        self.subtitle_tree.column("end", width=74, stretch=False)
        self.subtitle_tree.column("text", width=250, stretch=True)
        scrollbar = ttk.Scrollbar(tree_holder, orient="vertical", command=self.subtitle_tree.yview)
        self.subtitle_tree.configure(yscrollcommand=scrollbar.set)
        self.subtitle_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.subtitle_tree.bind("<Double-1>", lambda _event: self.edit_segment())
        self.subtitle_tree.bind("<<TreeviewSelect>>", self._select_segment)

    def _build_voice_tab(self, parent: tk.Misc) -> None:
        language_card = self._section(parent, "Multilanguage Voice Translate / Dubbing")
        ttk.Label(
            language_card,
            text="বাংলা ↔ English ↔ Hindi ↔ Arabicসহ সমর্থিত ভাষার voice পরিবর্তন করুন।",
            style="Muted.TLabel",
            wraplength=390,
        ).pack(anchor="w", fill="x", pady=(0, 8))
        ttk.Label(
            language_card,
            text="Natural voice-এর জন্য Internet লাগবে • API key বা প্রতি ভিডিওর টাকা লাগবে না",
            foreground="#65E6A3",
            background="#1B2940",
            font=("Nirmala UI", 9, "bold"),
            wraplength=390,
        ).pack(anchor="w", fill="x", pady=(0, 10))
        ttk.Label(language_card, text="মূল voice-এর ভাষা", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Combobox(
            language_card,
            textvariable=self.voice_source_var,
            values=list(VOICE_LANGUAGES),
            state="readonly",
        ).pack(fill="x", pady=(3, 9))
        ttk.Label(language_card, text="নতুন voice-এর ভাষা", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Combobox(
            language_card,
            textvariable=self.voice_target_var,
            values=list(VOICE_LANGUAGES),
            state="readonly",
        ).pack(fill="x", pady=(3, 9))
        ttk.Label(language_card, text="নতুন কণ্ঠ", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Combobox(
            language_card,
            textvariable=self.voice_gender_var,
            values=["নারী কণ্ঠ", "পুরুষ কণ্ঠ"],
            state="readonly",
        ).pack(fill="x", pady=(3, 4))

        audio_card = self._section(parent, "নতুন voice ও সময়")
        ttk.Label(
            audio_card,
            text="প্রতিটি অনুবাদ করা বাক্যের voice মূল কথার শুরু, শেষ ও বিরতির সঙ্গে মেলানো হবে।",
            style="Muted.TLabel",
            wraplength=390,
        ).pack(anchor="w", fill="x")
        self._labeled_scale(
            audio_card,
            "পুরোনো অডিও Volume (%)",
            self.voice_original_volume_var,
            0,
            30,
            lambda: None,
        )
        ttk.Label(
            audio_card,
            text="০% রাখলে মূল ভাষার voice সম্পূর্ণ বন্ধ থাকবে।",
            style="Muted.TLabel",
            wraplength=390,
        ).pack(anchor="w", pady=(4, 8))
        ttk.Checkbutton(
            audio_card,
            text="Translated লেখাগুলো Subtitle হিসেবে প্রস্তুত রাখুন",
            variable=self.voice_add_subtitles_var,
        ).pack(anchor="w", pady=3)

        output_card = self._section(parent, "Translated Voice Video")
        ttk.Label(output_card, text="Output MP4 file", style="CardTitle.TLabel").pack(anchor="w")
        output_row = ttk.Frame(output_card, style="Card.TFrame")
        output_row.pack(fill="x", pady=(4, 10))
        ttk.Entry(output_row, textvariable=self.voice_output_var).pack(side="left", fill="x", expand=True)
        ttk.Button(output_row, text="...", width=4, command=self.choose_voice_output).pack(side="left", padx=(4, 0))
        voice_actions = ttk.Frame(output_card, style="Card.TFrame")
        voice_actions.pack(fill="x")
        self.voice_translate_button = ttk.Button(
            voice_actions,
            text="Voice Translate শুরু করুন",
            style="Accent.TButton",
            command=self.start_voice_translation,
        )
        self.voice_translate_button.pack(side="left", fill="x", expand=True)
        self.voice_cancel_button = ttk.Button(
            voice_actions,
            text="বাতিল",
            style="Danger.TButton",
            command=self.cancel_task,
            state="disabled",
        )
        self.voice_cancel_button.pack(side="left", padx=(6, 0))
        ttk.Label(
            output_card,
            text="কাজ শেষে translated video-টি বর্তমান ভিডিও হবে এবং Subtitle tab-এ অনুবাদের লেখা পাওয়া যাবে।",
            style="Muted.TLabel",
            wraplength=390,
        ).pack(anchor="w", fill="x", pady=(9, 0))

    def _build_style_tab(self, parent: tk.Misc) -> None:
        card = self._section(parent, "ফন্ট ও লেখা")
        ttk.Label(card, text="Font").pack(anchor="w")
        fonts = sorted(set(tkfont.families(self)))
        preferred = [name for name in ["Nirmala UI", "Noto Sans Bengali", "SolaimanLipi", "Kalpurush"] if name in fonts]
        ttk.Combobox(card, textvariable=self.font_var, values=preferred + [f for f in fonts if f not in preferred], state="readonly").pack(fill="x", pady=(3, 8))
        self._labeled_scale(card, "লেখার Size", self.font_size_var, 24, 110, self._sync_style)
        self._labeled_scale(card, "Outline", self.outline_var, 0, 10, self._sync_style)
        self._labeled_scale(card, "Shadow", self.shadow_var, 0, 8, self._sync_style)
        ttk.Checkbutton(card, text="Bold লেখা", variable=self.bold_var, command=self._sync_style).pack(anchor="w", pady=3)
        ttk.Checkbutton(card, text="লেখার Background box", variable=self.background_var, command=self._sync_style).pack(anchor="w", pady=3)
        ttk.Checkbutton(card, text="দ্বিতীয় ভাষার লাইন দেখান", variable=self.show_secondary_var, command=self._sync_style).pack(anchor="w", pady=3)

        colors = self._section(parent, "Subtitle Color")
        self.primary_color_button = ttk.Button(colors, text="মূল লেখার রং", command=lambda: self._choose_color("primary"))
        self.primary_color_button.pack(fill="x", pady=3)
        self.secondary_color_button = ttk.Button(colors, text="দ্বিতীয় ভাষার রং", command=lambda: self._choose_color("secondary"))
        self.secondary_color_button.pack(fill="x", pady=3)
        self.outline_color_button = ttk.Button(colors, text="Outline রং", command=lambda: self._choose_color("outline"))
        self.outline_color_button.pack(fill="x", pady=3)
        self.background_color_button = ttk.Button(colors, text="Background রং", command=lambda: self._choose_color("background"))
        self.background_color_button.pack(fill="x", pady=3)

        position = self._section(parent, "অবস্থান ও লাইন")
        ttk.Label(position, text="ভিডিওতে অবস্থান").pack(anchor="w")
        combo = ttk.Combobox(position, textvariable=self.position_var, values=["উপরে", "মাঝখানে", "নিচে"], state="readonly")
        combo.pack(fill="x", pady=(3, 8))
        combo.bind("<<ComboboxSelected>>", lambda _event: self._sync_style())
        self._labeled_scale(position, "কিনারা থেকে দূরত্ব", self.margin_var, 10, 250, self._sync_style)
        self._labeled_scale(position, "এক লাইনের অক্ষর", self.max_chars_var, 20, 90, self._sync_style)

    def _build_logo_tab(self, parent: tk.Misc) -> None:
        card = self._section(parent, "ভিডিওর ওপর Logo Layer")
        self.logo_name_label = ttk.Label(card, text="কোনো লোগো নেই", style="Muted.TLabel", wraplength=360)
        self.logo_name_label.pack(anchor="w", fill="x", pady=(0, 8))
        row = ttk.Frame(card, style="Card.TFrame")
        row.pack(fill="x")
        ttk.Button(row, text="লোগো দিন", style="Accent.TButton", command=self.choose_logo).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Remove", style="Danger.TButton", command=self.remove_logo).pack(side="left", padx=(6, 0))
        self._labeled_scale(card, "লোগোর Size (%)", self.logo_scale_var, 3, 60, self._sync_logo)
        self._labeled_scale(card, "Opacity (%)", self.logo_opacity_var, 10, 100, self._sync_logo)

        position = self._section(parent, "Logo Position")
        ttk.Label(position, text="Preview-তে মাউস দিয়ে লোগো টেনে নেওয়া যাবে।", style="Muted.TLabel", wraplength=360).pack(anchor="w", pady=(0, 8))
        grid = ttk.Frame(position, style="Card.TFrame")
        grid.pack()
        positions = [
            ("↖", 0, 0, 2, 2), ("↑", 0, 1, 50, 2), ("↗", 0, 2, 98, 2),
            ("←", 1, 0, 2, 50), ("●", 1, 1, 50, 50), ("→", 1, 2, 98, 50),
            ("↙", 2, 0, 2, 98), ("↓", 2, 1, 50, 98), ("↘", 2, 2, 98, 98),
        ]
        for label, row_index, col, x_value, y_value in positions:
            ttk.Button(grid, text=label, width=6, command=lambda x=x_value, y=y_value: self._set_logo_position(x, y)).grid(row=row_index, column=col, padx=3, pady=3)

        timing = self._section(parent, "কতক্ষণ Logo দেখাবে")
        ttk.Label(timing, text="শুরুর সময় (HH:MM:SS,mmm)").pack(anchor="w")
        ttk.Entry(timing, textvariable=self.logo_start_var).pack(fill="x", pady=(3, 8))
        ttk.Label(timing, text="শেষ সময় অথবা ‘ভিডিওর শেষ পর্যন্ত’").pack(anchor="w")
        ttk.Entry(timing, textvariable=self.logo_end_var).pack(fill="x", pady=(3, 8))
        ttk.Button(timing, text="সময় Apply", command=self._apply_logo_times).pack(fill="x")

    def _build_color_tab(self, parent: tk.Misc) -> None:
        presets = self._section(parent, "Ready Color Collection")
        preset_grid = ttk.Frame(presets, style="Card.TFrame")
        preset_grid.pack(fill="x")
        preset_values = ["Natural", "Warm", "Cool", "Cinematic", "Vivid", "B&W"]
        for index, name in enumerate(preset_values):
            ttk.Button(preset_grid, text=name, command=lambda value=name: self.apply_preset(value)).grid(row=index // 2, column=index % 2, sticky="ew", padx=3, pady=3)
        preset_grid.columnconfigure(0, weight=1)
        preset_grid.columnconfigure(1, weight=1)

        manual = self._section(parent, "Manual Color Correction")
        self._labeled_scale(manual, "Brightness", self.brightness_var, -0.5, 0.5, self._sync_color)
        self._labeled_scale(manual, "Contrast", self.contrast_var, 0.5, 2.0, self._sync_color)
        self._labeled_scale(manual, "Saturation", self.saturation_var, 0.0, 2.5, self._sync_color)
        self._labeled_scale(manual, "Temperature", self.temperature_var, -50, 50, self._sync_color)
        self._labeled_scale(manual, "Tint", self.tint_var, -50, 50, self._sync_color)
        ttk.Button(manual, text="সব Color Reset", command=lambda: self.apply_preset("Natural")).pack(fill="x", pady=(8, 0))

    def _build_export_tab(self, parent: tk.Misc) -> None:
        summary = self._section(parent, "Final Video Export")
        ttk.Label(summary, text="Subtitle, logo এবং color একসঙ্গে নতুন MP4 ভিডিওতে বসবে।", style="Muted.TLabel", wraplength=360).pack(anchor="w", pady=(0, 10))
        ttk.Label(summary, text="Output file").pack(anchor="w")
        output_row = ttk.Frame(summary, style="Card.TFrame")
        output_row.pack(fill="x", pady=(3, 10))
        ttk.Entry(output_row, textvariable=self.output_var).pack(side="left", fill="x", expand=True)
        ttk.Button(output_row, text="...", width=4, command=self.choose_output).pack(side="left", padx=(4, 0))
        ttk.Label(summary, text="Quality").pack(anchor="w")
        ttk.Combobox(summary, textvariable=self.quality_var, values=["High", "Balanced", "Small"], state="readonly").pack(fill="x", pady=(3, 12))
        self.export_button = ttk.Button(summary, text="Export Video", style="Accent.TButton", command=self.start_export)
        self.export_button.pack(fill="x")

        project_card = self._section(parent, "Project")
        ttk.Button(project_card, text="Project Save", command=self.save_project).pack(fill="x", pady=3)
        ttk.Button(project_card, text="Project খুলুন", command=self.open_project).pack(fill="x", pady=3)
        ttk.Label(project_card, text="Project ও ভিডিও আপনার কম্পিউটারেই থাকে।", style="Muted.TLabel", wraplength=360).pack(anchor="w", pady=(8, 0))

    def _labeled_scale(
        self,
        parent: tk.Misc,
        label: str,
        variable: tk.DoubleVar,
        minimum: float,
        maximum: float,
        callback,
    ) -> None:
        row = ttk.Frame(parent, style=parent.cget("style") if isinstance(parent, ttk.Frame) else "Panel.TFrame")
        row.pack(fill="x", pady=(6, 0))
        text_var = tk.StringVar()

        def update(value: str | None = None) -> None:
            number = variable.get()
            text_var.set(f"{number:.2f}" if maximum <= 3 else f"{number:.0f}")
            callback()

        ttk.Label(row, text=label, style="CardTitle.TLabel" if isinstance(parent, ttk.Frame) and parent.cget("style") == "Card.TFrame" else "TLabel").pack(side="left")
        ttk.Label(row, textvariable=text_var, style="Muted.TLabel").pack(side="right")
        scale = ttk.Scale(parent, from_=minimum, to=maximum, variable=variable, command=update)
        scale.pack(fill="x", pady=(2, 0))
        update()

    def _draw_placeholder(self) -> None:
        self.preview_canvas.delete("all")
        width = max(300, self.preview_canvas.winfo_width())
        height = max(200, self.preview_canvas.winfo_height())
        self.preview_canvas.create_text(width / 2, height / 2 - 15, text="ভিডিও দিন", fill="#FFFFFF", font=("Nirmala UI", 24, "bold"))
        self.preview_canvas.create_text(width / 2, height / 2 + 28, text="বাংলা Subtitle • Logo • Color • Export", fill="#8294AF", font=("Nirmala UI", 12))

    def open_video(self) -> None:
        path = filedialog.askopenfilename(
            title="ভিডিও নির্বাচন করুন",
            filetypes=[("Video files", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v"), ("সব ফাইল", "*.*")],
        )
        if not path:
            return
        self.stop_playback()
        try:
            info = probe_video(path)
        except MediaError as exc:
            messagebox.showerror("ভিডিও খোলা যায়নি", str(exc), parent=self)
            return
        self.project.video_path = path
        self.project.duration = float(info["duration"])
        self.project.width = int(info["width"])
        self.project.height = int(info["height"])
        self.project.fps = float(info["fps"])
        self.project.output_path = self.project.default_output_path()
        self.output_var.set(self.project.output_path)
        target_code = VOICE_LANGUAGES.get(self.voice_target_var.get(), "en")
        self.voice_output_var.set(
            str(Path(path).with_name(f"{Path(path).stem}_{target_code}_voice.mp4"))
        )
        self.current_time = 0.0
        self.seek_var.set(0.0)
        self.seek_scale.configure(to=max(0.1, self.project.duration))
        self.video_name_var.set(f"{Path(path).name}  •  {self.project.width}×{self.project.height}")
        self._update_time_label()
        self.status_var.set("ভিডিও প্রস্তুত। Offline Generate Subtitle ক্লিক করুন।")
        self.request_preview(0.0)

    def request_preview(self, seconds: float) -> None:
        if not self.project.video_path:
            return
        self.preview_serial += 1
        serial = self.preview_serial
        self.status_var.set("Preview তৈরি হচ্ছে…")

        def worker() -> None:
            try:
                image = extract_frame(self.project.video_path, seconds, *PREVIEW_SIZE)
                self.after(0, lambda: self._receive_preview(serial, seconds, image, None))
            except Exception as exc:
                self.after(0, lambda error=exc: self._receive_preview(serial, seconds, None, error))

        threading.Thread(target=worker, daemon=True).start()

    def _receive_preview(self, serial: int, seconds: float, image: Image.Image | None, error: Exception | None) -> None:
        if serial != self.preview_serial:
            return
        if error:
            self.status_var.set(str(error))
            return
        self.current_time = seconds
        self.last_frame = image
        self._redraw_preview()
        self._update_time_label()
        self.status_var.set("Preview প্রস্তুত।")

    def _on_seek(self, value: str) -> None:
        if not self.project.video_path:
            return
        seconds = max(0.0, min(float(value), self.project.duration))
        self.current_time = seconds
        self._update_time_label()
        self._redraw_preview()
        if self.playing:
            self.stop_playback()
        if self.preview_job:
            self.after_cancel(self.preview_job)
        self.preview_job = self.after(220, lambda: self.request_preview(seconds))

    def toggle_playback(self) -> None:
        if self.playing:
            self.stop_playback()
        else:
            self.start_playback()

    def start_playback(self) -> None:
        if not self.project.video_path:
            messagebox.showinfo(APP_NAME, "প্রথমে ভিডিও দিন।", parent=self)
            return
        self.stop_playback()
        try:
            ffmpeg = bundled_tool("ffmpeg")
        except MediaError as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return
        self.playing = True
        self.play_button.configure(text="⏸ থামান")
        self.status_var.set("ভিডিও Preview চলছে…")
        start = self.current_time
        width, height, fps = PREVIEW_SIZE[0], PREVIEW_SIZE[1], 20
        vf = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x101827,fps={fps}"
        command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", self.project.video_path, "-an", "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]
        self.play_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, startupinfo=_startupinfo())
        try:
            ffplay = bundled_tool("ffplay")
            self.audio_process = subprocess.Popen([ffplay, "-nodisp", "-autoexit", "-loglevel", "quiet", "-ss", f"{start:.3f}", "-i", self.project.video_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=_startupinfo())
        except MediaError:
            self.audio_process = None

        def reader() -> None:
            assert self.play_process and self.play_process.stdout
            frame_bytes = width * height * 3
            frame_index = 0
            target = time.monotonic()
            while self.playing:
                data = self.play_process.stdout.read(frame_bytes)
                if len(data) != frame_bytes:
                    break
                image = Image.frombytes("RGB", (width, height), data)
                seconds = start + frame_index / fps
                frame_index += 1
                try:
                    self.play_queue.put((image, seconds), timeout=0.1)
                except queue.Full:
                    pass
                target += 1 / fps
                delay = target - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
            try:
                self.play_queue.put(None, timeout=0.1)
            except queue.Full:
                pass

        threading.Thread(target=reader, daemon=True).start()
        self.after(20, self._poll_playback)

    def _poll_playback(self) -> None:
        if not self.playing:
            return
        latest: tuple[Image.Image, float] | None = None
        try:
            while True:
                item = self.play_queue.get_nowait()
                if item is None:
                    self.stop_playback()
                    return
                latest = item
        except queue.Empty:
            pass
        if latest:
            self.last_frame, self.current_time = latest
            self.seek_var.set(self.current_time)
            self._update_time_label()
            self._redraw_preview()
            if self.current_time >= self.project.duration:
                self.stop_playback()
                return
        self.after(20, self._poll_playback)

    def stop_playback(self) -> None:
        was_playing = self.playing
        self.playing = False
        for process in (self.play_process, self.audio_process):
            if process and process.poll() is None:
                try:
                    process.terminate()
                except OSError:
                    pass
        self.play_process = None
        self.audio_process = None
        while not self.play_queue.empty():
            try:
                self.play_queue.get_nowait()
            except queue.Empty:
                break
        if hasattr(self, "play_button"):
            self.play_button.configure(text="▶ Preview")
        if was_playing:
            self.status_var.set("Preview থামানো হয়েছে।")

    def _apply_preview_color(self, image: Image.Image) -> Image.Image:
        color = self.project.color
        result = ImageEnhance.Brightness(image).enhance(max(0.0, 1.0 + color.brightness))
        result = ImageEnhance.Contrast(result).enhance(max(0.0, color.contrast))
        result = ImageEnhance.Color(result).enhance(max(0.0, color.saturation))
        if abs(color.temperature) > 0.01 or abs(color.tint) > 0.01:
            red, green, blue = result.split()
            red = red.point(lambda value: max(0, min(255, value * (1 + color.temperature / 150))))
            blue = blue.point(lambda value: max(0, min(255, value * (1 - color.temperature / 150))))
            green = green.point(lambda value: max(0, min(255, value * (1 + color.tint / 180))))
            result = Image.merge("RGB", (red, green, blue))
        return result

    def _redraw_preview(self) -> None:
        if not hasattr(self, "preview_canvas"):
            return
        if self.last_frame is None:
            self._draw_placeholder()
            return
        canvas_width = max(1, self.preview_canvas.winfo_width())
        canvas_height = max(1, self.preview_canvas.winfo_height())
        ratio = min(canvas_width / PREVIEW_SIZE[0], canvas_height / PREVIEW_SIZE[1])
        width = max(1, int(PREVIEW_SIZE[0] * ratio))
        height = max(1, int(PREVIEW_SIZE[1] * ratio))
        x0 = (canvas_width - width) / 2
        y0 = (canvas_height - height) / 2
        image = self._apply_preview_color(self.last_frame).resize((width, height), Image.Resampling.LANCZOS)
        self.preview_photo = ImageTk.PhotoImage(image)
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(canvas_width / 2, canvas_height / 2, image=self.preview_photo)
        self._draw_logo(x0, y0, width, height)
        self._draw_subtitle(x0, y0, width, height)

    def _draw_logo(self, x0: float, y0: float, width: int, height: int) -> None:
        logo = self.project.logo
        end = self.project.duration if logo.end < 0 else logo.end
        if not logo.enabled or not logo.path or not (logo.start <= self.current_time <= end):
            return
        try:
            image = Image.open(logo.path).convert("RGBA")
        except (OSError, ValueError):
            return
        target_width = max(12, round(width * logo.scale_percent / 100))
        target_height = max(8, round(target_width * image.height / max(1, image.width)))
        image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        if logo.opacity < 100:
            alpha = image.getchannel("A").point(lambda value: int(value * max(0, logo.opacity) / 100))
            image.putalpha(alpha)
        self.logo_photo = ImageTk.PhotoImage(image)
        x = x0 + target_width / 2 + (width - target_width) * logo.x_percent / 100
        y = y0 + target_height / 2 + (height - target_height) * logo.y_percent / 100
        self.preview_canvas.create_image(x, y, image=self.logo_photo, tags=("logo",))

    def _current_segment(self) -> SubtitleSegment | None:
        for segment in self.project.subtitles:
            if segment.start <= self.current_time <= segment.end:
                return segment
        return None

    def _draw_subtitle(self, x0: float, y0: float, width: int, height: int) -> None:
        segment = self._current_segment()
        if not segment:
            return
        style = self.project.subtitle_style
        text = segment.text
        if style.show_secondary and segment.secondary_text:
            text += "\n" + segment.secondary_text
        position_ratio = {"top": 0.12, "middle": 0.5, "bottom": 0.88}.get(style.position, 0.88)
        if style.position == "top":
            y = y0 + max(10, style.margin_v * height / 1080)
            anchor = "n"
        elif style.position == "middle":
            y = y0 + height * position_ratio
            anchor = "center"
        else:
            y = y0 + height - max(10, style.margin_v * height / 1080)
            anchor = "s"
        font_size = max(10, round(style.font_size * height / 1080))
        font = (style.font_name, font_size, "bold" if style.bold else "normal")
        kwargs = {
            "text": text,
            "fill": style.primary_color,
            "font": font,
            "width": int(width * 0.9),
            "justify": "center",
            "anchor": anchor,
            "tags": ("subtitle",),
        }
        outline_width = max(0, round(style.outline * height / 1080))
        if outline_width:
            kwargs["stipple"] = ""
        text_id = self.preview_canvas.create_text(x0 + width / 2, y, **kwargs)
        if style.background:
            bbox = self.preview_canvas.bbox(text_id)
            if bbox:
                pad = 8
                rect = self.preview_canvas.create_rectangle(bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad, fill=style.background_color, outline="", tags=("subtitle_bg",))
                self.preview_canvas.tag_lower(rect, text_id)
        if outline_width:
            # Tk's stippled duplicate offsets provide a lightweight preview of the final ASS outline.
            coords = self.preview_canvas.coords(text_id)
            self.preview_canvas.delete(text_id)
            for dx, dy in [(-outline_width, 0), (outline_width, 0), (0, -outline_width), (0, outline_width)]:
                self.preview_canvas.create_text(coords[0] + dx, coords[1] + dy, **{**kwargs, "fill": style.outline_color, "tags": ("subtitle_outline",)})
            self.preview_canvas.create_text(coords[0], coords[1], **kwargs)

    def _start_logo_drag(self, event: tk.Event) -> None:
        bbox = self.preview_canvas.bbox("logo")
        if bbox:
            self.logo_drag_offset = (event.x - (bbox[0] + bbox[2]) / 2, event.y - (bbox[1] + bbox[3]) / 2)

    def _drag_logo(self, event: tk.Event) -> None:
        canvas_width = self.preview_canvas.winfo_width()
        canvas_height = self.preview_canvas.winfo_height()
        ratio = min(canvas_width / PREVIEW_SIZE[0], canvas_height / PREVIEW_SIZE[1])
        width, height = PREVIEW_SIZE[0] * ratio, PREVIEW_SIZE[1] * ratio
        x0, y0 = (canvas_width - width) / 2, (canvas_height - height) / 2
        bbox = self.preview_canvas.bbox("logo")
        if not bbox:
            return
        logo_width, logo_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        center_x = event.x - self.logo_drag_offset[0]
        center_y = event.y - self.logo_drag_offset[1]
        self.project.logo.x_percent = max(0.0, min(100.0, (center_x - x0 - logo_width / 2) / max(1, width - logo_width) * 100))
        self.project.logo.y_percent = max(0.0, min(100.0, (center_y - y0 - logo_height / 2) / max(1, height - logo_height) * 100))
        self._redraw_preview()

    def generate_subtitles(self) -> None:
        if self.busy:
            return
        if not self.project.video_path:
            messagebox.showinfo(APP_NAME, "প্রথমে একটি ভিডিও দিন।", parent=self)
            return
        if self.project.subtitles and not messagebox.askyesno("নতুন Subtitle", "বর্তমান subtitle বাদ দিয়ে নতুন করে তৈরি করবেন?", parent=self):
            return
        self._set_busy(True)
        self.busy_cancel.clear()
        target_language = LANGUAGES.get(self.language_var.get(), "bn")
        prompt_text = self.prompt_var.get()
        lead_seconds = self.subtitle_lead_var.get()

        def progress(value: float, message: str) -> None:
            self.after(0, lambda: self._update_progress(value, message))

        def worker() -> None:
            try:
                needs_conversion = target_language != "bn"

                def transcribe_progress(value: float, message: str) -> None:
                    progress(value * (0.84 if needs_conversion else 1.0), message)

                segments = transcribe_video(
                    self.project.video_path,
                    self.project.duration,
                    "bn",
                    prompt_text,
                    transcribe_progress,
                    self.busy_cancel,
                )
                segments = shift_segments_earlier(segments, lead_seconds)

                def translation_progress(value: float, message: str) -> None:
                    progress(0.84 + max(0.0, min(1.0, value)) * 0.16, message)

                segments = translate_segments(
                    segments,
                    target_language,
                    translation_progress if needs_conversion else progress,
                    self.busy_cancel,
                )
                self.after(0, lambda: self._finish_transcription(segments, None))
            except Exception as exc:
                self.after(0, lambda error=exc: self._finish_transcription([], error))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_transcription(self, segments: list[SubtitleSegment], error: Exception | None) -> None:
        self._set_busy(False)
        if error:
            self.status_var.set(str(error))
            messagebox.showerror("Subtitle তৈরি হয়নি", str(error), parent=self)
            return
        self.project.subtitles = segments
        self._capture_sync_baseline()
        self._refresh_subtitle_tree()
        self.status_var.set(f"{len(segments)}টি subtitle line তৈরি হয়েছে। ভুল থাকলে double-click করে ঠিক করুন।")
        self.progress_var.set(100)
        self.request_preview(self.current_time)

    @staticmethod
    def _copy_segments(segments: list[SubtitleSegment]) -> list[SubtitleSegment]:
        return [
            SubtitleSegment(item.start, item.end, item.text, item.secondary_text)
            for item in segments
        ]

    def _capture_sync_baseline(self) -> None:
        self._sync_baseline = self._copy_segments(self.project.subtitles)
        self._global_sync_offset = 0.0
        self.sync_status_var.set("বর্তমান পরিবর্তন: 0.00 সেকেন্ড")

    def _adjust_global_sync(self, direction: int) -> None:
        if not self.project.subtitles:
            messagebox.showinfo(APP_NAME, "আগে Subtitle তৈরি অথবা SRT Import করুন।", parent=self)
            return
        if len(self._sync_baseline) != len(self.project.subtitles):
            self._capture_sync_baseline()
        try:
            step = max(0.05, min(2.0, float(self.sync_step_var.get())))
        except (TypeError, ValueError, tk.TclError):
            step = 0.10
            self.sync_step_var.set(step)
        self._global_sync_offset = max(
            -30.0,
            min(30.0, self._global_sync_offset + (-step if direction < 0 else step)),
        )
        self.project.subtitles = shift_segments(
            self._sync_baseline,
            self._global_sync_offset,
        )
        if self._global_sync_offset < 0:
            label = f"{abs(self._global_sync_offset):.2f} সেকেন্ড আগে"
        elif self._global_sync_offset > 0:
            label = f"{self._global_sync_offset:.2f} সেকেন্ড পরে"
        else:
            label = "0.00 সেকেন্ড"
        self.sync_status_var.set(f"বর্তমান পরিবর্তন: {label}")
        self.status_var.set(f"সব ভাষার সম্পূর্ণ Subtitle {label} করা হয়েছে।")
        self._refresh_subtitle_tree()
        self.request_preview(self.current_time)

    def _reset_global_sync(self) -> None:
        if not self._sync_baseline:
            self._capture_sync_baseline()
            return
        self.project.subtitles = self._copy_segments(self._sync_baseline)
        self._global_sync_offset = 0.0
        self.sync_status_var.set("বর্তমান পরিবর্তন: 0.00 সেকেন্ড")
        self.status_var.set("Global Subtitle Sync Reset হয়েছে।")
        self._refresh_subtitle_tree()
        self.request_preview(self.current_time)

    def cancel_task(self) -> None:
        self.busy_cancel.set()
        self.status_var.set("বাতিল করা হচ্ছে…")

    def _set_busy(self, value: bool) -> None:
        self.busy = value
        state = "disabled" if value else "normal"
        self.generate_button.configure(state=state)
        self.export_button.configure(state=state)
        self.voice_translate_button.configure(state=state)
        self.cancel_button.configure(state="normal" if value else "disabled")
        self.voice_cancel_button.configure(state="normal" if value else "disabled")
        if not value:
            self.progress_var.set(0)

    def _update_progress(self, value: float, message: str) -> None:
        self.progress_var.set(max(0, min(100, value * 100)))
        self.status_var.set(message)

    def _refresh_subtitle_tree(self) -> None:
        self.subtitle_tree.delete(*self.subtitle_tree.get_children())
        for index, segment in enumerate(self.project.subtitles):
            self.subtitle_tree.insert("", "end", iid=str(index), values=(self._short_time(segment.start), self._short_time(segment.end), segment.text))

    @staticmethod
    def _short_time(seconds: float) -> str:
        value = format_srt_time(seconds)
        return value[3:8] if seconds < 3600 else value[:8]

    def _select_segment(self, _event: tk.Event | None = None) -> None:
        selection = self.subtitle_tree.selection()
        if not selection:
            return
        index = int(selection[0])
        if 0 <= index < len(self.project.subtitles):
            self.current_time = self.project.subtitles[index].start
            self.seek_var.set(self.current_time)
            self.request_preview(self.current_time)

    def edit_segment(self) -> None:
        selection = self.subtitle_tree.selection()
        if not selection:
            messagebox.showinfo(APP_NAME, "একটি subtitle line নির্বাচন করুন।", parent=self)
            return
        index = int(selection[0])
        segment = self.project.subtitles[index]
        dialog = tk.Toplevel(self)
        dialog.title("Subtitle Edit")
        dialog.configure(bg="#152033")
        dialog.geometry("650x430")
        dialog.transient(self)
        dialog.grab_set()
        body = ttk.Frame(dialog, style="Panel.TFrame", padding=18)
        body.pack(fill="both", expand=True)
        time_row = ttk.Frame(body, style="Panel.TFrame")
        time_row.pack(fill="x")
        start_var = tk.StringVar(value=format_srt_time(segment.start))
        end_var = tk.StringVar(value=format_srt_time(segment.end))
        ttk.Label(time_row, text="শুরু").grid(row=0, column=0, sticky="w")
        ttk.Entry(time_row, textvariable=start_var).grid(row=1, column=0, sticky="ew", padx=(0, 8))
        ttk.Label(time_row, text="শেষ").grid(row=0, column=1, sticky="w")
        ttk.Entry(time_row, textvariable=end_var).grid(row=1, column=1, sticky="ew")
        time_row.columnconfigure(0, weight=1)
        time_row.columnconfigure(1, weight=1)
        ttk.Label(body, text="বাংলা Subtitle").pack(anchor="w", pady=(14, 4))
        primary = tk.Text(body, height=5, wrap="word", bg="#0F1A2C", fg="#FFFFFF", insertbackground="#FFFFFF", relief="flat", font=("Nirmala UI", 12), padx=8, pady=8)
        primary.pack(fill="both", expand=True)
        primary.insert("1.0", segment.text)
        ttk.Label(body, text="দ্বিতীয় ভাষা/অনুবাদ (ঐচ্ছিক)").pack(anchor="w", pady=(12, 4))
        secondary = tk.Text(body, height=3, wrap="word", bg="#0F1A2C", fg="#FFD966", insertbackground="#FFFFFF", relief="flat", font=("Nirmala UI", 11), padx=8, pady=8)
        secondary.pack(fill="both", expand=True)
        secondary.insert("1.0", segment.secondary_text)

        def save() -> None:
            try:
                updated = SubtitleSegment(parse_timecode(start_var.get()), parse_timecode(end_var.get()), primary.get("1.0", "end").strip(), secondary.get("1.0", "end").strip()).normalized()
            except ValueError as exc:
                messagebox.showerror(APP_NAME, str(exc), parent=dialog)
                return
            if not updated.text:
                messagebox.showerror(APP_NAME, "Subtitle লেখা খালি রাখা যাবে না।", parent=dialog)
                return
            self.project.subtitles[index] = updated
            self.project.subtitles.sort(key=lambda item: item.start)
            self._capture_sync_baseline()
            self._refresh_subtitle_tree()
            self._redraw_preview()
            dialog.destroy()

        ttk.Button(body, text="পরিবর্তন Save", style="Accent.TButton", command=save).pack(fill="x", pady=(14, 0))
        primary.focus_set()

    def add_segment(self) -> None:
        end = min(self.project.duration or self.current_time + 3, self.current_time + 3)
        self.project.subtitles.append(SubtitleSegment(self.current_time, max(self.current_time + 0.5, end), "নতুন সাবটাইটেল"))
        self.project.subtitles.sort(key=lambda item: item.start)
        self._capture_sync_baseline()
        self._refresh_subtitle_tree()

    def delete_segment(self) -> None:
        selection = self.subtitle_tree.selection()
        if not selection:
            return
        index = int(selection[0])
        if messagebox.askyesno(APP_NAME, "নির্বাচিত subtitle line মুছবেন?", parent=self):
            del self.project.subtitles[index]
            self._capture_sync_baseline()
            self._refresh_subtitle_tree()
            self._redraw_preview()

    def import_srt(self) -> None:
        path = filedialog.askopenfilename(title="SRT Import", filetypes=[("SRT subtitle", "*.srt")])
        if not path:
            return
        try:
            segments = parse_srt(path)
        except (OSError, ValueError) as exc:
            messagebox.showerror(APP_NAME, f"SRT পড়া যায়নি:\n{exc}", parent=self)
            return
        self.project.subtitles = segments
        self._capture_sync_baseline()
        self._refresh_subtitle_tree()
        self.status_var.set(f"{len(segments)}টি subtitle line Import হয়েছে।")
        self._redraw_preview()

    def export_srt(self) -> None:
        if not self.project.subtitles:
            messagebox.showinfo(APP_NAME, "কোনো subtitle নেই।", parent=self)
            return
        default = "বাংলা_সাবটাইটেল.srt"
        if self.project.video_path:
            default = Path(self.project.video_path).stem + "_বাংলা.srt"
        path = filedialog.asksaveasfilename(title="SRT Save", defaultextension=".srt", initialfile=default, filetypes=[("SRT subtitle", "*.srt")])
        if path:
            write_srt(path, self.project.subtitles)
            self.status_var.set("SRT file Save হয়েছে।")

    def _sync_style(self) -> None:
        if not hasattr(self, "preview_canvas"):
            return
        style = self.project.subtitle_style
        style.font_name = self.font_var.get()
        style.font_size = round(self.font_size_var.get())
        style.outline = round(self.outline_var.get())
        style.shadow = round(self.shadow_var.get())
        style.bold = self.bold_var.get()
        style.background = self.background_var.get()
        style.position = {"উপরে": "top", "মাঝখানে": "middle", "নিচে": "bottom"}.get(self.position_var.get(), "bottom")
        style.margin_v = round(self.margin_var.get())
        style.max_chars = round(self.max_chars_var.get())
        style.show_secondary = self.show_secondary_var.get()
        self._redraw_preview()

    def _choose_color(self, target: str) -> None:
        style = self.project.subtitle_style
        attr = {
            "primary": "primary_color",
            "secondary": "secondary_color",
            "outline": "outline_color",
            "background": "background_color",
        }[target]
        selected = colorchooser.askcolor(getattr(style, attr), parent=self)[1]
        if selected:
            setattr(style, attr, selected.upper())
            self._redraw_preview()

    def choose_logo(self) -> None:
        path = filedialog.askopenfilename(title="Logo নির্বাচন করুন", filetypes=[("Image", "*.png *.jpg *.jpeg *.webp *.bmp"), ("সব ফাইল", "*.*")])
        if not path:
            return
        try:
            Image.open(path).verify()
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"লোগো পড়া যায়নি:\n{exc}", parent=self)
            return
        self.project.logo.path = path
        self.project.logo.enabled = True
        self.logo_name_label.configure(text=Path(path).name)
        self._sync_logo()

    def remove_logo(self) -> None:
        self.project.logo.path = ""
        self.project.logo.enabled = False
        self.logo_name_label.configure(text="কোনো লোগো নেই")
        self._redraw_preview()

    def _sync_logo(self) -> None:
        if not hasattr(self, "preview_canvas"):
            return
        self.project.logo.scale_percent = self.logo_scale_var.get()
        self.project.logo.opacity = self.logo_opacity_var.get()
        self._redraw_preview()

    def _set_logo_position(self, x: float, y: float) -> None:
        self.project.logo.x_percent = x
        self.project.logo.y_percent = y
        self._redraw_preview()

    def _apply_logo_times(self) -> None:
        try:
            self.project.logo.start = parse_timecode(self.logo_start_var.get())
            end_text = self.logo_end_var.get().strip()
            self.project.logo.end = -1.0 if end_text in {"", "ভিডিওর শেষ পর্যন্ত", "শেষ পর্যন্ত"} else parse_timecode(end_text)
        except ValueError as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return
        if self.project.logo.end >= 0 and self.project.logo.end <= self.project.logo.start:
            messagebox.showerror(APP_NAME, "লোগোর শেষ সময় শুরুর সময়ের পরে হতে হবে।", parent=self)
            return
        self.status_var.set("Logo timing Apply হয়েছে।")
        self._redraw_preview()

    def apply_preset(self, name: str) -> None:
        values = {
            "Natural": (0.0, 1.0, 1.0, 0.0, 0.0),
            "Warm": (0.02, 1.06, 1.08, 18.0, 2.0),
            "Cool": (0.0, 1.04, 1.0, -16.0, 0.0),
            "Cinematic": (-0.03, 1.18, 0.88, 7.0, -4.0),
            "Vivid": (0.02, 1.10, 1.32, 4.0, 0.0),
            "B&W": (0.0, 1.12, 0.0, 0.0, 0.0),
        }[name]
        self.preset_var.set(name)
        self.brightness_var.set(values[0])
        self.contrast_var.set(values[1])
        self.saturation_var.set(values[2])
        self.temperature_var.set(values[3])
        self.tint_var.set(values[4])
        self._sync_color()

    def _sync_color(self) -> None:
        if not hasattr(self, "preview_canvas"):
            return
        self.project.color = ColorSettings(
            preset=self.preset_var.get(),
            brightness=self.brightness_var.get(),
            contrast=self.contrast_var.get(),
            saturation=self.saturation_var.get(),
            temperature=self.temperature_var.get(),
            tint=self.tint_var.get(),
        )
        self._redraw_preview()

    def choose_output(self) -> None:
        initial = Path(self.output_var.get()).name if self.output_var.get() else "বাংলা_সাবটাইটেল_ভিডিও.mp4"
        path = filedialog.asksaveasfilename(title="Final video Save", defaultextension=".mp4", initialfile=initial, filetypes=[("MP4 Video", "*.mp4")])
        if path:
            self.output_var.set(path)

    def choose_voice_output(self) -> None:
        if self.voice_output_var.get().strip():
            initial = Path(self.voice_output_var.get()).name
        elif self.project.video_path:
            target = VOICE_LANGUAGES.get(self.voice_target_var.get(), "en")
            initial = f"{Path(self.project.video_path).stem}_{target}_voice.mp4"
        else:
            initial = "translated_voice_video.mp4"
        path = filedialog.asksaveasfilename(
            title="Translated Voice Video Save",
            defaultextension=".mp4",
            initialfile=initial,
            filetypes=[("MP4 Video", "*.mp4")],
        )
        if path:
            self.voice_output_var.set(path)

    def start_voice_translation(self) -> None:
        if self.busy:
            return
        if not self.project.video_path:
            messagebox.showinfo(APP_NAME, "প্রথমে একটি ভিডিও দিন।", parent=self)
            return
        source = VOICE_LANGUAGES.get(self.voice_source_var.get(), "bn")
        target = VOICE_LANGUAGES.get(self.voice_target_var.get(), "en")
        if source == target:
            messagebox.showerror(
                APP_NAME,
                "মূল voice ও নতুন voice-এর ভাষা আলাদা নির্বাচন করুন।",
                parent=self,
            )
            return
        output = self.voice_output_var.get().strip()
        if not output:
            output = str(
                Path(self.project.video_path).with_name(
                    f"{Path(self.project.video_path).stem}_{target}_voice.mp4"
                )
            )
        if not output.lower().endswith(".mp4"):
            output += ".mp4"
        if Path(output).resolve() == Path(self.project.video_path).resolve():
            messagebox.showerror(
                APP_NAME,
                "মূল ভিডিওর ওপর Voice Translate করা যাবে না। অন্য output নাম দিন।",
                parent=self,
            )
            return
        self.voice_output_var.set(output)
        gender = "Male" if self.voice_gender_var.get() == "পুরুষ কণ্ঠ" else "Female"
        original_volume = max(0.0, min(30.0, self.voice_original_volume_var.get())) / 100.0
        keep_subtitles = self.voice_add_subtitles_var.get()
        source_video = self.project.video_path
        source_duration = self.project.duration
        self._set_busy(True)
        self.busy_cancel.clear()

        def progress(value: float, message: str) -> None:
            self.after(0, lambda: self._update_progress(value, message))

        def worker() -> None:
            try:
                segments = create_voice_translated_video(
                    video_path=source_video,
                    duration=source_duration,
                    source_language=source,
                    target_language=target,
                    gender=gender,
                    output_path=output,
                    original_volume=original_volume,
                    progress=progress,
                    cancel_event=self.busy_cancel,
                )
                self.after(
                    0,
                    lambda: self._finish_voice_translation(
                        output,
                        segments if keep_subtitles else [],
                        target,
                        None,
                    ),
                )
            except Exception as exc:
                self.after(
                    0,
                    lambda error=exc: self._finish_voice_translation(
                        output, [], target, error
                    ),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _finish_voice_translation(
        self,
        output: str,
        segments: list[SubtitleSegment],
        target_language: str,
        error: Exception | None,
    ) -> None:
        self._set_busy(False)
        if error:
            self.status_var.set(str(error))
            messagebox.showerror("Voice Translate হয়নি", str(error), parent=self)
            return
        try:
            info = probe_video(output)
        except MediaError as exc:
            self.status_var.set(str(exc))
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return
        self.stop_playback()
        self.project.video_path = output
        self.project.duration = float(info["duration"])
        self.project.width = int(info["width"])
        self.project.height = int(info["height"])
        self.project.fps = float(info["fps"])
        self.project.subtitles = segments
        self.project.output_path = self.project.default_output_path()
        self.output_var.set(self.project.output_path)
        self.current_time = 0.0
        self.seek_var.set(0.0)
        self.seek_scale.configure(to=max(0.1, self.project.duration))
        self.video_name_var.set(
            f"{Path(output).name}  •  {self.project.width}×{self.project.height}"
        )
        self._capture_sync_baseline()
        self._refresh_subtitle_tree()
        self._update_time_label()
        self.request_preview(0.0)
        self.progress_var.set(100)
        language_name = next(
            (name for name, code in VOICE_LANGUAGES.items() if code == target_language),
            target_language,
        )
        self.status_var.set(f"{language_name} translated voice video তৈরি হয়েছে।")
        messagebox.showinfo(
            APP_NAME,
            "Voice Translate সম্পন্ন হয়েছে।\n\n"
            "Translated video এখন Preview-তে আছে। Subtitle রাখা থাকলে Style ঠিক করে Export করুন।",
            parent=self,
        )

    def start_export(self) -> None:
        if self.busy:
            return
        if not self.project.video_path:
            messagebox.showinfo(APP_NAME, "প্রথমে ভিডিও দিন।", parent=self)
            return
        output = self.output_var.get().strip() or self.project.default_output_path()
        if not output.lower().endswith(".mp4"):
            output += ".mp4"
        self.output_var.set(output)
        if Path(output).resolve() == Path(self.project.video_path).resolve():
            messagebox.showerror(APP_NAME, "মূল ভিডিওর ওপর Export করা যাবে না। অন্য নাম দিন।", parent=self)
            return
        self._apply_logo_times()
        self._sync_style()
        self._sync_color()
        self._set_busy(True)
        self.busy_cancel.clear()

        def progress(value: float, message: str) -> None:
            self.after(0, lambda: self._update_progress(value, message))

        def worker() -> None:
            try:
                export_project(self.project, output, self.quality_var.get(), progress, self.busy_cancel)
                self.after(0, lambda: self._finish_export(output, None))
            except Exception as exc:
                self.after(0, lambda error=exc: self._finish_export(output, error))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_export(self, output: str, error: Exception | None) -> None:
        self._set_busy(False)
        if error:
            self.status_var.set(str(error))
            messagebox.showerror("Export হয়নি", str(error), parent=self)
            return
        self.progress_var.set(100)
        self.status_var.set("ভিডিও Export সম্পন্ন হয়েছে।")
        if messagebox.askyesno("Export সম্পন্ন", f"ভিডিও তৈরি হয়েছে:\n{output}\n\nFolder খুলবেন?", parent=self):
            self._open_folder(output)

    @staticmethod
    def _open_folder(path: str) -> None:
        if os.name == "nt":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        elif os.name == "posix":
            subprocess.Popen(["xdg-open", str(Path(path).parent)])

    def save_project(self) -> None:
        if not self.project_path:
            initial = (Path(self.project.video_path).stem if self.project.video_path else "subtitle_project") + ".bssproject"
            path = filedialog.asksaveasfilename(title="Project Save", defaultextension=".bssproject", initialfile=initial, filetypes=[("Bangla Subtitle Project", "*.bssproject")])
            if not path:
                return
            self.project_path = path
        self._sync_style()
        self._sync_logo()
        self._sync_color()
        self.project.output_path = self.output_var.get()
        try:
            Path(self.project_path).write_text(json.dumps(self.project.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"Project Save হয়নি:\n{exc}", parent=self)
            return
        self.status_var.set("Project Save হয়েছে।")

    def open_project(self) -> None:
        path = filedialog.askopenfilename(title="Project খুলুন", filetypes=[("Bangla Subtitle Project", "*.bssproject"), ("JSON", "*.json")])
        if not path:
            return
        try:
            project = Project.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            messagebox.showerror(APP_NAME, f"Project খোলা যায়নি:\n{exc}", parent=self)
            return
        self.stop_playback()
        self.project = project
        self.project_path = path
        self._load_project_into_ui()
        if self.project.video_path and Path(self.project.video_path).is_file():
            self.seek_scale.configure(to=max(0.1, self.project.duration))
            self.video_name_var.set(f"{Path(self.project.video_path).name}  •  {self.project.width}×{self.project.height}")
            self.request_preview(0)
        else:
            self._draw_placeholder()
            messagebox.showwarning(APP_NAME, "Project খুলেছে, কিন্তু মূল ভিডিওটি আগের জায়গায় পাওয়া যায়নি। ভিডিওটি আবার নির্বাচন করুন।", parent=self)
        self.status_var.set("Project খোলা হয়েছে।")

    def _load_project_into_ui(self) -> None:
        style = self.project.subtitle_style
        self.font_var.set(style.font_name)
        self.font_size_var.set(style.font_size)
        self.outline_var.set(style.outline)
        self.shadow_var.set(style.shadow)
        self.bold_var.set(style.bold)
        self.background_var.set(style.background)
        self.position_var.set({"top": "উপরে", "middle": "মাঝখানে", "bottom": "নিচে"}.get(style.position, "নিচে"))
        self.margin_var.set(style.margin_v)
        self.max_chars_var.set(style.max_chars)
        self.show_secondary_var.set(style.show_secondary)
        logo = self.project.logo
        self.logo_scale_var.set(logo.scale_percent)
        self.logo_opacity_var.set(logo.opacity)
        self.logo_start_var.set(format_srt_time(logo.start))
        self.logo_end_var.set("ভিডিওর শেষ পর্যন্ত" if logo.end < 0 else format_srt_time(logo.end))
        self.logo_name_label.configure(text=Path(logo.path).name if logo.path else "কোনো লোগো নেই")
        color = self.project.color
        self.preset_var.set(color.preset)
        self.brightness_var.set(color.brightness)
        self.contrast_var.set(color.contrast)
        self.saturation_var.set(color.saturation)
        self.temperature_var.set(color.temperature)
        self.tint_var.set(color.tint)
        self.output_var.set(self.project.output_path or self.project.default_output_path())
        self._capture_sync_baseline()
        self._refresh_subtitle_tree()

    def _update_time_label(self) -> None:
        self.time_var.set(f"{format_srt_time(self.current_time)[:8]} / {format_srt_time(self.project.duration)[:8]}")

    def _on_close(self) -> None:
        if self.busy and not messagebox.askyesno(APP_NAME, "কাজ চলছে। বন্ধ করলে বর্তমান কাজ বাতিল হবে। বন্ধ করবেন?", parent=self):
            return
        self.busy_cancel.set()
        self.stop_playback()
        self.destroy()


def main() -> None:
    app = BanglaSubtitleStudio()
    app.mainloop()


if __name__ == "__main__":
    main()
