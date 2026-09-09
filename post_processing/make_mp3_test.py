import os
import tempfile
import unittest
import wave
import subprocess
from unittest.mock import patch, MagicMock
from post_processing.make_mp3 import make_mp3, main

class TestMakeMp3(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.src_dir = os.path.join(self.temp_dir.name, "src")
        self.dest_dir = os.path.join(self.temp_dir.name, "dest")
        os.makedirs(self.src_dir)
        os.makedirs(self.dest_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_dummy_wav(self, path):
        with wave.open(path, 'w') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b'\x00\x00' * 44100)

    @patch('subprocess.run')
    def test_make_mp3_success(self, mock_subprocess):
        mock_result = MagicMock()
        mock_result.stderr = 'some log text { "input_i": "-20.0", "input_tp": "-2.0", "input_lra": "5.0", "input_thresh": "-30.0", "target_offset": "0.5" } end log'
        mock_subprocess.return_value = mock_result

        self.create_dummy_wav(os.path.join(self.src_dir, "Test - Song.wav"))
        make_mp3(self.src_dir, self.dest_dir, ffmpeg_path="ffmpeg")

        self.assertEqual(mock_subprocess.call_count, 2)
        
        # Pass 1 assertion
        pass1_call = mock_subprocess.call_args_list[0][0][0]
        pass1_cmd_str = " ".join(pass1_call)
        self.assertIn("loudnorm=I=-14:TP=-1:print_format=json", pass1_cmd_str)

        # Pass 2 assertion
        pass2_call = mock_subprocess.call_args_list[1][0][0]
        pass2_cmd_str = " ".join(pass2_call)
        self.assertIn("Test - Song.wav", pass2_cmd_str)
        self.assertIn("-codec:a libmp3lame -q:a 0", pass2_cmd_str)
        self.assertIn("loudnorm=I=-14:TP=-1:measured_I=-20.0", pass2_cmd_str)
        self.assertIn("afade=t=in:st=0:d=3.0", pass2_cmd_str)
        self.assertTrue(pass2_call[-1].endswith("Test - Song.mp3"))

    def test_make_mp3_skips_existing(self):
        self.create_dummy_wav(os.path.join(self.src_dir, "ExistingSong.wav"))
        with open(os.path.join(self.dest_dir, "ExistingSong.mp3"), 'w') as f:
            f.write("dummy mp3")

        with patch('subprocess.run') as mock_subprocess:
            make_mp3(self.src_dir, self.dest_dir)
            mock_subprocess.assert_not_called()

    @patch('subprocess.run')
    def test_make_mp3_filter_by_target_date(self, mock_subprocess):
        mock_result = MagicMock()
        mock_result.stderr = 'some log text { "input_i": "-20.0", "input_tp": "-2.0", "input_lra": "5.0", "input_thresh": "-30.0", "target_offset": "0.5" } end log'
        mock_subprocess.return_value = mock_result

        self.create_dummy_wav(os.path.join(self.src_dir, "Song A - 2026-09-06.wav"))
        self.create_dummy_wav(os.path.join(self.src_dir, "Song B - 2026-09-13.wav"))

        make_mp3(
            self.src_dir,
            self.dest_dir,
            target_date="2026-09-06"
        )

        self.assertEqual(mock_subprocess.call_count, 2)
        cmd_str = " ".join(mock_subprocess.call_args_list[1][0][0])
        self.assertIn("Song A - 2026-09-06.wav", cmd_str)
        self.assertNotIn("Song B - 2026-09-13.wav", cmd_str)

    @patch('subprocess.run')
    def test_make_mp3_filter_by_date_range(self, mock_subprocess):
        mock_result = MagicMock()
        mock_result.stderr = 'some log text { "input_i": "-20.0", "input_tp": "-2.0", "input_lra": "5.0", "input_thresh": "-30.0", "target_offset": "0.5" } end log'
        mock_subprocess.return_value = mock_result

        self.create_dummy_wav(os.path.join(self.src_dir, "Song A - 2026-08-20.wav"))
        self.create_dummy_wav(os.path.join(self.src_dir, "Song B - 2026-09-06.wav"))
        self.create_dummy_wav(os.path.join(self.src_dir, "Song C - 2026-10-01.wav"))

        make_mp3(
            self.src_dir,
            self.dest_dir,
            start_date="2026-09-01",
            end_date="2026-09-30"
        )

        self.assertEqual(mock_subprocess.call_count, 2)
        cmd_str = " ".join(mock_subprocess.call_args_list[1][0][0])
        self.assertIn("Song B - 2026-09-06.wav", cmd_str)
        self.assertNotIn("Song A - 2026-08-20.wav", cmd_str)
        self.assertNotIn("Song C - 2026-10-01.wav", cmd_str)

    @patch('subprocess.run')
    def test_make_mp3_no_matching_date(self, mock_subprocess):
        self.create_dummy_wav(os.path.join(self.src_dir, "Song A - 2026-08-20.wav"))

        make_mp3(
            self.src_dir,
            self.dest_dir,
            target_date="2026-09-06"
        )

        mock_subprocess.assert_not_called()

    def test_make_mp3_missing_src_dir(self):
        with patch('subprocess.run') as mock_subprocess:
            make_mp3("/non/existent/path/for/audio", self.dest_dir)
            mock_subprocess.assert_not_called()

    def test_make_mp3_no_wav_files(self):
        with patch('subprocess.run') as mock_subprocess:
            make_mp3(self.src_dir, self.dest_dir)
            mock_subprocess.assert_not_called()

    @patch('subprocess.run')
    def test_make_mp3_invalid_loudnorm_json(self, mock_subprocess):
        mock_result = MagicMock()
        mock_result.stderr = "No valid json"
        mock_subprocess.return_value = mock_result

        self.create_dummy_wav(os.path.join(self.src_dir, "Song.wav"))
        make_mp3(self.src_dir, self.dest_dir)
        # Only Pass 1 attempted, Pass 2 skipped due to invalid JSON
        self.assertEqual(mock_subprocess.call_count, 1)

    @patch('subprocess.run')
    def test_make_mp3_handles_ffmpeg_error(self, mock_subprocess):
        mock_result = MagicMock()
        mock_result.stderr = 'some log text { "input_i": "-20.0", "input_tp": "-2.0", "input_lra": "5.0", "input_thresh": "-30.0", "target_offset": "0.5" } end log'
        mock_subprocess.side_effect = [mock_result, subprocess.CalledProcessError(1, ["ffmpeg"])]

        self.create_dummy_wav(os.path.join(self.src_dir, "Error - Song.wav"))

        # Should not raise unhandled exception
        make_mp3(self.src_dir, self.dest_dir)
        self.assertEqual(mock_subprocess.call_count, 2)

    @patch('subprocess.run')
    def test_make_mp3_main_cli(self, mock_subprocess):
        mock_result = MagicMock()
        mock_result.stderr = 'some log text { "input_i": "-20.0", "input_tp": "-2.0", "input_lra": "5.0", "input_thresh": "-30.0", "target_offset": "0.5" } end log'
        mock_subprocess.return_value = mock_result

        self.create_dummy_wav(os.path.join(self.src_dir, "CLI - Song.wav"))
        main([
            "--src-dir", self.src_dir,
            "--dest-dir", self.dest_dir,
            "--date", "2026-09-06"
        ])
        # "CLI - Song.wav" has no date, so date filtering won't match
        mock_subprocess.assert_not_called()

        self.create_dummy_wav(os.path.join(self.src_dir, "CLI - Song - 2026-09-06.wav"))
        main([
            "--src-dir", self.src_dir,
            "--dest-dir", self.dest_dir,
            "--date", "2026-09-06"
        ])
        self.assertEqual(mock_subprocess.call_count, 2)

if __name__ == '__main__':
    unittest.main()
