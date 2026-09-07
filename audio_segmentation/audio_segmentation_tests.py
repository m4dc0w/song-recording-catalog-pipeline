import unittest
from unittest.mock import patch, mock_open
import os

# Import the functions and config to test from the main pipeline script
from audio_segmentation import (
    clean_filename,
    time_to_ms,
    validate_segments,
    compress_wav_to_mp3,
    slice_and_fade_ffmpeg,
    generate_daw_locators,
    FFMPEG_PATH  # Imported dynamically to ensure mock accuracy
)

class TestAudioSegmentation(unittest.TestCase):

    # ==============================================================================
    # 1. STRING AND FILENAME PARSING
    # ==============================================================================
    def test_clean_filename_removes_illegal_chars(self):
        """Ensures macOS/Windows filesystem illegal characters are stripped."""
        self.assertEqual(clean_filename("Amazing Grace?"), "Amazing Grace")
        self.assertEqual(clean_filename('Song "Title" | Remix/Edit\\*'), "Song Title  RemixEdit")
        self.assertEqual(clean_filename("   Praise <God> : Doxology   "), "Praise God  Doxology")

    # ==============================================================================
    # 2. TIME CONVERSION LOGIC
    # ==============================================================================
    def test_time_to_ms_valid_formats(self):
        """Tests standard sub-second timestamp string conversions for 3-part format."""
        self.assertEqual(time_to_ms("00:00:01.000"), 1000)
        self.assertEqual(time_to_ms("00:00:01.500"), 1500)
        # (1 hour * 3600) + (2 min * 60) + 3 sec = 3723 sec -> 3723000 ms + 450 ms
        self.assertEqual(time_to_ms("01:02:03.450"), 3723450) 
        
    def test_time_to_ms_fallback_2_part_formats(self):
        """Tests that the function can gracefully handle 2-part MM:SS.f if Gemini hallucinates it."""
        self.assertEqual(time_to_ms("05:30.000"), 330000) # 5 min * 60 = 300s + 30s = 330s -> 330000ms
        self.assertEqual(time_to_ms("01:00.500"), 60500) 
        
    def test_time_to_ms_sub_second_padding(self):
        """Tests that fractional seconds are padded correctly to milliseconds."""
        self.assertEqual(time_to_ms("00:00:05.5"), 5500)   # .5 should be 500ms
        self.assertEqual(time_to_ms("00:00:05.05"), 5050)  # .05 should be 50ms
        self.assertEqual(time_to_ms("00:00:05.500"), 5500) 

    def test_time_to_ms_invalid_format_returns_zero(self):
        """Ensures malformed timestamps do not crash the pipeline."""
        self.assertEqual(time_to_ms("invalid_time_string"), 0)
        self.assertEqual(time_to_ms("00:00"), 0)

    # ==============================================================================
    # 3. AI OUTPUT VALIDATION (HALLUCINATION PREVENTION)
    # ==============================================================================
    def test_validate_segments_removes_negative_duration(self):
        """Ensures segments where end_time <= start_time are dropped."""
        segments = [
            {"label": "song", "start_time": "00:01:00.000", "end_time": "00:00:30.000"}, # Invalid
            {"label": "speaking", "start_time": "00:01:30.000", "end_time": "00:02:00.000"} # Valid
        ]
        valid = validate_segments(segments)
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0]["label"], "speaking")

    def test_validate_segments_allows_intentional_overlaps(self):
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

    def test_validate_segments_fixes_backwards_jumps(self):
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
    @patch('audio_segmentation.subprocess.run')
    def test_compress_wav_to_mp3_subprocess_call(self, mock_run):
        """Verifies the FFmpeg compression command is structured correctly."""
        compress_wav_to_mp3("input.wav", "output.mp3")
        mock_run.assert_called_once()
        
        args = mock_run.call_args[0][0]
        # Assert that the dynamically loaded FFMPEG_PATH was passed to subprocess
        self.assertIn(FFMPEG_PATH, args)
        self.assertIn("-b:a", args)
        self.assertIn("64k", args)
        self.assertIn("output.mp3", args[-1]) # Output file should be the last arg

    @patch('audio_segmentation.subprocess.run')
    def test_slice_and_fade_ffmpeg_command_structure(self, mock_run):
        """Verifies mathematical conversions for fast-seeking and crossfades."""
        # Test 1000ms -> 5000ms with a 1000ms fade
        slice_and_fade_ffmpeg("input.wav", "output.wav", 1000, 5000, 1000)
        mock_run.assert_called_once()
        
        args = mock_run.call_args[0][0]
        # start_ms = 1000 -> 1.000s
        self.assertIn("1.000", args)
        # duration = 5000 - 1000 = 4000ms -> 4.000s
        self.assertIn("4.000", args)
        # Check if the audio filter (afade) parameter was built
        self.assertTrue(any("afade" in arg for arg in args))

    @patch('builtins.open', new_callable=mock_open)
    def test_generate_daw_locators_file_writing(self, mock_file):
        """Verifies the text marker file is formatted correctly for DAW import in Live 12."""
        segments = [
            {"label": "song", "song_title": "Amazing Grace", "start_time": "00:00:01.000", "end_time": "00:01:00.000"}
        ]
        generate_daw_locators(segments, "/mock_dir", "2026-08-30")
        
        mock_file.assert_called_once_with(os.path.join("/mock_dir", "2026-08-30_DAW_Locators.txt"), 'w', encoding='utf-8')
        handle = mock_file()
        handle.write.assert_called_with("1.000\tAmazing Grace\n")


if __name__ == '__main__':
    unittest.main(verbosity=2)
