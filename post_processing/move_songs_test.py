import os
import shutil
import tempfile
import unittest
from post_processing.move_songs import move_songs

class TestMoveSongs(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.src_dir = os.path.join(self.temp_dir.name, "src")
        self.dest_dir = os.path.join(self.temp_dir.name, "dest")
        os.makedirs(self.src_dir)
        os.makedirs(self.dest_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_move_songs_moves_wav_files(self):
        with open(os.path.join(self.src_dir, "Song_1.wav"), 'w') as f:
            f.write("dummy")
        with open(os.path.join(self.src_dir, "NotWav.txt"), 'w') as f:
            f.write("dummy")

        move_songs(self.src_dir, self.dest_dir)

        self.assertTrue(os.path.exists(os.path.join(self.dest_dir, "Song_1.wav")))
        self.assertFalse(os.path.exists(os.path.join(self.src_dir, "Song_1.wav")))
        
        self.assertFalse(os.path.exists(os.path.join(self.dest_dir, "NotWav.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "NotWav.txt")))

    def test_move_songs_does_not_overwrite(self):
        with open(os.path.join(self.src_dir, "Existing.wav"), 'w') as f:
            f.write("new_content")
        
        dest_file = os.path.join(self.dest_dir, "Existing.wav")
        with open(dest_file, 'w') as f:
            f.write("old_content")

        move_songs(self.src_dir, self.dest_dir)

        with open(dest_file, 'r') as f:
            self.assertEqual(f.read(), "old_content")
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "Existing.wav")))

    def test_move_songs_filter_by_target_date(self):
        # Create files for different dates
        with open(os.path.join(self.src_dir, "Amazing Grace - 2026-09-06.wav"), 'w') as f:
            f.write("content1")
        with open(os.path.join(self.src_dir, "How Great - 2026-09-13.wav"), 'w') as f:
            f.write("content2")

        move_songs(self.src_dir, self.dest_dir, target_date="2026-09-06")

        # 2026-09-06 should be moved
        self.assertTrue(os.path.exists(os.path.join(self.dest_dir, "Amazing Grace - 2026-09-06.wav")))
        self.assertFalse(os.path.exists(os.path.join(self.src_dir, "Amazing Grace - 2026-09-06.wav")))

        # 2026-09-13 should remain in source
        self.assertFalse(os.path.exists(os.path.join(self.dest_dir, "How Great - 2026-09-13.wav")))
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "How Great - 2026-09-13.wav")))

    def test_move_songs_filter_by_date_range(self):
        with open(os.path.join(self.src_dir, "Song A - 2026-08-20.wav"), 'w') as f:
            f.write("a")
        with open(os.path.join(self.src_dir, "Song B - 2026-09-06.wav"), 'w') as f:
            f.write("b")
        with open(os.path.join(self.src_dir, "Song C - 2026-10-01.wav"), 'w') as f:
            f.write("c")

        move_songs(self.src_dir, self.dest_dir, start_date="2026-09-01", end_date="2026-09-30")

        self.assertFalse(os.path.exists(os.path.join(self.dest_dir, "Song A - 2026-08-20.wav")))
        self.assertTrue(os.path.exists(os.path.join(self.dest_dir, "Song B - 2026-09-06.wav")))
        self.assertFalse(os.path.exists(os.path.join(self.dest_dir, "Song C - 2026-10-01.wav")))

        # Unmatched files remain in source
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "Song A - 2026-08-20.wav")))
        self.assertFalse(os.path.exists(os.path.join(self.src_dir, "Song B - 2026-09-06.wav")))
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "Song C - 2026-10-01.wav")))

    def test_move_songs_no_match(self):
        with open(os.path.join(self.src_dir, "Song A - 2026-08-20.wav"), 'w') as f:
            f.write("a")

        move_songs(self.src_dir, self.dest_dir, target_date="2026-09-06")

        self.assertFalse(os.path.exists(os.path.join(self.dest_dir, "Song A - 2026-08-20.wav")))
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "Song A - 2026-08-20.wav")))

if __name__ == '__main__':
    unittest.main()
