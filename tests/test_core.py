from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import urllib.error

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
from bangla_subtitle_studio.credentials import load_api_key
from bangla_subtitle_studio.transcription import TranscriptionError, _multipart_body, validate_api_key


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


class TranscriptionRequestTests(unittest.TestCase):
    def test_multipart_contains_fields_and_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "audio.mp3"
            path.write_bytes(b"audio-bytes")
            body, boundary = _multipart_body([("model", "whisper-1")], "file", str(path))
        self.assertIn(b"whisper-1", body)
        self.assertIn(b"audio-bytes", body)
        self.assertIn(boundary.encode(), body)

    @mock.patch("bangla_subtitle_studio.transcription.urllib.request.urlopen")
    def test_invalid_api_key_has_clear_message(self, mocked_urlopen: mock.Mock) -> None:
        mocked_urlopen.side_effect = urllib.error.HTTPError(
            "https://api.openai.com/v1/models", 401, "Unauthorized", {}, None
        )
        with self.assertRaisesRegex(TranscriptionError, "API key সঠিক নয়"):
            validate_api_key("invalid-key")


class CredentialTests(unittest.TestCase):
    def test_non_windows_load_does_not_write_plaintext_file(self) -> None:
        if os.name == "nt":
            self.skipTest("Non-Windows fallback test")
        self.assertEqual(load_api_key(), "")


if __name__ == "__main__":
    unittest.main()
