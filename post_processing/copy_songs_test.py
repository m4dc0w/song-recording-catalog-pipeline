import os
import shutil
import tempfile
import unittest
from post_processing.copy_songs import copy_songs

class TestCopySongs(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.src_dir = os.path.join(self.temp_dir.name, "src")
        self.dest_dir = os.path.join(self.temp_dir.name, "dest")
        os.makedirs(self.src_dir)
        os.makedirs(self.dest_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_copy_songs_strips_prefix_and_copies(self):
        files_to_create = [
            "Song_01_Amazing_Grace.wav",
            "Song_2_How_Great.wav",
            "NotASong_123.wav",
            "Song_99_Test.txt" # Not a wav
        ]
        for f in files_to_create:
            with open(os.path.join(self.src_dir, f), 'w') as temp_f:
                temp_f.write("dummy")

        copy_songs(self.src_dir, self.dest_dir)

        dest_files = set(os.listdir(self.dest_dir))
        expected_files = {"Amazing_Grace.wav", "How_Great.wav"}
        self.assertEqual(dest_files, expected_files)

    def test_copy_songs_does_not_overwrite(self):
        with open(os.path.join(self.src_dir, "Song_01_Existing.wav"), 'w') as temp_f:
            temp_f.write("source_content")

        dest_file_path = os.path.join(self.dest_dir, "Existing.wav")
        with open(dest_file_path, 'w') as temp_f:
            temp_f.write("original_content")

        copy_songs(self.src_dir, self.dest_dir)

        with open(dest_file_path, 'r') as temp_f:
            content = temp_f.read()
            self.assertEqual(content, "original_content")

if __name__ == '__main__':
    unittest.main()
