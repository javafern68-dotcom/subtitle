from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
import wave
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
    MULTILINGUAL_MODEL_NAME,
    OFFLINE_MODEL_NAME,
    VAD_MODEL_NAME,
    _WHISPER_PROGRESS_RE,
    build_whisper_command,
    transcribe_audio_file,
)
from bangla_subtitle_studio.voice_translate import (
    TEXT_VOICE_OPTIONS,
    VOICE_SAMPLE_RATE,
    _atempo_expression,
    _build_timed_voice_track,
    _online_voice,
    _save_speech,
    _select_voice,
    _signed_control,
    _split_text_voice_chunks,
    create_text_voice,
    create_voice_translated_video,
)
from bangla_subtitle_studio.translation import (
    _google_translate_text,
    _google_translate_texts,
    _ensure_runtime_streams,
    _best_effort_target_candidate,
    _normalize_target_fluency,
    _preserve_greeting,
    _select_semantic_candidate,
    _select_valid_target_candidate,
    _valid_target_script,
    _clean_avro_roman,
    _format_avro_text,
    _title_case_latin_words,
    shift_segments,
    shift_segments_earlier,
    translate_segments,
    translate_voice_segments,
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

    def test_multilingual_voice_command_keeps_selected_source_language(self) -> None:
        command = build_whisper_command(
            "whisper-cli.exe",
            MULTILINGUAL_MODEL_NAME,
            "audio.wav",
            "subtitle",
            "hi",
            vad_model_path="vad.bin",
            force_bengali=False,
        )
        self.assertEqual(command[command.index("-l") + 1], "hi")
        self.assertEqual(MULTILINGUAL_MODEL_NAME, "ggml-large-v3-turbo-q5_0.bin")

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
    def test_windowed_exe_has_safe_utf8_library_log_streams(self) -> None:
        with (
            mock.patch.object(sys, "stdout", None),
            mock.patch.object(sys, "stderr", None),
        ):
            _ensure_runtime_streams()
            self.assertIsNotNone(sys.stdout)
            self.assertIsNotNone(sys.stderr)
            assert sys.stdout is not None
            sys.stdout.write("বাংলা हिंदी English")

    def test_all_requested_voice_directions_require_the_correct_script(self) -> None:
        directions = [
            ("বাংলা কথা", "How Are You", "en"),
            ("English speech", "আপনি কেমন আছেন", "bn"),
            ("বাংলা কথা", "आप कैसे हैं", "hi"),
            ("हिंदी आवाज", "আপনি কেমন আছেন", "bn"),
            ("हिंदी आवाज", "How Are You", "en"),
            ("English speech", "आप कैसे हैं", "hi"),
        ]
        for source, translated, target in directions:
            with self.subTest(target=target, translated=translated):
                self.assertTrue(_valid_target_script(source, translated, target))

    def test_mixed_source_alphabet_is_rejected_before_voice_generation(self) -> None:
        self.assertFalse(
            _valid_target_script(
                "आप कैसे हैं और आज क्या कर रहे हैं",
                "आप कैसे हैं और আজ क्या कर रहे हैं",
                "bn",
            )
        )

    def test_valid_bengali_with_roman_brand_name_is_not_rejected(self) -> None:
        self.assertTrue(
            _valid_target_script(
                "यह OpenAI वीडियो है",
                "এটি OpenAI দিয়ে তৈরি একটি ভিডিও",
                "bn",
            )
        )

    def test_valid_second_candidate_is_used_instead_of_aborting_video(self) -> None:
        selected = _select_valid_target_candidate(
            "आप कैसे हैं?",
            ["आप कैसे हैं?", "আপনি কেমন আছেন?"],
            ["आप कैसे हैं?", "आप कैसे हैं?"],
            "bn",
        )
        self.assertEqual(selected, "আপনি কেমন আছেন?")

    def test_best_effort_keeps_a_difficult_phrase_audible(self) -> None:
        selected = _best_effort_target_candidate(
            "OpenAI वीडियो",
            ["OpenAI", "OpenAI বাংলা ভিডিও"],
            "bn",
        )
        self.assertEqual(selected, "OpenAI বাংলা ভিডিও")

    @mock.patch("bangla_subtitle_studio.translation.urllib.request.urlopen")
    def test_google_translation_response_is_parsed_and_validated(
        self, urlopen: mock.Mock
    ) -> None:
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            [[["How are you?", "আপনি কেমন আছেন?", None, None]]]
        ).encode("utf-8")
        urlopen.return_value = response
        self.assertEqual(
            _google_translate_text("আপনি কেমন আছেন?", "bn", "en"),
            "How are you?",
        )
        self.assertIn("sl=bn", urlopen.call_args.args[0].full_url)
        self.assertIn("tl=en", urlopen.call_args.args[0].full_url)

    @mock.patch("bangla_subtitle_studio.translation._google_translate_text")
    def test_complete_video_sentences_use_one_online_request(
        self, google: mock.Mock
    ) -> None:
        google.return_value = (
            "[[[BSSSEG0000]]] How Are You?\n"
            "[[[BSSSEG0001]]] I Am Fine."
        )
        self.assertEqual(
            _google_translate_texts(
                ["আপনি কেমন আছেন?", "আমি ভালো আছি।"], "bn", "en"
            ),
            ["How Are You?", "I Am Fine."],
        )
        google.assert_called_once()

    @mock.patch("bangla_subtitle_studio.translation.time.sleep")
    @mock.patch("bangla_subtitle_studio.translation._google_translate_texts")
    def test_long_video_uses_small_ordered_translation_batches(
        self, google: mock.Mock, _sleep: mock.Mock
    ) -> None:
        google.side_effect = lambda batch, _source, _target: [
            f"English Phrase {index + 1}" for index, _value in enumerate(batch)
        ]
        source = [
            SubtitleSegment(index, index + 0.8, f"বাংলা বাক্য {index + 1}")
            for index in range(9)
        ]
        result = translate_voice_segments(source, "en", source_language="bn")
        self.assertEqual(len(result), 9)
        self.assertEqual(google.call_count, 2)
        self.assertEqual(len(google.call_args_list[0].args[0]), 8)
        self.assertEqual(len(google.call_args_list[1].args[0]), 1)

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

    def test_literal_hindi_fallback_becomes_natural_spoken_bengali(self) -> None:
        self.assertEqual(
            _normalize_target_fluency(
                "আপনি কিভাবে? আমি ঠিক আছে। আজ খুব ভালো দিন।", "bn"
            ),
            "আপনি কেমন আছেন? আমি ঠিক আছি। আজ খুব ভালো দিন।",
        )

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

    def test_same_non_bengali_source_and_target_is_preserved(self) -> None:
        source = [SubtitleSegment(0, 2, "आप कैसे हैं", "old")]
        result = translate_segments(source, "hi", source_language="hi")
        self.assertEqual(result[0].text, "आप कैसे हैं")
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

    def test_avro_removes_bengali_hasanta_and_dotted_circle_triggers(self) -> None:
        dirty = "Bismillo্Lah Rohanir Rohim Asalamu Alikeumu Rahmatullo্Lahi"
        cleaned = _format_avro_text(
            "বিসমিল্লাহির রহমানির রাহিম আসসালামু আলাইকুম ওয়া রাহমাতুল্লাহি",
            dirty,
        )
        self.assertEqual(
            cleaned,
            "Bismillahir Rahmanir Rahim Assalamu Alaikum Warahmatullahi",
        )
        self.assertTrue(all(ord(character) < 128 for character in cleaned))
        self.assertNotRegex(cleaned, r"[\u0980-\u09FF]")

    def test_generic_avro_cleaner_keeps_only_roman_text(self) -> None:
        self.assertEqual(
            _clean_avro_roman("Ami্ Banglay। Gaan Gai…"),
            "Ami Banglay. Gaan Gai...",
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

    def test_ui_has_multilanguage_voice_translate_tab(self) -> None:
        source = (Path(__file__).parents[1] / "bangla_subtitle_studio" / "app.py").read_text(encoding="utf-8")
        self.assertIn('self.notebook.add(self.voice_tab, text="Voice Translate")', source)
        self.assertIn("মূল voice-এর ভাষা", source)
        self.assertIn("নতুন voice-এর ভাষা", source)
        self.assertIn("create_voice_translated_video", source)

    def test_ui_has_text_to_voice_tab_and_controls(self) -> None:
        source = (Path(__file__).parents[1] / "bangla_subtitle_studio" / "app.py").read_text(encoding="utf-8")
        self.assertIn('self.notebook.add(self.text_voice_tab, text="Text To Voice")', source)
        self.assertIn("Text / Script থেকে Natural Voice", source)
        self.assertIn("Voice ID", source)
        self.assertIn("Speed: Slow (-) ↔ Fast (+) %", source)
        self.assertIn("Pitch: ভারী (-) ↔ চিকন (+) Hz", source)
        self.assertIn("create_text_voice", source)


class VoiceTranslationTests(unittest.TestCase):
    def test_text_voice_has_bengali_and_english_voice_ids(self) -> None:
        self.assertIn(("bn-BD-NabanitaNeural", "নারী কণ্ঠ"), TEXT_VOICE_OPTIONS["bn"])
        self.assertTrue(
            any(voice_id == "en-US-JennyNeural" for voice_id, _label in TEXT_VOICE_OPTIONS["en"])
        )

    def test_text_voice_long_script_is_split_at_readable_boundaries(self) -> None:
        script = " ".join(
            f"Sentence number {index} is clear." for index in range(1, 31)
        )
        chunks = _split_text_voice_chunks(script, max_chars=200)
        self.assertGreaterEqual(len(chunks), 3)
        self.assertTrue(all(len(chunk) <= 200 for chunk in chunks))
        self.assertEqual(" ".join(chunks), script)

    def test_text_voice_signed_edge_controls_are_valid(self) -> None:
        self.assertEqual(_signed_control(25, "%"), "+25%")
        self.assertEqual(_signed_control(-12, "Hz"), "-12Hz")

    @mock.patch("bangla_subtitle_studio.voice_translate._save_text_voice_chunk")
    def test_text_voice_creates_complete_mp3(self, save_chunk: mock.Mock) -> None:
        def write_audio(
            _text: str,
            _language: str,
            _voice_id: str,
            output: str,
            _rate: int,
            _pitch: int,
        ) -> None:
            Path(output).write_bytes(b"ID3" + b"\x01" * 1_000)

        save_chunk.side_effect = write_audio
        with tempfile.TemporaryDirectory() as temp_dir:
            output = str(Path(temp_dir) / "voice.mp3")
            create_text_voice(
                "This is a complete voice test.",
                "en",
                "en-US-JennyNeural",
                output,
                rate_percent=20,
                pitch_hz=-5,
            )
            self.assertGreater(Path(output).stat().st_size, 500)
        save_chunk.assert_called_once()

    def test_preferred_bengali_female_voice_is_selected(self) -> None:
        voices = [
            {"Locale": "bn-BD", "Gender": "Female", "ShortName": "bn-BD-OtherNeural"},
            {"Locale": "bn-BD", "Gender": "Female", "ShortName": "bn-BD-NabanitaNeural"},
        ]
        self.assertEqual(_select_voice(voices, "bn", "Female"), "bn-BD-NabanitaNeural")

    def test_long_voice_speed_uses_safe_atempo_chain(self) -> None:
        self.assertEqual(
            _atempo_expression(4.5),
            "atempo=2.00000,atempo=2.00000,atempo=1.12500",
        )

    @mock.patch("bangla_subtitle_studio.voice_translate._fit_speech_to_cue")
    @mock.patch("bangla_subtitle_studio.voice_translate._save_speech")
    def test_timed_voice_keeps_complete_phrases_and_natural_pauses(
        self, _save: mock.Mock, fit: mock.Mock
    ) -> None:
        def write_half_second(_source: str, output: str, _duration: float) -> float:
            with wave.open(output, "wb") as writer:
                writer.setnchannels(1)
                writer.setsampwidth(2)
                writer.setframerate(VOICE_SAMPLE_RATE)
                writer.writeframes(b"\x01\x00" * (VOICE_SAMPLE_RATE // 2))
            return 0.5

        fit.side_effect = write_half_second
        segments = [
            SubtitleSegment(0.0, 1.0, "প্রথম কথা"),
            SubtitleSegment(2.0, 3.0, "দ্বিতীয় কথা"),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = str(Path(temp_dir) / "track.wav")
            _build_timed_voice_track(
                segments, "bn-BD-NabanitaNeural", 3.0, output, temp_dir
            )
            with wave.open(output, "rb") as reader:
                frames = reader.readframes(reader.getnframes())

        # Both complete half-second phrases are present; the source pause is
        # silence rather than a stretched or clipped translated word.
        first = frames[: VOICE_SAMPLE_RATE]
        pause = frames[VOICE_SAMPLE_RATE : 4 * VOICE_SAMPLE_RATE]
        second = frames[4 * VOICE_SAMPLE_RATE : 5 * VOICE_SAMPLE_RATE]
        self.assertNotEqual(first, b"\x00" * len(first))
        self.assertEqual(pause, b"\x00" * len(pause))
        self.assertNotEqual(second, b"\x00" * len(second))

    def test_google_bengali_voice_is_used_when_microsoft_is_unreachable(self) -> None:
        edge_module = types.ModuleType("edge_tts")

        async def failed_voice_list() -> list[dict[str, object]]:
            raise OSError("Microsoft service blocked")

        edge_module.list_voices = failed_voice_list  # type: ignore[attr-defined]
        gtts_package = types.ModuleType("gtts")
        gtts_package.__path__ = []  # type: ignore[attr-defined]
        gtts_lang = types.ModuleType("gtts.lang")
        gtts_lang.tts_langs = lambda: {"bn": "Bengali"}  # type: ignore[attr-defined]
        with (
            mock.patch.dict(
                sys.modules,
                {"edge_tts": edge_module, "gtts": gtts_package, "gtts.lang": gtts_lang},
            ),
            mock.patch("bangla_subtitle_studio.voice_translate.time.sleep"),
        ):
            self.assertEqual(_online_voice("bn", "Female"), "google:bn")

    def test_google_fallback_writes_real_audio_file(self) -> None:
        gtts_package = types.ModuleType("gtts")

        class FakeGoogleSpeech:
            def __init__(self, text: str, lang: str, slow: bool) -> None:
                self.values = (text, lang, slow)

            def save(self, output_path: str) -> None:
                Path(output_path).write_bytes(b"google voice")

        gtts_package.gTTS = FakeGoogleSpeech  # type: ignore[attr-defined]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "fallback.mp3"
            with mock.patch.dict(sys.modules, {"gtts": gtts_package}):
                _save_speech("আপনি কেমন আছেন", "google:bn", str(output))
            self.assertEqual(output.read_bytes(), b"google voice")

    @mock.patch("bangla_subtitle_studio.voice_translate._mux_dubbed_video")
    @mock.patch("bangla_subtitle_studio.voice_translate._build_timed_voice_track")
    @mock.patch("bangla_subtitle_studio.voice_translate._online_voice", return_value="en-US-JennyNeural")
    @mock.patch("bangla_subtitle_studio.voice_translate.translate_voice_segments")
    @mock.patch("bangla_subtitle_studio.voice_translate.transcribe_video")
    def test_hindi_voice_can_become_english_voice(
        self,
        transcribe: mock.Mock,
        translate: mock.Mock,
        _voice: mock.Mock,
        _track: mock.Mock,
        mux: mock.Mock,
    ) -> None:
        transcribe.return_value = [SubtitleSegment(0, 2, "आप कैसे हैं")]
        translate.return_value = [SubtitleSegment(0, 2, "How Are You")]
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "hindi.mp4"
            video.write_bytes(b"video")
            output = str(Path(temp_dir) / "english.mp4")
            result = create_voice_translated_video(
                str(video), 2.0, "hi", "en", "Female", output
            )
        self.assertEqual(result[0].text, "How Are You")
        self.assertTrue(transcribe.call_args.kwargs["multilingual"])
        self.assertEqual(transcribe.call_args.args[3], "")
        self.assertEqual(transcribe.call_args.kwargs["segment_max_words"], 10)
        self.assertEqual(transcribe.call_args.kwargs["segment_max_duration"], 5.5)
        self.assertEqual(translate.call_args.kwargs["source_language"], "hi")
        self.assertEqual(translate.call_args.args[1], "en")
        mux.assert_called_once()


if __name__ == "__main__":
    unittest.main()
