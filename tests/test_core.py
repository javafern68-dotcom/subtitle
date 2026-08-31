from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from bangla_subtitle_studio.exporter import build_export_command, build_filter_graph
from bangla_subtitle_studio.models import ColorSettings, LogoSettings, Project, SubtitleSegment, SubtitleStyle
from bangla_subtitle_studio.subtitles import (
    format_srt_time,
    parse_srt,
    parse_srt_text,
    parse_timecode,
    merge_short_segments,
    split_for_readability,
    write_ass,
    write_srt,
)
from bangla_subtitle_studio.transcription import (
    OFFLINE_MODEL_NAME,
    VAD_MODEL_NAME,
    _WHISPER_PROGRESS_RE,
    build_whisper_command,
    transcribe_audio_file,
)
from bangla_subtitle_studio.translation import (
    _preserve_greeting,
    _select_semantic_candidate,
    _format_avro_text,
    _title_case_latin_words,
    shift_segments,
    shift_segments_earlier,
    translate_segments,
)


class SubtitleTests(unittest.TestCase):
    def test_timecode_roundtrip(self) -> None:
        self.assertEqual(format_srt_time(3723.456), "01:02:03,456")
        self.assertAlmostEqual(parse_timecode("01:02:03,456"), 3723.456, places=3)

    def test_srt_roundtrip_unicode(self) -> None:
        items = [
            SubtitleSegment(0.25, 2.75, "এটি বাংলা পরীক্ষা"),
            SubtitleSegment(3.0, 5.5, "দ্বিতীয় লাইন"),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "বাংলা.srt"
            write_srt(path, items)
            loaded = parse_srt(path)
        self.assertEqual([item.text for item in loaded], [item.text for item in items])
        self.assertAlmostEqual(loaded[0].start, 0.25)

    def test_whisper_srt_without_blank_lines_is_recovered(self) -> None:
        text = (
            "1\n00:00:00.000 --> 00:00:02.250\nবাংলা প্রথম লাইন\n"
            "2\n0:02.25 --> 0:04.5\nবাংলা দ্বিতীয় লাইন\n"
        )
        loaded = parse_srt_text(text)
        self.assertEqual([item.text for item in loaded], ["বাংলা প্রথম লাইন", "বাংলা দ্বিতীয় লাইন"])
        self.assertAlmostEqual(loaded[1].start, 2.25)
        self.assertAlmostEqual(loaded[1].end, 4.5)

    def test_one_damaged_cue_does_not_discard_valid_cues(self) -> None:
        text = (
            "1\n00:00:00,000 --> 00:00:01,000\nশুরু\n\n"
            "2\nbad time --> 00:00:02,000\nএই অংশ বাদ যাবে\n\n"
            "3\n00:00:02,000 --> 00:00:03,000\nশেষ\n"
        )
        loaded = parse_srt_text(text)
        self.assertEqual([item.text for item in loaded], ["শুরু", "শেষ"])

    def test_utf16_srt_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "utf16.srt"
            path.write_bytes("1\n00:00:00,000 --> 00:00:01,000\nবাংলা\n".encode("utf-16"))
            loaded = parse_srt(path)
        self.assertEqual(loaded[0].text, "বাংলা")

    def test_ass_contains_bangla_and_secondary_color(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "বাংলা.ass"
            write_ass(
                path,
                [SubtitleSegment(0, 2, "বাংলা", "English")],
                SubtitleStyle(secondary_color="#FFD966"),
            )
            text = path.read_text(encoding="utf-8-sig")
        self.assertIn("বাংলা", text)
        self.assertIn(r"\c&H66D9FF&", text)

    def test_long_segments_are_split(self) -> None:
        source = [SubtitleSegment(0, 12, "এক দুই তিন চার পাঁচ ছয় সাত আট নয় দশ এগারো বারো তেরো চৌদ্দ")]
        result = split_for_readability(source, max_words=6, max_duration=5)
        self.assertGreaterEqual(len(result), 3)
        self.assertAlmostEqual(result[0].start, 0)
        self.assertAlmostEqual(result[-1].end, 12)

    def test_short_asr_fragments_are_joined_as_one_sentence(self) -> None:
        source = [
            SubtitleSegment(0.0, 2.4, "বিসমিল্লাহির রহমানের রাহিম আপনারা"),
            SubtitleSegment(2.45, 3.7, "কেমন আছেন"),
        ]
        result = merge_short_segments(source)
        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0].text,
            "বিসমিল্লাহির রহমানের রাহিম, আপনারা কেমন আছেন",
        )
        self.assertAlmostEqual(result[0].start, 0.0)
        self.assertAlmostEqual(result[0].end, 3.7)


