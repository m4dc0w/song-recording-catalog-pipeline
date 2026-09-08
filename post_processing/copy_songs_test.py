import os
import shutil
import tempfile
import unittest
from post_processing.copy_songs import copy_songs, format_duplicate_song_name

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

    def test_copy_songs_filter_by_target_date(self):
        folder_sep6 = os.path.join(self.src_dir, "Output_R_20260906-103109")
        folder_aug30 = os.path.join(self.src_dir, "Output_R_20260830-100000")
        os.makedirs(folder_sep6)
        os.makedirs(folder_aug30)

        with open(os.path.join(folder_sep6, "Song_01_Amazing Grace - 2026-09-06.wav"), 'w') as f:
            f.write("audio1")
        with open(os.path.join(folder_sep6, "Song_02_How Great - 2026-09-06.wav"), 'w') as f:
            f.write("audio2")
        with open(os.path.join(folder_aug30, "Song_01_Crown Him - 2026-08-30.wav"), 'w') as f:
            f.write("audio3")

        copy_songs(self.src_dir, self.dest_dir, target_date="2026-09-06")

        dest_files = set(os.listdir(self.dest_dir))
        expected_files = {"Amazing Grace - 2026-09-06.wav", "How Great - 2026-09-06.wav"}
        self.assertEqual(dest_files, expected_files)

    def test_copy_songs_filter_by_folder_date(self):
        """Files without a date in the filename inherit the date from their enclosing folder."""
        folder = os.path.join(self.src_dir, "Output_R_20260906-103109")
        os.makedirs(folder)

        with open(os.path.join(folder, "Song_01_Holy Holy.wav"), 'w') as f:
            f.write("audio")

        copy_songs(self.src_dir, self.dest_dir, target_date="2026-09-06")

        dest_files = set(os.listdir(self.dest_dir))
        self.assertEqual(dest_files, {"Holy Holy.wav"})

    def test_copy_songs_filter_by_date_range(self):
        folder_aug15 = os.path.join(self.src_dir, "Output_R_20260815-100000")
        folder_sep06 = os.path.join(self.src_dir, "Output_R_20260906-103109")
        folder_sep13 = os.path.join(self.src_dir, "Output_R_20260913-100000")
        folder_oct04 = os.path.join(self.src_dir, "Output_R_20261004-100000")
        for fld in (folder_aug15, folder_sep06, folder_sep13, folder_oct04):
            os.makedirs(fld)

        with open(os.path.join(folder_aug15, "Song_01_Song A - 2026-08-15.wav"), 'w') as f:
            f.write("a")
        with open(os.path.join(folder_sep06, "Song_01_Song B - 2026-09-06.wav"), 'w') as f:
            f.write("b")
        with open(os.path.join(folder_sep13, "Song_01_Song C - 2026-09-13.wav"), 'w') as f:
            f.write("c")
        with open(os.path.join(folder_oct04, "Song_01_Song D - 2026-10-04.wav"), 'w') as f:
            f.write("d")

        # Range covers September 2026 only (inclusive)
        copy_songs(self.src_dir, self.dest_dir, start_date="2026-09-01", end_date="2026-09-30")

        dest_files = set(os.listdir(self.dest_dir))
        expected_files = {"Song B - 2026-09-06.wav", "Song C - 2026-09-13.wav"}
        self.assertEqual(dest_files, expected_files)

    def test_format_duplicate_song_name(self):
        self.assertEqual(format_duplicate_song_name("Amazing Grace - 2026-09-06.wav", 1), "Amazing Grace - 2026-09-06.wav")
        self.assertEqual(format_duplicate_song_name("Amazing Grace - 2026-09-06.wav", 2), "Amazing Grace (2) - 2026-09-06.wav")
        self.assertEqual(format_duplicate_song_name("Amazing Grace - 2026-09-06.wav", 3), "Amazing Grace (3) - 2026-09-06.wav")
        self.assertEqual(format_duplicate_song_name("Holy Holy.wav", 1), "Holy Holy.wav")
        self.assertEqual(format_duplicate_song_name("Holy Holy.wav", 2), "Holy Holy (2).wav")
        self.assertEqual(format_duplicate_song_name("Part 1 - Living Hope - 2026-09-06.wav", 2), "Part 1 - Living Hope (2) - 2026-09-06.wav")

    def test_copy_songs_duplicate_titles_same_date(self):
        """When the same song is sung twice in the same service, the 2nd receives ' (2)' before the date."""
        with open(os.path.join(self.src_dir, "Song_01_Amazing Grace - 2026-09-06.wav"), 'w') as f:
            f.write("first_performance")
        with open(os.path.join(self.src_dir, "Song_04_Amazing Grace - 2026-09-06.wav"), 'w') as f:
            f.write("second_performance")
        with open(os.path.join(self.src_dir, "Song_02_How Great - 2026-09-06.wav"), 'w') as f:
            f.write("other_song")

        copy_songs(self.src_dir, self.dest_dir)

        dest_files = set(os.listdir(self.dest_dir))
        expected_files = {
            "Amazing Grace - 2026-09-06.wav",
            "Amazing Grace (2) - 2026-09-06.wav",
            "How Great - 2026-09-06.wav"
        }
        self.assertEqual(dest_files, expected_files)

        with open(os.path.join(self.dest_dir, "Amazing Grace - 2026-09-06.wav"), 'r') as f:
            self.assertEqual(f.read(), "first_performance")
        with open(os.path.join(self.dest_dir, "Amazing Grace (2) - 2026-09-06.wav"), 'r') as f:
            self.assertEqual(f.read(), "second_performance")

    def test_copy_songs_multiple_duplicates_and_idempotency(self):
        """Three occurrences receive (1/base), (2), and (3). Rerunning does not duplicate further."""
        with open(os.path.join(self.src_dir, "Song_01_Holy Holy - 2026-09-06.wav"), 'w') as f:
            f.write("take1")
        with open(os.path.join(self.src_dir, "Song_03_Holy Holy - 2026-09-06.wav"), 'w') as f:
            f.write("take2")
        with open(os.path.join(self.src_dir, "Song_05_Holy Holy - 2026-09-06.wav"), 'w') as f:
            f.write("take3")

        copy_songs(self.src_dir, self.dest_dir)

        dest_files = set(os.listdir(self.dest_dir))
        expected_files = {
            "Holy Holy - 2026-09-06.wav",
            "Holy Holy (2) - 2026-09-06.wav",
            "Holy Holy (3) - 2026-09-06.wav"
        }
        self.assertEqual(dest_files, expected_files)

        # Idempotent re-run: should not create extra files
        copy_songs(self.src_dir, self.dest_dir)
        self.assertEqual(set(os.listdir(self.dest_dir)), expected_files)

    def test_copy_songs_duplicate_titles_without_date(self):
        """Duplicate songs without dates in the filename receive (2) on the title stem."""
        with open(os.path.join(self.src_dir, "Song_01_Glory.wav"), 'w') as f:
            f.write("g1")
        with open(os.path.join(self.src_dir, "Song_02_Glory.wav"), 'w') as f:
            f.write("g2")

        copy_songs(self.src_dir, self.dest_dir)

        dest_files = set(os.listdir(self.dest_dir))
        self.assertEqual(dest_files, {"Glory.wav", "Glory (2).wav"})

    def test_copy_songs_duplicate_chronological_ordering(self):
        """Verifies track numbers are respected even if filenames are discovered out of order."""
        with open(os.path.join(self.src_dir, "Song_10_Praise - 2026-09-06.wav"), 'w') as f:
            f.write("track_10")
        with open(os.path.join(self.src_dir, "Song_02_Praise - 2026-09-06.wav"), 'w') as f:
            f.write("track_2")

        copy_songs(self.src_dir, self.dest_dir)

        with open(os.path.join(self.dest_dir, "Praise - 2026-09-06.wav"), 'r') as f:
            self.assertEqual(f.read(), "track_2")
        with open(os.path.join(self.dest_dir, "Praise (2) - 2026-09-06.wav"), 'r') as f:
            self.assertEqual(f.read(), "track_10")

if __name__ == '__main__':
    unittest.main()
