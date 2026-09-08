import os
import tempfile
import unittest
from data_sources.local_drive import discover_raw_audio

class TestLocalDrive(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.raw_audio_dir = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_discover_raw_audio_dir_not_exists(self):
        # Pass a non-existent directory
        fake_dir = os.path.join(self.raw_audio_dir, "nonexistent")
        result = discover_raw_audio("2026-09-06", fake_dir)
        self.assertEqual(result, [])

    def test_discover_raw_audio_no_matches(self):
        # Create some unrelated files
        with open(os.path.join(self.raw_audio_dir, "R_20260905-100000.wav"), 'w') as f:
            f.write("dummy")
            
        result = discover_raw_audio("2026-09-06", self.raw_audio_dir)
        self.assertEqual(result, [])

    def test_discover_raw_audio_success_single(self):
        match_file = os.path.join(self.raw_audio_dir, "R_20260906-103109.wav")
        with open(match_file, 'w') as f:
            f.write("dummy")
            
        result = discover_raw_audio("2026-09-06", self.raw_audio_dir)
        self.assertEqual(result, [match_file])

    def test_discover_raw_audio_success_multiple_sorted(self):
        file2 = os.path.join(self.raw_audio_dir, "R_20260906-110000.wav")
        file1 = os.path.join(self.raw_audio_dir, "R_20260906-103109.wav")
        
        # Create out of order to ensure the function sorts them
        with open(file2, 'w') as f:
            f.write("dummy")
        with open(file1, 'w') as f:
            f.write("dummy")
            
        result = discover_raw_audio("2026-09-06", self.raw_audio_dir)
        self.assertEqual(result, [file1, file2])

    def test_discover_raw_audio_ignores_non_wav(self):
        # Has date but wrong extension
        txt_file = os.path.join(self.raw_audio_dir, "R_20260906-103109.txt")
        wav_file = os.path.join(self.raw_audio_dir, "R_20260906-103109.wav")
        
        with open(txt_file, 'w') as f:
            f.write("dummy")
        with open(wav_file, 'w') as f:
            f.write("dummy")
            
        result = discover_raw_audio("2026-09-06", self.raw_audio_dir)
        self.assertEqual(result, [wav_file])

    def test_discover_raw_audio_directory_with_brackets(self):
        # Tests that directory paths containing square brackets (e.g. '[Raw] CBC Recordings')
        # are handled properly and not broken by glob pattern character class syntax
        bracket_dir = os.path.join(self.raw_audio_dir, "[Raw] CBC Recordings")
        os.makedirs(bracket_dir, exist_ok=True)
        wav_file = os.path.join(bracket_dir, "R_20260906-103109.WAV")
        with open(wav_file, 'w') as f:
            f.write("dummy")

        result = discover_raw_audio("2026-09-06", bracket_dir)
        self.assertEqual(result, [wav_file])

if __name__ == '__main__':
    unittest.main()