class ModelAndExportTests(unittest.TestCase):
    def test_project_json_shape(self) -> None:
        project = Project(video_path="video.mp4", subtitles=[SubtitleSegment(0, 1, "বাংলা")])
        encoded = json.dumps(project.to_dict(), ensure_ascii=False)
        loaded = Project.from_dict(json.loads(encoded))
        self.assertEqual(loaded.subtitles[0].text, "বাংলা")

    def test_filter_graph_has_color_logo_and_subtitles(self) -> None:
        project = Project(
            video_path="video.mp4",
            duration=10,
            width=1920,
            height=1080,
            subtitles=[SubtitleSegment(0, 1, "বাংলা")],
            logo=LogoSettings(path="logo.png", enabled=True, scale_percent=20),
            color=ColorSettings(brightness=0.1, contrast=1.2, saturation=1.3, temperature=10),
        )
        graph, label = build_filter_graph(project, "/tmp/sub.ass")
        self.assertIn("eq=brightness=0.1000:contrast=1.2000:saturation=1.3000", graph)
        self.assertIn("scale=384:-1", graph)
        self.assertIn("overlay=", graph)
        self.assertIn("subtitles=", graph)
        self.assertEqual(label, "vout")

    def test_command_maps_optional_audio(self) -> None:
        project = Project(video_path="video.mp4", duration=5)
        command = build_export_command(project, "out.mp4", None)
        self.assertIn("0:a?", command)
        self.assertIn("libx264", command)


class OfflineTranscriptionTests(unittest.TestCase):
    def test_whisper_command_uses_local_model_and_srt(self) -> None:
        command = build_whisper_command(
            "whisper-cli.exe",
            "ggml-bengali-medium-q4_0.bin",
            "audio.wav",
            "subtitle",
            "en",
            "বাংলা বানান",
            threads=4,
            vad_model_path="ggml-silero-v6.2.0.bin",
        )
        self.assertEqual(command[0], "whisper-cli.exe")
        self.assertEqual(OFFLINE_MODEL_NAME, "ggml-bengali-medium-q4_0.bin")
        self.assertEqual(VAD_MODEL_NAME, "ggml-silero-v6.2.0.bin")
        self.assertIn("ggml-bengali-medium-q4_0.bin", command)
        self.assertIn("-osrt", command)
        self.assertIn("-pp", command)
        self.assertEqual(command[command.index("-l") + 1], "bn")
        self.assertNotIn("en", command)
        self.assertNotIn("-tr", command)
        self.assertIn("--prompt", command)
        self.assertIn("--vad", command)
        self.assertIn("ggml-silero-v6.2.0.bin", command)
        self.assertEqual(command[command.index("-ml") + 1], "84")
        self.assertNotIn("--carry-initial-prompt", command)
        self.assertNotIn("api.openai.com", " ".join(command))

    def test_live_progress_output_is_detected(self) -> None:
        output = b"whisper_print_progress_callback: progress =  42%\r"
        self.assertEqual(_WHISPER_PROGRESS_RE.findall(output), [b"42"])

    @mock.patch("bangla_subtitle_studio.transcription.subprocess.Popen")
    @mock.patch("bangla_subtitle_studio.transcription.offline_components")
    def test_offline_srt_result_is_parsed(
        self, mocked_components: mock.Mock, mocked_popen: mock.Mock
    ) -> None:
        mocked_components.return_value = ("whisper-cli.exe", "model.bin", "vad.bin")
        process = mock.Mock()
        process.poll.return_value = 0
        process.returncode = 0
        mocked_popen.return_value = process
        with tempfile.TemporaryDirectory() as temp_dir:
            prefix = str(Path(temp_dir) / "result")
            Path(prefix + ".srt").write_text(
                "1\n00:00:00,000 --> 00:00:02,000\nবাংলা পরীক্ষা\n",
                encoding="utf-8",
            )
            result = transcribe_audio_file("audio.wav", output_prefix=prefix)
        self.assertEqual(result[0].text, "বাংলা পরীক্ষা")
        self.assertAlmostEqual(result[0].end, 2.0)


