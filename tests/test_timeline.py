from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from bangla_subtitle_studio.media import probe_media, probe_video
from bangla_subtitle_studio.models import Project, TimelineMedia
from bangla_subtitle_studio.timeline_exporter import (
    build_timeline_export_command,
    export_timeline_project,
)


class TimelineModelTests(unittest.TestCase):
    def _video(self, name: str = "one.mp4", duration: float = 8.0) -> TimelineMedia:
        return TimelineMedia(
            path=name,
            name=name,
            kind="video",
            duration=duration,
            width=1280,
            height=720,
            fps=25,
            has_video=True,
            has_audio=True,
        )

    def test_video_clip_creates_linked_video_and_audio_layers(self) -> None:
        project = Project()
        media = project.timeline.add_media(self._video())
        created = project.timeline.add_clip(media.id)
        self.assertEqual(len(created), 2)
        tracks = [project.timeline.track_by_id(clip.track_id) for clip in created]
        self.assertEqual({track.kind for track in tracks if track}, {"video", "audio"})
        self.assertEqual(created[0].group_id, created[1].group_id)

    def test_sequential_video_and_new_layer(self) -> None:
        project = Project()
        first = project.timeline.add_media(self._video("one.mp4", 4))
        second = project.timeline.add_media(self._video("two.mp4", 3))
        first_clip = project.timeline.add_clip(first.id)[0]
        second_clip = project.timeline.add_clip(second.id)[0]
        overlay_clip = project.timeline.add_clip(second.id, start=1, new_layer=True)[0]
        self.assertAlmostEqual(first_clip.start, 0)
        self.assertAlmostEqual(second_clip.start, 4)
        self.assertAlmostEqual(overlay_clip.start, 1)
        self.assertNotEqual(first_clip.track_id, overlay_clip.track_id)

    def test_drag_split_and_ripple_delete_keep_linked_audio_in_sync(self) -> None:
        project = Project()
        media = project.timeline.add_media(self._video(duration=10))
        video_clip, audio_clip = project.timeline.add_clip(media.id)
        project.timeline.move_group(video_clip.id, 2.0)
        self.assertAlmostEqual(audio_clip.start, 2.0)
        right_items = project.timeline.split_group(video_clip.id, 6.0)
        self.assertEqual(len(right_items), 2)
        self.assertTrue(all(item.start == 6.0 for item in right_items))
        left_ids = {video_clip.id, audio_clip.id}
        project.timeline.delete_group(video_clip.id, ripple=True)
        self.assertFalse(any(item.id in left_ids for item in project.timeline.clips))
        self.assertTrue(all(item.start == 2.0 for item in project.timeline.clips))

    def test_project_json_roundtrip_keeps_timeline(self) -> None:
        project = Project()
        media = project.timeline.add_media(self._video())
        project.timeline.add_clip(media.id)
        loaded = Project.from_dict(json.loads(json.dumps(project.to_dict())))
        self.assertEqual(len(loaded.timeline.media), 1)
        self.assertEqual(len(loaded.timeline.clips), 2)
        self.assertAlmostEqual(loaded.timeline.duration(), 8.0)

    def test_removing_video_layer_removes_its_linked_audio_clip(self) -> None:
        project = Project()
        media = project.timeline.add_media(self._video())
        video_clip, audio_clip = project.timeline.add_clip(media.id)
        video_track = project.timeline.track_by_id(video_clip.track_id)
        assert video_track
        project.timeline.add_track("video")
        project.timeline.remove_track(video_track.id)
        remaining_ids = {clip.id for clip in project.timeline.clips}
        self.assertNotIn(video_clip.id, remaining_ids)
        self.assertNotIn(audio_clip.id, remaining_ids)

    def test_timeline_ui_exposes_all_requested_editor_controls(self) -> None:
        source = (
            Path(__file__).parents[1]
            / "bangla_subtitle_studio"
            / "timeline_ui.py"
        ).read_text(encoding="utf-8")
        for label in (
            "+ Video",
            "+ Audio",
            "+ Image",
            "Add Sequential",
            "Add New Layer",
            "✂ Split",
            "Ripple Delete",
            "+ Video Layer",
            "+ Audio Layer",
            "🔒 Lock",
            "👁 Hide",
            "🔊 Mute",
            "Fade In",
            "Fade Out",
        ):
            self.assertIn(label, source)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is required")
class TimelineExportIntegrationTests(unittest.TestCase):
    def test_real_multivideo_multiaudio_timeline_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video_one = root / "one.mp4"
            video_two = root / "two.mp4"
            music = root / "music.wav"
            output = root / "timeline.mp4"
            ffmpeg = shutil.which("ffmpeg")
            assert ffmpeg
            for path, color, frequency in (
                (video_one, "red", 440),
                (video_two, "blue", 660),
            ):
                subprocess.run(
                    [
                        ffmpeg,
                        "-y",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-f",
                        "lavfi",
                        "-i",
                        f"color=c={color}:s=640x360:r=25:d=1.2",
                        "-f",
                        "lavfi",
                        "-i",
                        f"sine=frequency={frequency}:duration=1.2",
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-c:a",
                        "aac",
                        "-shortest",
                        str(path),
                    ],
                    check=True,
                )
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=220:duration=2.4",
                    str(music),
                ],
                check=True,
            )
            project = Project(width=640, height=360, fps=25)
            project.timeline.width = 640
            project.timeline.height = 360
            for path in (video_one, video_two):
                info = probe_media(str(path))
                media = project.timeline.add_media(
                    TimelineMedia(
                        path=str(path),
                        name=path.name,
                        kind="video",
                        duration=float(info["duration"]),
                        width=int(info["width"]),
                        height=int(info["height"]),
                        fps=float(info["fps"]),
                        has_video=True,
                        has_audio=True,
                    )
                )
                project.timeline.add_clip(media.id)
            music_info = probe_media(str(music))
            music_media = project.timeline.add_media(
                TimelineMedia(
                    path=str(music),
                    name=music.name,
                    kind="audio",
                    duration=float(music_info["duration"]),
                    has_video=False,
                    has_audio=True,
                )
            )
            music_track = project.timeline.add_track("audio")
            music_clip = project.timeline.add_clip(
                music_media.id,
                music_track.id,
                start=0.0,
                add_linked_audio=False,
            )[0]
            music_clip.volume = 0.25
            music_clip.fade_in = 0.2
            music_clip.fade_out = 0.2

            command = build_timeline_export_command(project, str(output), None)
            graph = command[command.index("-filter_complex") + 1]
            self.assertIn("overlay=", graph)
            self.assertIn("amix=inputs=3", graph)
            self.assertIn("afade=t=in", graph)
            export_timeline_project(project, str(output))
            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size, 10_000)
            info = probe_video(str(output))
            self.assertAlmostEqual(float(info["duration"]), project.timeline.duration(), delta=0.25)
            output_media = probe_media(str(output))
            self.assertTrue(output_media["has_audio"])


if __name__ == "__main__":
    unittest.main()
