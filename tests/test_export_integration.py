from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from bangla_subtitle_studio.exporter import export_project
from bangla_subtitle_studio.models import ColorSettings, LogoSettings, Project, SubtitleSegment, SubtitleStyle
from bangla_subtitle_studio.media import probe_video


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is required")
class ExportIntegrationTests(unittest.TestCase):
    def test_real_mp4_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.mp4"
            logo = root / "logo.png"
            output = root / "output.mp4"
            Image.new("RGBA", (120, 60), (255, 80, 60, 220)).save(logo)
            subprocess.run(
                [
                    shutil.which("ffmpeg"), "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25:duration=2",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source),
                ],
                check=True,
            )
            project = Project(
                video_path=str(source), duration=2, width=640, height=360, fps=25,
                subtitles=[SubtitleSegment(0.1, 1.8, "বাংলা সাবটাইটেল")],
                subtitle_style=SubtitleStyle(font_name="DejaVu Sans", font_size=48),
                logo=LogoSettings(path=str(logo), enabled=True, scale_percent=20, opacity=85),
                color=ColorSettings(contrast=1.05, saturation=1.1),
            )
            export_project(project, str(output))
            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size, 10_000)
            info = probe_video(str(output))
            self.assertAlmostEqual(float(info["duration"]), 2, delta=0.25)


if __name__ == "__main__":
    unittest.main()