class TranslationAndSyncTests(unittest.TestCase):
    def test_semantic_reranking_prefers_meaning_preserving_translation(self) -> None:
        chosen = _select_semantic_candidate(
            "সবাই কেমন আছেন",
            ["Everyone is here", "How is everyone"],
            ["সবাই এখানে আছে", "সবাই কেমন আছেন"],
        )
        self.assertEqual(chosen, "How is everyone")

    def test_islamic_greeting_is_not_lost_in_translation(self) -> None:
        result = _preserve_greeting(
            "আসসালামু আলাইকুম। সবাই কেমন আছেন?",
            "How is everyone?",
            "en",
        )
        self.assertEqual(result, "Assalamu Alaikum। How is everyone?")

    def test_subtitle_timing_is_shifted_earlier(self) -> None:
        result = shift_segments_earlier(
            [SubtitleSegment(1.0, 3.0, "বাংলা"), SubtitleSegment(0.1, 0.5, "শুরু")],
            0.35,
        )
        self.assertAlmostEqual(result[0].start, 0.65)
        self.assertAlmostEqual(result[0].end, 2.65)
        self.assertEqual(result[1].start, 0.0)
        self.assertAlmostEqual(result[1].end, 0.15)

    def test_global_sync_moves_every_language_together(self) -> None:
        source = [
            SubtitleSegment(1.0, 2.0, "বাংলা"),
            SubtitleSegment(3.0, 4.0, "How Are You", "কেমন আছেন"),
        ]
        result = shift_segments(source, 0.25)
        self.assertAlmostEqual(result[0].start, 1.25)
        self.assertAlmostEqual(result[1].end, 4.25)
        self.assertEqual(result[1].secondary_text, "কেমন আছেন")

    def test_bangla_output_is_preserved(self) -> None:
        source = [SubtitleSegment(0, 2, "বাংলা পরীক্ষা", "old")]
        result = translate_segments(source, "bn")
        self.assertEqual(result[0].text, "বাংলা পরীক্ষা")
        self.assertEqual(result[0].secondary_text, "")

    def test_avro_output_is_title_case_without_bangla_second_line(self) -> None:
        fake_avro = types.SimpleNamespace(reverse_iter=lambda _items: ["ami banglay gan gai."])
        with mock.patch.dict(sys.modules, {"avro": fake_avro}):
            result = translate_segments(
                [SubtitleSegment(0, 2, "আমি বাংলায় গান গাই।")], "avro"
            )
        self.assertEqual(result[0].text, "Ami Banglay Gan Gai.")
        self.assertEqual(result[0].secondary_text, "")

    def test_every_english_word_starts_with_a_capital(self) -> None:
        self.assertEqual(
            _title_case_latin_words("bismillahir rahmanir rahim, how are you?"),
            "Bismillahir Rahmanir Rahim, How Are You?",
        )

    def test_requested_bismillah_avro_spelling_is_exact(self) -> None:
        self.assertEqual(
            _format_avro_text(
                "বিসমিল্লাহির রহমানের রাহিম",
                "bismillahir rhamaner rahim",
            ),
            "Bismillahir Rahmanir Rahim",
        )


class UIRegressionTests(unittest.TestCase):
    def test_color_presets_grid_isolated_from_packed_card(self) -> None:
        source = (Path(__file__).parents[1] / "bangla_subtitle_studio" / "app.py").read_text(encoding="utf-8")
        self.assertIn("ttk.Button(preset_grid", source)
        self.assertNotIn("ttk.Button(presets, text=name", source)

    def test_offline_ui_has_no_api_key_controls(self) -> None:
        source = (Path(__file__).parents[1] / "bangla_subtitle_studio" / "app.py").read_text(encoding="utf-8")
        self.assertIn("সম্পূর্ণ Offline", source)
        self.assertNotIn("api_key_var", source)

    def test_offline_ui_forces_bangla_script_mode(self) -> None:
        source = (Path(__file__).parents[1] / "bangla_subtitle_studio" / "app.py").read_text(encoding="utf-8")
        self.assertIn('"বাংলা (বাংলা অক্ষর)": "bn"', source)
        self.assertIn('"বাংলা (Avro / Banglish)": "avro"', source)
        self.assertIn('"हिन्दी (Hindi)": "hi"', source)
        self.assertIn('"العربية (Arabic)": "ar"', source)
        self.assertIn('                    "bn",', source)
        self.assertNotIn('"Auto Detect": "auto"', source)
        self.assertIn('self.prompt_var = tk.StringVar(value="")', source)

    def test_ui_has_language_independent_global_sync_controls(self) -> None:
        source = (Path(__file__).parents[1] / "bangla_subtitle_studio" / "app.py").read_text(encoding="utf-8")
        self.assertIn("সব Subtitle-এর Global Sync", source)
        self.assertIn("self._adjust_global_sync(-1)", source)
        self.assertIn("self._adjust_global_sync(1)", source)
        self.assertIn("command=self._reset_global_sync", source)


if __name__ == "__main__":
    unittest.main()
