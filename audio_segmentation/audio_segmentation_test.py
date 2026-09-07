import os
import unittest
from unittest.mock import patch, mock_open

from core.schemas import ServicePlan, Song
from audio_segmentation.audio_segmentation import (
    clean_filename,
    time_to_ms,
    validate_segments,
    compress_wav_to_mp3,
    slice_audio_ffmpeg_copy,
    generate_daw_locators,
    _format_setlist_for_ai,
    segment_service_audio,
    FFMPEG_PATH
)


class TestAudioSegmentation(unittest.TestCase):

    # ==============================================================================
    # 1. STRING, DATACLASS, AND FILENAME PARSING
    # ==============================================================================
    def test_clean_filename_removes_illegal_chars(self) -> None:
        """Ensures macOS/Windows filesystem illegal characters are stripped."""
        self.assertEqual(clean_filename("Amazing Grace?"), "Amazing Grace")
        self.assertEqual(clean_filename('Song "Title" | Remix/Edit\\*'), "Song Title  RemixEdit")
        self.assertEqual(clean_filename("   Praise <God> : Doxology   "), "Praise God  Doxology")

    def test_format_setlist_for_ai(self) -> None:
        """Ensures the ServicePlan dataclass converts songs into the expected AI prompt string."""
        plan = ServicePlan(
            date="2026-09-06",
            songs=[
                Song(title="Amazing Grace", key="G"),
                Song(title="A Song With No Key")
            ]
        )
        expected = "Amazing Grace (G)\nA Song With No Key"
        self.assertEqual(_format_setlist_for_ai(plan), expected)

    # ==============================================================================
    # 2. TIME CONVERSION LOGIC
    # ==============================================================================
    def test_time_to_ms_valid_formats(self) -> None:
        """Tests standard sub-second timestamp string conversions for 3-part format."""
        self.assertEqual(time_to_ms("00:00:01.000"), 1000)
        self.assertEqual(time_to_ms("00:00:01.500"), 1500)
        # (1 hour * 3600) + (2 min * 60) + 3 sec = 3723 sec -> 3723000 ms + 450 ms
        self.assertEqual(time_to_ms("01:02:03.450"), 3723450) 
        
    def test_time_to_ms_fallback_2_part_formats(self) -> None:
        """Tests that the function can gracefully handle 2-part MM:SS.f if Gemini hallucinates it."""
        self.assertEqual(time_to_ms("05:30.000"), 330000) # 5 min * 60 = 300s + 30s = 330s -> 330000ms
        self.assertEqual(time_to_ms("01:00.500"), 60500) 
        
    def test_time_to_ms_sub_second_padding(self) -> None:
        """Tests that fractional seconds are padded correctly to milliseconds."""
        self.assertEqual(time_to_ms("00:00:05.5"), 5500)   # .5 should be 500ms
        self.assertEqual(time_to_ms("00:00:05.05"), 5050)  # .05 should be 50ms
        self.assertEqual(time_to_ms("00:00:05.500"), 5500) 

    def test_time_to_ms_invalid_format_returns_zero(self) -> None:
        """Ensures malformed timestamps do not crash the pipeline."""
        self.assertEqual(time_to_ms("invalid_time_string"), 0)
        self.assertEqual(time_to_ms("00:00"), 0)

    # ==============================================================================
    # 3. AI OUTPUT VALIDATION (HALLUCINATION PREVENTION)
    # ==============================================================================
    def test_validate_segments_removes_negative_duration(self) -> None:
        """Ensures segments where end_time <= start_time are dropped."""
        segments = [
            {"label": "song", "start_time": "00:01:00.000", "end_time": "00:00:30.000"}, # Invalid
            {"label": "speaking", "start_time": "00:01:30.000", "end_time": "00:02:00.000"} # Valid
        ]
        valid = validate_segments(segments)
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0]["label"], "speaking")

    def test_validate_segments_allows_intentional_overlaps(self) -> None:
        """Ensures chained song interludes and speech bleed can safely overlap without being trimmed."""
        segments = [
            {"label": "song", "start_time": "00:01:00.000", "end_time": "00:05:30.000"},
            # Next song starts at 05:00, sharing a 30-second transition interlude
            {"label": "song", "start_time": "00:05:00.000", "end_time": "00:10:00.000"} 
        ]
        valid = validate_segments(segments)
        self.assertEqual(len(valid), 2)
        # The 5-minute start time should be preserved perfectly, NOT snapped to 05:30
        self.assertEqual(valid[1]["start_time"], "00:05:00.000")

    def test_validate_segments_fixes_backwards_jumps(self) -> None:
        """Ensures that if the AI hallucinates a segment starting completely before the previous one, it snaps forward."""
        segments = [
            {"label": "sermon", "start_time": "00:10:00.000", "end_time": "00:45:00.000"},
            # Hallucination: The final song accidentally starts at 5 minutes instead of 45 minutes
            {"label": "song", "start_time": "00:05:00.000", "end_time": "00:50:00.000"} 
        ]
        valid = validate_segments(segments)
        self.assertEqual(len(valid), 2)
        # The erroneous 00:05 start time is snapped to the previous segment's start time (00:10)
        self.assertEqual(valid[1]["start_time"], "00:10:00.000")

    # ==============================================================================
    # 4. SUBPROCESS AND FILE I/O MOCKING
    # ==============================================================================
    @patch('audio_segmentation.audio_segmentation.subprocess.run')
    def test_compress_wav_to_mp3_subprocess_call(self, mock_run) -> None:
        """Verifies the FFmpeg compression command is structured correctly."""
        compress_wav_to_mp3("input.wav", "output.mp3")
        mock_run.assert_called_once()
        
        args = mock_run.call_args[0][0]
        # Assert that the dynamically loaded FFMPEG_PATH was passed to subprocess
        self.assertIn(FFMPEG_PATH, args)
        self.assertIn("-b:a", args)
        self.assertIn("192k", args)
        self.assertIn("output.mp3", args[-1]) 

    @patch('audio_segmentation.audio_segmentation.subprocess.run')
    def test_slice_audio_ffmpeg_copy_command_structure(self, mock_run) -> None:
        """Verifies correct parameters for fast-seeking and bit-perfect copying."""
        slice_audio_ffmpeg_copy("input.wav", "output.wav", 1.000, 5.000)
        mock_run.assert_called_once()
        
        args = mock_run.call_args[0][0]
        self.assertIn("-ss", args)
        self.assertIn("1.000", args)
        self.assertIn("-to", args)
        self.assertIn("5.000", args)
        # Ensure the stream copy codec is utilized
        self.assertIn("-c:a", args)
        self.assertIn("copy", args)

    @patch('builtins.open', new_callable=mock_open)
    def test_generate_daw_locators_file_writing(self, mock_file) -> None:
        """Verifies the text marker file is formatted correctly for DAW import in Live 12."""
        segments = [
            {"label": "song", "song_title": "Amazing Grace", "start_time": "00:00:01.000", "end_time": "00:01:00.000"}
        ]
        generate_daw_locators(segments, "/mock_dir", "2026-08-30")
        
        mock_file.assert_called_once_with(os.path.join("/mock_dir", "2026-08-30_DAW_Locators.txt"), 'w', encoding='utf-8')
        handle = mock_file()
        handle.write.assert_called_with("1.000\tAmazing Grace\n")

    # ==============================================================================
    # 5. PIPELINE EXECUTION & ERROR HANDLING
    # ==============================================================================
    @patch('audio_segmentation.audio_segmentation.os.path.exists')
    def test_segment_service_audio_raises_error_if_output_dir_exists(self, mock_exists) -> None:
        """Ensures that the pipeline aborts safely if the destination folder already exists to prevent accidental overwrites."""
        # Setup the mock to return True for the raw audio file, and True for the output directory
        def side_effect(path):
            if "R_20260906" in path: # Simulate raw audio exists
                return True
            if "Output_R_20260906-103109" in path: # Simulate output dir exists
                return True
            return False
            
        mock_exists.side_effect = side_effect
        
        plan = ServicePlan(
            date="2026-09-06",
            songs=[],
            raw_audio_filepath="/mock/raw_audio/R_20260906-103109.wav"
        )
        
        with self.assertRaisesRegex(FileExistsError, "Destination folder already exists"):
            segment_service_audio(plan)


if __name__ == '__main__':
    unittest.main(verbosity=2)
