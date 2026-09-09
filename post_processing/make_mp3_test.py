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
        self.create_dummy_wav(os.path.join(self.src_dir, "Test - Song.wav"))
        make_mp3(self.src_dir, self.dest_dir, ffmpeg_path="ffmpeg")

        self.assertEqual(mock_subprocess.call_count, 1)
        cmd_args = mock_subprocess.call_args[0][0]
        cmd_str = " ".join(cmd_args)
        self.assertIn("Test - Song.wav", cmd_str)
        self.assertIn("-codec:a libmp3lame -q:a 0", cmd_str)
        self.assertTrue(cmd_args[-1].endswith("Test - Song.mp3"))

    def test_make_mp3_skips_existing(self):
        self.create_dummy_wav(os.path.join(self.src_dir, "ExistingSong.wav"))
        with open(os.path.join(self.dest_dir, "ExistingSong.mp3"), 'w') as f:
            f.write("dummy mp3")

        with patch('subprocess.run') as mock_subprocess:
            make_mp3(self.src_dir, self.dest_dir)
            mock_subprocess.assert_not_called()

    @patch('subprocess.run')
    def test_make_mp3_filter_by_target_date(self, mock_subprocess):
        self.create_dummy_wav(os.path.join(self.src_dir, "Song A - 2026-09-06.wav"))
        self.create_dummy_wav(os.path.join(self.src_dir, "Song B - 2026-09-13.wav"))

        make_mp3(
            self.src_dir,
            self.dest_dir,
            target_date="2026-09-06"
        )

        self.assertEqual(mock_subprocess.call_count, 1)
        cmd_str = " ".join(mock_subprocess.call_args[0][0])
        self.assertIn("Song A - 2026-09-06.wav", cmd_str)
        self.assertNotIn("Song B - 2026-09-13.wav", cmd_str)

    @patch('subprocess.run')
    def test_make_mp3_filter_by_date_range(self, mock_subprocess):
        self.create_dummy_wav(os.path.join(self.src_dir, "Song A - 2026-08-20.wav"))
        self.create_dummy_wav(os.path.join(self.src_dir, "Song B - 2026-09-06.wav"))
        self.create_dummy_wav(os.path.join(self.src_dir, "Song C - 2026-10-01.wav"))

        make_mp3(
            self.src_dir,
            self.dest_dir,
            start_date="2026-09-01",
            end_date="2026-09-30"
        )

        self.assertEqual(mock_subprocess.call_count, 1)
        cmd_str = " ".join(mock_subprocess.call_args[0][0])
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
    def test_make_mp3_handles_ffmpeg_error(self, mock_subprocess):
        self.create_dummy_wav(os.path.join(self.src_dir, "Error - Song.wav"))
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, ["ffmpeg"])

        # Should not raise exception
        make_mp3(self.src_dir, self.dest_dir)
        self.assertEqual(mock_subprocess.call_count, 1)

    @patch('subprocess.run')
    def test_make_mp3_main_cli(self, mock_subprocess):
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
        self.assertEqual(mock_subprocess.call_count, 1)

if __name__ == '__main__':
    unittest.main()
