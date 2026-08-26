from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bangla_subtitle_studio.exporter import build_export_command, build_filter_graph
from bangla_subtitle_studio.models import ColorSettings, LogoSettings, Project, SubtitleSegment, SubtitleStyle
from bangla_subtitle_studio.subtitles import (
    format_srt_time,
    parse_srt,
    parse_timecode,
    split_for_readability,
    write_ass,
    write_srt,
)
from bangla_subtitle_studio.transcription import (
    OFFLINE_MODEL_NAME,
    _WHISPER_PROGRESS_RE,
    build_whisper_command,
    transcribe_audio_file,
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
            "ggml-small-q5_1.bin",
            "audio.wav",
            "subtitle",
            "bn",
            "বাংলা বানান",
            threads=4,
        )
        self.assertEqual(command[0], "whisper-cli.exe")
        self.assertEqual(OFFLINE_MODEL_NAME, "ggml-small-q5_1.bin")
        self.assertIn("ggml-small-q5_1.bin", command)
        self.assertIn("-osrt", command)
        self.assertIn("-pp", command)
        self.assertIn("bn", command)
        self.assertIn("--prompt", command)
        self.assertNotIn("api.openai.com", " ".join(command))

    def test_live_progress_output_is_detected(self) -> None:
        output = b"whisper_print_progress_callback: progress =  42%\r"
        self.assertEqual(_WHISPER_PROGRESS_RE.findall(output), [b"42"])

    @mock.patch("bangla_subtitle_studio.transcription.subprocess.Popen")
    @mock.patch("bangla_subtitle_studio.transcription.offline_components")
    def test_offline_srt_result_is_parsed(
        self, mocked_components: mock.Mock, mocked_popen: mock.Mock
    ) -> None:
        mocked_components.return_value = ("whisper-cli.exe", "model.bin")
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


class UIRegressionTests(unittest.TestCase):
    def test_color_presets_grid_isolated_from_packed_card(self) -> None:
        source = (Path(__file__).parents[1] / "bangla_subtitle_studio" / "app.py").read_text(encoding="utf-8")
        self.assertIn("ttk.Button(preset_grid", source)
        self.assertNotIn("ttk.Button(presets, text=name", source)

    def test_offline_ui_has_no_api_key_controls(self) -> None:
        source = (Path(__file__).parents[1] / "bangla_subtitle_studio" / "app.py").read_text(encoding="utf-8")
        self.assertIn("সম্পূর্ণ Offline", source)
        self.assertNotIn("api_key_var", source)


if __name__ == "__main__":
    unittest.main()
