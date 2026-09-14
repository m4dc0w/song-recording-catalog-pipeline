import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from core.schemas import Song, ServicePlan, PlanSummary, ServiceType
from post_processing.enrich_song_keys import (
    enrich_song_keys,
    PlanningCenterKeyProvider,
    main,
)


class MockProvider:
    def __init__(self, song_map=None):
        self.song_map = song_map or {}

    def get_songs_for_date(self, date_str: str):
        return self.song_map.get(date_str, [])


class TestEnrichSongKeys(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_dummy_file(self, filename: str, content: str = "dummy content") -> str:
        path = os.path.join(self.dir_path, filename)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_enrich_song_keys_exact_match(self):
        # Create MP3, MP4, and WAV files as requested
        self.create_dummy_file("Amazing Grace - 2024-08-04.mp3")
        self.create_dummy_file("Amazing Grace - 2024-08-04.mp4")
        self.create_dummy_file("Way Maker - 2024-08-04.wav")
        self.create_dummy_file("Build My Life - 2024-08-04.wav")
        self.create_dummy_file("In Christ Alone - 2024-08-04.mp4")

        mock_provider = MockProvider({
            "2024-08-04": [
                Song(title="Amazing Grace", key="E"),
                Song(title="Way Maker", key="Bb"),
                Song(title="Build My Life", key="C# Major"),
                Song(title="In Christ Alone", key="D-E"),
            ]
        })

        renamed = enrich_song_keys(self.dir_path, key_provider=mock_provider)
        self.assertEqual(len(renamed), 5)

        # Verify old files are gone and new files exist
        self.assertFalse(os.path.exists(os.path.join(self.dir_path, "Amazing Grace - 2024-08-04.mp3")))
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Amazing Grace - E - 2024-08-04.mp3")))

        self.assertFalse(os.path.exists(os.path.join(self.dir_path, "Amazing Grace - 2024-08-04.mp4")))
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Amazing Grace - E - 2024-08-04.mp4")))

        self.assertFalse(os.path.exists(os.path.join(self.dir_path, "Way Maker - 2024-08-04.wav")))
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Way Maker - Bb - 2024-08-04.wav")))

        self.assertFalse(os.path.exists(os.path.join(self.dir_path, "Build My Life - 2024-08-04.wav")))
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Build My Life - C# Major - 2024-08-04.wav")))

        self.assertFalse(os.path.exists(os.path.join(self.dir_path, "In Christ Alone - 2024-08-04.mp4")))
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "In Christ Alone - D-E - 2024-08-04.mp4")))

    def test_enrich_song_keys_heuristic_prefix(self):
        # PCO has 'Offertory - Amazing Grace'
        self.create_dummy_file("Amazing Grace - 2024-08-04.mp3")

        mock_provider = MockProvider({
            "2024-08-04": [
                Song(title="Offertory - Amazing Grace", key="E"),
            ]
        })

        renamed = enrich_song_keys(self.dir_path, key_provider=mock_provider)
        self.assertEqual(len(renamed), 1)
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Amazing Grace - E - 2024-08-04.mp3")))

    def test_enrich_song_keys_heuristic_parenthetical_key(self):
        # PCO has 'Amazing Grace (E)' with empty key field
        self.create_dummy_file("Amazing Grace - 2024-08-04.mp3")

        mock_provider = MockProvider({
            "2024-08-04": [
                Song(title="Amazing Grace (E)", key=""),
            ]
        })

        renamed = enrich_song_keys(self.dir_path, key_provider=mock_provider)
        self.assertEqual(len(renamed), 1)
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Amazing Grace - E - 2024-08-04.mp3")))

    def test_enrich_song_keys_duplicate_suffix(self):
        # Two performances of Holy Holy in the same service: first in D, second in E
        self.create_dummy_file("Holy Holy - 2024-08-04.mp3")
        self.create_dummy_file("Holy Holy (2) - 2024-08-04.mp3")

        mock_provider = MockProvider({
            "2024-08-04": [
                Song(title="Holy Holy", key="D"),
                Song(title="Holy Holy", key="E"),
            ]
        })

        renamed = enrich_song_keys(self.dir_path, key_provider=mock_provider)
        self.assertEqual(len(renamed), 2)

        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Holy Holy - D - 2024-08-04.mp3")))
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Holy Holy (2) - E - 2024-08-04.mp3")))

    def test_enrich_song_keys_skips_already_keyed(self):
        self.create_dummy_file("Amazing Grace - E - 2024-08-04.mp3")

        mock_provider = MockProvider({
            "2024-08-04": [Song(title="Amazing Grace", key="E")]
        })

        renamed = enrich_song_keys(self.dir_path, key_provider=mock_provider)
        self.assertEqual(len(renamed), 0)
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Amazing Grace - E - 2024-08-04.mp3")))

    def test_enrich_song_keys_key_modulation(self):
        # Song modulating from D to E (shows up as 'D-E' in Planning Center)
        self.create_dummy_file("In Christ Alone - 2026-09-13.mp4")

        mock_provider = MockProvider({
            "2026-09-13": [
                Song(title="In Christ Alone", key="D-E"),
            ]
        })

        renamed = enrich_song_keys(self.dir_path, key_provider=mock_provider)
        self.assertEqual(len(renamed), 1)
        expected_file = os.path.join(self.dir_path, "In Christ Alone - D-E - 2026-09-13.mp4")
        self.assertTrue(os.path.exists(expected_file))
        self.assertFalse(os.path.exists(os.path.join(self.dir_path, "In Christ Alone - 2026-09-13.mp4")))

        # Re-running key enrichment should skip this file because it already has key 'D-E'
        renamed_second_pass = enrich_song_keys(self.dir_path, key_provider=mock_provider)
        self.assertEqual(len(renamed_second_pass), 0)
        self.assertTrue(os.path.exists(expected_file))

    def test_enrich_song_keys_sharp_keys(self):
        # Verify sharp keys: C# Major, F#, C#m, G# Minor across media formats
        self.create_dummy_file("Build My Life - 2024-08-04.wav")
        self.create_dummy_file("Gratitude - 2024-08-04.mp3")
        self.create_dummy_file("King of Kings - 2024-08-04.mp4")
        self.create_dummy_file("Way Maker - 2024-08-04.mp3")

        mock_provider = MockProvider({
            "2024-08-04": [
                Song(title="Build My Life", key="C# Major"),
                Song(title="Gratitude", key="F#"),
                Song(title="King of Kings", key="C#m"),
                Song(title="Way Maker", key="G# Minor"),
            ]
        })

        renamed = enrich_song_keys(self.dir_path, key_provider=mock_provider)
        self.assertEqual(len(renamed), 4)

        expected_build = os.path.join(self.dir_path, "Build My Life - C# Major - 2024-08-04.wav")
        expected_gratitude = os.path.join(self.dir_path, "Gratitude - F# - 2024-08-04.mp3")
        expected_king = os.path.join(self.dir_path, "King of Kings - C#m - 2024-08-04.mp4")
        expected_way = os.path.join(self.dir_path, "Way Maker - G# Minor - 2024-08-04.mp3")

        self.assertTrue(os.path.exists(expected_build))
        self.assertTrue(os.path.exists(expected_gratitude))
        self.assertTrue(os.path.exists(expected_king))
        self.assertTrue(os.path.exists(expected_way))

        # Re-running key enrichment must skip these files because sharp keys are valid
        second_pass = enrich_song_keys(self.dir_path, key_provider=mock_provider)
        self.assertEqual(len(second_pass), 0)

    def test_enrich_song_keys_sharp_key_parenthetical(self):
        # Verify sharp keys embedded in song titles (e.g. Planning Center item names)
        self.create_dummy_file("Build My Life - 2024-08-04.wav")
        self.create_dummy_file("Gratitude - 2024-08-04.mp4")

        mock_provider = MockProvider({
            "2024-08-04": [
                Song(title="Build My Life (C# Major)", key=""),
                Song(title="Gratitude (F#)", key=""),
            ]
        })

        renamed = enrich_song_keys(self.dir_path, key_provider=mock_provider)
        self.assertEqual(len(renamed), 2)

        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Build My Life - C# Major - 2024-08-04.wav")))
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Gratitude - F# - 2024-08-04.mp4")))

    def test_enrich_song_keys_key_modulations_with_sharps(self):
        # Verify key changes/modulations with sharp keys and spacing variations
        self.create_dummy_file("Song One - 2026-09-13.wav")
        self.create_dummy_file("Song Two - 2026-09-13.mp3")
        self.create_dummy_file("Song Three - 2026-09-13.mp4")
        self.create_dummy_file("Song Four - 2026-09-13.wav")

        mock_provider = MockProvider({
            "2026-09-13": [
                Song(title="Song One", key="C#-D#"),
                Song(title="Song Two", key="B-C#"),
                Song(title="Song Three", key="D - E"),
                Song(title="Song Four", key="C# Major - D# Major"),
            ]
        })

        renamed = enrich_song_keys(self.dir_path, key_provider=mock_provider)
        self.assertEqual(len(renamed), 4)

        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Song One - C#-D# - 2026-09-13.wav")))
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Song Two - B-C# - 2026-09-13.mp3")))
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Song Three - D-E - 2026-09-13.mp4")))
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Song Four - C# Major-D# Major - 2026-09-13.wav")))

        # Re-running skips all already-keyed modulation files
        second_pass = enrich_song_keys(self.dir_path, key_provider=mock_provider)
        self.assertEqual(len(second_pass), 0)

    def test_enrich_song_keys_skips_if_target_exists(self):
        self.create_dummy_file("Amazing Grace - 2024-08-04.mp3")
        self.create_dummy_file("Amazing Grace - E - 2024-08-04.mp3")

        mock_provider = MockProvider({
            "2024-08-04": [Song(title="Amazing Grace", key="E")]
        })

        renamed = enrich_song_keys(self.dir_path, key_provider=mock_provider)
        self.assertEqual(len(renamed), 0)

    def test_enrich_song_keys_skips_when_no_key_found(self):
        self.create_dummy_file("Unknown Piece - 2024-08-04.mp3")

        mock_provider = MockProvider({
            "2024-08-04": [Song(title="Amazing Grace", key="E")]
        })

        renamed = enrich_song_keys(self.dir_path, key_provider=mock_provider)
        self.assertEqual(len(renamed), 0)
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Unknown Piece - 2024-08-04.mp3")))

    def test_enrich_song_keys_dry_run(self):
        self.create_dummy_file("Amazing Grace - 2024-08-04.mp3")

        mock_provider = MockProvider({
            "2024-08-04": [Song(title="Amazing Grace", key="E")]
        })

        renamed = enrich_song_keys(self.dir_path, dry_run=True, key_provider=mock_provider)
        self.assertEqual(len(renamed), 1)

        # File was NOT renamed on disk
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Amazing Grace - 2024-08-04.mp3")))
        self.assertFalse(os.path.exists(os.path.join(self.dir_path, "Amazing Grace - E - 2024-08-04.mp3")))

    def test_enrich_song_keys_date_filter(self):
        self.create_dummy_file("Song A - 2024-08-04.mp3")
        self.create_dummy_file("Song B - 2024-08-11.mp3")

        mock_provider = MockProvider({
            "2024-08-04": [Song(title="Song A", key="G")],
            "2024-08-11": [Song(title="Song B", key="D")],
        })

        renamed = enrich_song_keys(self.dir_path, target_date="2024-08-04", key_provider=mock_provider)
        self.assertEqual(len(renamed), 1)
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Song A - G - 2024-08-04.mp3")))
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Song B - 2024-08-11.mp3")))

    def test_enrich_song_keys_date_range_filter(self):
        self.create_dummy_file("Song A - 2024-07-28.mp3")
        self.create_dummy_file("Song B - 2024-08-04.mp3")
        self.create_dummy_file("Song C - 2024-09-01.mp3")

        mock_provider = MockProvider({
            "2024-07-28": [Song(title="Song A", key="A")],
            "2024-08-04": [Song(title="Song B", key="B")],
            "2024-09-01": [Song(title="Song C", key="C")],
        })

        renamed = enrich_song_keys(
            self.dir_path,
            start_date="2024-08-01",
            end_date="2024-08-31",
            key_provider=mock_provider,
        )
        self.assertEqual(len(renamed), 1)
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Song A - 2024-07-28.mp3")))
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Song B - B - 2024-08-04.mp3")))
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Song C - 2024-09-01.mp3")))

    def test_enrich_song_keys_multiple_directories(self):
        dir2 = tempfile.mkdtemp()
        try:
            self.create_dummy_file("Amazing Grace - 2024-08-04.mp3")
            with open(os.path.join(dir2, "Amazing Grace - 2024-08-04.mp4"), "w") as f:
                f.write("video content")

            mock_provider = MockProvider({
                "2024-08-04": [Song(title="Amazing Grace", key="E")]
            })

            renamed = enrich_song_keys([self.dir_path, dir2], key_provider=mock_provider)
            self.assertEqual(len(renamed), 2)
            self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Amazing Grace - E - 2024-08-04.mp3")))
            self.assertTrue(os.path.exists(os.path.join(dir2, "Amazing Grace - E - 2024-08-04.mp4")))
        finally:
            import shutil
            shutil.rmtree(dir2)

    @patch("data_sources.planning_center.fetch_recent_plans")
    @patch("data_sources.planning_center.fetch_service_plan")
    def test_planning_center_key_provider_caching(self, mock_fetch_plan, mock_fetch_recent):
        mock_fetch_recent.return_value = [PlanSummary(id="plan123", date="2024-08-04")]
        mock_fetch_plan.return_value = ServicePlan(
            date="2024-08-04",
            songs=[Song(title="Amazing Grace", key="E")]
        )

        provider = PlanningCenterKeyProvider(service_type_id="st999")
        songs1 = provider.get_songs_for_date("2024-08-04")
        self.assertEqual(len(songs1), 1)
        self.assertEqual(songs1[0].key, "E")

        # Second call should hit the cache without calling the API again
        songs2 = provider.get_songs_for_date("2024-08-04")
        self.assertEqual(len(songs2), 1)
        self.assertEqual(mock_fetch_recent.call_count, 1)
        self.assertEqual(mock_fetch_plan.call_count, 1)

    def test_enrich_song_keys_embedded_parenthetical_keys_normalization(self):
        # Test case A: Files with embedded key in title but no key segment in filename
        self.create_dummy_file("Yet Not I But Through Christ In Me (D) - 2026-08-02.mp4")
        self.create_dummy_file("10,000 Reasons (Bless The Lord) (D) - 2026-08-02.mp4")

        mock_provider = MockProvider({
            "2026-08-02": [
                Song(title="Yet Not I But Through Christ In Me", key="D"),
                Song(title="10,000 Reasons (Bless The Lord)", key="D"),
            ]
        })

        renamed = enrich_song_keys(self.dir_path, key_provider=mock_provider)
        self.assertEqual(len(renamed), 2)

        self.assertFalse(os.path.exists(os.path.join(self.dir_path, "Yet Not I But Through Christ In Me (D) - 2026-08-02.mp4")))
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Yet Not I But Through Christ In Me - D - 2026-08-02.mp4")))

        self.assertFalse(os.path.exists(os.path.join(self.dir_path, "10,000 Reasons (Bless The Lord) (D) - 2026-08-02.mp4")))
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "10,000 Reasons (Bless The Lord) - D - 2026-08-02.mp4")))

        # Running again should skip because they are already normalized
        renamed_second = enrich_song_keys(self.dir_path, key_provider=mock_provider)
        self.assertEqual(len(renamed_second), 0)

    def test_enrich_song_keys_duplicate_embedded_and_segment_key_normalization(self):
        # Test case B: Files that already had - Key - appended but retained embedded (Key) in title
        self.create_dummy_file("Yet Not I But Through Christ In Me (D) - D - 2026-08-02.mp4")
        self.create_dummy_file("10,000 Reasons (Bless The Lord) (D) - D - 2026-08-02.mp4")

        mock_provider = MockProvider({
            "2026-08-02": [
                Song(title="Yet Not I But Through Christ In Me", key="D"),
                Song(title="10,000 Reasons (Bless The Lord)", key="D"),
            ]
        })

        renamed = enrich_song_keys(self.dir_path, key_provider=mock_provider)
        self.assertEqual(len(renamed), 2)

        self.assertFalse(os.path.exists(os.path.join(self.dir_path, "Yet Not I But Through Christ In Me (D) - D - 2026-08-02.mp4")))
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "Yet Not I But Through Christ In Me - D - 2026-08-02.mp4")))

        self.assertFalse(os.path.exists(os.path.join(self.dir_path, "10,000 Reasons (Bless The Lord) (D) - D - 2026-08-02.mp4")))
        self.assertTrue(os.path.exists(os.path.join(self.dir_path, "10,000 Reasons (Bless The Lord) - D - 2026-08-02.mp4")))

        # Running again should skip
        renamed_second = enrich_song_keys(self.dir_path, key_provider=mock_provider)
        self.assertEqual(len(renamed_second), 0)

    @patch("post_processing.enrich_song_keys.enrich_song_keys")
    def test_main_cli(self, mock_enrich):
        main(["--dir", self.dir_path, "--date", "2024-08-04", "--dry-run"])
        mock_enrich.assert_called_once_with(
            directories=[self.dir_path],
            target_date="2024-08-04",
            start_date=None,
            end_date=None,
            service_type_id=None,
            dry_run=True,
        )


if __name__ == "__main__":
    unittest.main()
