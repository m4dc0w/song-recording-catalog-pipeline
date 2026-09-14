import unittest
from core.schemas import Song
from core.helpers import (
    filename_to_song,
    song_to_filename,
    from_filename_to_song,
    from_song_to_filename,
    find_matching_song,
    extract_key_from_song,
    is_valid_musical_key,
    normalize_song_title,
    strip_embedded_key_from_title,
)


class TestCoreHelpers(unittest.TestCase):

    def test_is_valid_musical_key(self):
        self.assertTrue(is_valid_musical_key("E"))
        self.assertTrue(is_valid_musical_key("G"))
        self.assertTrue(is_valid_musical_key("Bm"))
        self.assertTrue(is_valid_musical_key("F#m"))
        self.assertTrue(is_valid_musical_key("Eb"))
        self.assertTrue(is_valid_musical_key("Db"))
        self.assertTrue(is_valid_musical_key("G/B"))
        self.assertTrue(is_valid_musical_key("Eb/G"))
        
        # Sharp keys and modes
        self.assertTrue(is_valid_musical_key("C#"))
        self.assertTrue(is_valid_musical_key("C# Major"))
        self.assertTrue(is_valid_musical_key("C# Minor"))
        self.assertTrue(is_valid_musical_key("C#m"))
        self.assertTrue(is_valid_musical_key("F#"))
        self.assertTrue(is_valid_musical_key("F# Major"))
        self.assertTrue(is_valid_musical_key("F#m"))
        self.assertTrue(is_valid_musical_key("G# Minor"))
        self.assertTrue(is_valid_musical_key("Bb Major"))
        
        # Key changes / modulations
        self.assertTrue(is_valid_musical_key("D-E"))
        self.assertTrue(is_valid_musical_key("C-D-E"))
        self.assertTrue(is_valid_musical_key("Eb-F"))
        self.assertTrue(is_valid_musical_key("Bm-C#m"))
        self.assertTrue(is_valid_musical_key("G-Ab"))
        self.assertTrue(is_valid_musical_key("D - E"))
        self.assertTrue(is_valid_musical_key("D->E"))
        self.assertTrue(is_valid_musical_key("D–E"))
        self.assertTrue(is_valid_musical_key("C#-D#"))
        self.assertTrue(is_valid_musical_key("C# Major - D# Major"))
        self.assertTrue(is_valid_musical_key("B-C#"))
        
        self.assertFalse(is_valid_musical_key(""))
        self.assertFalse(is_valid_musical_key("Part 1"))
        self.assertFalse(is_valid_musical_key("2026"))
        self.assertFalse(is_valid_musical_key("Amazing Grace"))
        self.assertFalse(is_valid_musical_key("D-X"))
        self.assertFalse(is_valid_musical_key("Part-1"))

    def test_filename_to_song_basic(self):
        song = filename_to_song("Amazing Grace - 2026-06-21.mp3")
        self.assertIsNotNone(song)
        self.assertEqual(song.title, "Amazing Grace")
        self.assertEqual(song.key, "")
        self.assertEqual(song.date, "2026-06-21")

    def test_filename_to_song_with_key(self):
        song = filename_to_song("Amazing Grace - E - 2024-08-04.mp3")
        self.assertIsNotNone(song)
        self.assertEqual(song.title, "Amazing Grace")
        self.assertEqual(song.key, "E")
        self.assertEqual(song.date, "2024-08-04")

    def test_filename_to_song_with_minor_and_slash_keys(self):
        song_bm = filename_to_song("Great Are You Lord - Bm - 2026-09-06.wav")
        self.assertEqual(song_bm.title, "Great Are You Lord")
        self.assertEqual(song_bm.key, "Bm")
        self.assertEqual(song_bm.date, "2026-09-06")

        song_eb = filename_to_song("Living Hope - Eb - 2026-09-06.mp4")
        self.assertEqual(song_eb.title, "Living Hope")
        self.assertEqual(song_eb.key, "Eb")
        self.assertEqual(song_eb.date, "2026-09-06")

    def test_filename_to_song_with_key_modulation(self):
        # Key change / modulation from D Major to E Major (D-E)
        song = filename_to_song("In Christ Alone - D-E - 2026-09-13.mp4")
        self.assertIsNotNone(song)
        self.assertEqual(song.title, "In Christ Alone")
        self.assertEqual(song.key, "D-E")
        self.assertEqual(song.date, "2026-09-13")

        # Without date
        song_no_date = filename_to_song("In Christ Alone - D-E.mp4")
        self.assertIsNotNone(song_no_date)
        self.assertEqual(song_no_date.title, "In Christ Alone")
        self.assertEqual(song_no_date.key, "D-E")
        self.assertIsNone(song_no_date.date)

        # With duplicate suffix
        song_dup = filename_to_song("In Christ Alone (2) - D-E - 2026-09-13.wav")
        self.assertIsNotNone(song_dup)
        self.assertEqual(song_dup.title, "In Christ Alone (2)")
        self.assertEqual(song_dup.key, "D-E")
        self.assertEqual(song_dup.date, "2026-09-13")

        # Multi-key modulation C to D to E
        song_multi = filename_to_song("Medley - C-D-E - 2026-09-13.mp3")
        self.assertEqual(song_multi.title, "Medley")
        self.assertEqual(song_multi.key, "C-D-E")
        self.assertEqual(song_multi.date, "2026-09-13")

        # Sharp key modulation (e.g. C#-D#, B-C#)
        song_sharp_mod = filename_to_song("Build My Life - C#-D# - 2026-09-13.wav")
        self.assertIsNotNone(song_sharp_mod)
        self.assertEqual(song_sharp_mod.title, "Build My Life")
        self.assertEqual(song_sharp_mod.key, "C#-D#")
        self.assertEqual(song_sharp_mod.date, "2026-09-13")

        # Sharp key with mode (e.g. C# Major, F# Minor)
        song_sharp_major = filename_to_song("Build My Life - C# Major - 2026-09-13.mp3")
        self.assertIsNotNone(song_sharp_major)
        self.assertEqual(song_sharp_major.title, "Build My Life")
        self.assertEqual(song_sharp_major.key, "C# Major")
        self.assertEqual(song_sharp_major.date, "2026-09-13")

    def test_filename_to_song_duplicate_suffix(self):
        song = filename_to_song("Amazing Grace (2) - 2026-06-21.mp3")
        self.assertEqual(song.title, "Amazing Grace (2)")
        self.assertEqual(song.key, "")
        self.assertEqual(song.date, "2026-06-21")

        song_with_key = filename_to_song("Amazing Grace (2) - E - 2026-06-21.mp3")
        self.assertEqual(song_with_key.title, "Amazing Grace (2)")
        self.assertEqual(song_with_key.key, "E")
        self.assertEqual(song_with_key.date, "2026-06-21")

    def test_filename_to_song_hyphen_in_title(self):
        song = filename_to_song("Part 1 - Opening Song - 2026-06-21.mp3")
        self.assertEqual(song.title, "Part 1 - Opening Song")
        self.assertEqual(song.key, "")
        self.assertEqual(song.date, "2026-06-21")

        song_with_key = filename_to_song("Part 1 - Opening Song - G - 2026-06-21.mp3")
        self.assertEqual(song_with_key.title, "Part 1 - Opening Song")
        self.assertEqual(song_with_key.key, "G")
        self.assertEqual(song_with_key.date, "2026-06-21")

    def test_filename_to_song_full_path(self):
        song = filename_to_song("/my/verified_audio/Videos/Amazing Grace - 2024-08-04.mp4")
        self.assertEqual(song.title, "Amazing Grace")
        self.assertEqual(song.key, "")
        self.assertEqual(song.date, "2024-08-04")

    def test_filename_to_song_empty_or_none(self):
        self.assertIsNone(filename_to_song(""))
        self.assertIsNone(filename_to_song("   "))

    def test_song_to_filename(self):
        # Song with date, no key
        song1 = Song(title="Amazing Grace", date="2024-08-04")
        self.assertEqual(song_to_filename(song1, ext=".mp3"), "Amazing Grace - 2024-08-04.mp3")
        self.assertEqual(song_to_filename(song1, ext="mp4"), "Amazing Grace - 2024-08-04.mp4")

        # Song with key and date
        song2 = Song(title="Amazing Grace", key="E", date="2024-08-04")
        self.assertEqual(song_to_filename(song2, ext=".mp3"), "Amazing Grace - E - 2024-08-04.mp3")
        self.assertEqual(song_to_filename(song2, ext=".mp4"), "Amazing Grace - E - 2024-08-04.mp4")

        # Song with modulated key (D-E)
        song_mod = Song(title="In Christ Alone", key="D-E", date="2026-09-13")
        self.assertEqual(song_to_filename(song_mod, ext=".mp4"), "In Christ Alone - D-E - 2026-09-13.mp4")

        # Song with spaces in key ('D - E') gets normalized in filename
        song_mod_spaces = Song(title="In Christ Alone", key="D - E", date="2026-09-13")
        self.assertEqual(song_to_filename(song_mod_spaces, ext=".mp4"), "In Christ Alone - D-E - 2026-09-13.mp4")

        # Song with key only
        song3 = Song(title="Amazing Grace", key="E")
        self.assertEqual(song_to_filename(song3), "Amazing Grace - E")

        # Song with title only
        song4 = Song(title="Amazing Grace")
        self.assertEqual(song_to_filename(song4), "Amazing Grace")

    def test_backward_compatible_aliases(self):
        song = from_filename_to_song("Amazing Grace - 2024-08-04.mp3")
        self.assertEqual(song.title, "Amazing Grace")
        self.assertEqual(song.date, "2024-08-04")

        filename = from_song_to_filename(Song(title="Amazing Grace", key="E", date="2024-08-04"), ext=".mp3")
        self.assertEqual(filename, "Amazing Grace - E - 2024-08-04.mp3")

    def test_extract_key_from_song(self):
        song_with_key = Song(title="Amazing Grace", key="E")
        self.assertEqual(extract_key_from_song(song_with_key), "E")

        song_with_modulation_key = Song(title="In Christ Alone", key="D-E")
        self.assertEqual(extract_key_from_song(song_with_modulation_key), "D-E")

        song_with_key_in_title = Song(title="Amazing Grace (E)", key="")
        self.assertEqual(extract_key_from_song(song_with_key_in_title), "E")

        song_with_modulation_in_title = Song(title="In Christ Alone (D-E)", key="")
        self.assertEqual(extract_key_from_song(song_with_modulation_in_title), "D-E")

        song_with_slash_key_in_title = Song(title="Living Hope (Eb/G)", key="")
        self.assertEqual(extract_key_from_song(song_with_slash_key_in_title), "Eb/G")

        song_with_sharp_major = Song(title="Build My Life", key="C# Major")
        self.assertEqual(extract_key_from_song(song_with_sharp_major), "C# Major")

        song_with_sharp_major_in_title = Song(title="Build My Life (C# Major)", key="")
        self.assertEqual(extract_key_from_song(song_with_sharp_major_in_title), "C# Major")

        song_with_sharp_mod_in_title = Song(title="Gratitude (B-C#)", key="")
        self.assertEqual(extract_key_from_song(song_with_sharp_mod_in_title), "B-C#")

        song_without_key = Song(title="Amazing Grace", key="")
        self.assertEqual(extract_key_from_song(song_without_key), "")

    def test_find_matching_song_exact(self):
        candidates = [
            Song(title="Great Are You Lord", key="A"),
            Song(title="Amazing Grace", key="E"),
            Song(title="Way Maker", key="Bb"),
        ]
        match = find_matching_song("Amazing Grace", candidates)
        self.assertIsNotNone(match)
        self.assertEqual(match.title, "Amazing Grace")
        self.assertEqual(match.key, "E")

    def test_find_matching_song_offertory_prefix(self):
        candidates = [
            Song(title="Offertory - Amazing Grace", key="E"),
            Song(title="Way Maker", key="Bb"),
        ]
        match = find_matching_song("Amazing Grace", candidates)
        self.assertIsNotNone(match)
        self.assertEqual(match.title, "Offertory - Amazing Grace")
        self.assertEqual(match.key, "E")

    def test_find_matching_song_parenthetical(self):
        candidates = [
            Song(title="Amazing Grace (E)", key="E"),
            Song(title="Crown Him With Many Crowns", key="D"),
        ]
        match = find_matching_song("Amazing Grace", candidates)
        self.assertIsNotNone(match)
        self.assertEqual(match.title, "Amazing Grace (E)")
        self.assertEqual(match.key, "E")

    def test_find_matching_song_duplicate_index(self):
        candidates = [
            Song(title="Holy Holy", key="D"),
            Song(title="Great Are You Lord", key="G"),
            Song(title="Holy Holy", key="E"),
        ]
        match_first = find_matching_song("Holy Holy", candidates)
        self.assertEqual(match_first.key, "D")

        match_second = find_matching_song("Holy Holy (2)", candidates)
        self.assertEqual(match_second.key, "E")

    def test_find_matching_song_fuzzy(self):
        candidates = [
            Song(title="All Hail King Jesus (Live at Passion)", key="B"),
        ]
        match = find_matching_song("All Hail King Jesus", candidates)
        self.assertIsNotNone(match)
        self.assertEqual(match.key, "B")


    def test_strip_embedded_key_from_title(self):
        self.assertEqual(
            strip_embedded_key_from_title("Yet Not I But Through Christ In Me (D)"),
            ("Yet Not I But Through Christ In Me", "D"),
        )
        self.assertEqual(
            strip_embedded_key_from_title("10,000 Reasons (Bless The Lord) (D)"),
            ("10,000 Reasons (Bless The Lord)", "D"),
        )
        self.assertEqual(
            strip_embedded_key_from_title("10,000 Reasons (Bless The Lord)"),
            ("10,000 Reasons (Bless The Lord)", ""),
        )
        self.assertEqual(
            strip_embedded_key_from_title("Yet Not I But Through Christ In Me (D) (2)"),
            ("Yet Not I But Through Christ In Me (2)", "D"),
        )
        self.assertEqual(
            strip_embedded_key_from_title("Yet Not I But Through Christ In Me (2) (D)"),
            ("Yet Not I But Through Christ In Me (2)", "D"),
        )
        self.assertEqual(
            strip_embedded_key_from_title("In Christ Alone (D-E)"),
            ("In Christ Alone", "D-E"),
        )
        self.assertEqual(
            strip_embedded_key_from_title("Build My Life (C# Major)"),
            ("Build My Life", "C# Major"),
        )
        self.assertEqual(
            strip_embedded_key_from_title("Amazing Grace"),
            ("Amazing Grace", ""),
        )

    def test_filename_to_song_embedded_keys_normalization(self):
        # User example 1: 'Yet Not I But Through Christ In Me (D) - 2026-08-02.mp4'
        s1 = filename_to_song("Yet Not I But Through Christ In Me (D) - 2026-08-02.mp4")
        self.assertIsNotNone(s1)
        self.assertEqual(s1.title, "Yet Not I But Through Christ In Me")
        self.assertEqual(s1.key, "D")
        self.assertEqual(s1.date, "2026-08-02")
        self.assertEqual(song_to_filename(s1, ext=".mp4"), "Yet Not I But Through Christ In Me - D - 2026-08-02.mp4")

        # User example 2: 'Yet Not I But Through Christ In Me (D) - D - 2026-08-02.mp4'
        s2 = filename_to_song("Yet Not I But Through Christ In Me (D) - D - 2026-08-02.mp4")
        self.assertIsNotNone(s2)
        self.assertEqual(s2.title, "Yet Not I But Through Christ In Me")
        self.assertEqual(s2.key, "D")
        self.assertEqual(s2.date, "2026-08-02")
        self.assertEqual(song_to_filename(s2, ext=".mp4"), "Yet Not I But Through Christ In Me - D - 2026-08-02.mp4")

        # User example 3: '10,000 Reasons (Bless The Lord) (D) - 2026-08-02.mp4'
        s3 = filename_to_song("10,000 Reasons (Bless The Lord) (D) - 2026-08-02.mp4")
        self.assertIsNotNone(s3)
        self.assertEqual(s3.title, "10,000 Reasons (Bless The Lord)")
        self.assertEqual(s3.key, "D")
        self.assertEqual(s3.date, "2026-08-02")
        self.assertEqual(song_to_filename(s3, ext=".mp4"), "10,000 Reasons (Bless The Lord) - D - 2026-08-02.mp4")

        # User example 4: '10,000 Reasons (Bless The Lord) (D) - D - 2026-08-02.mp4'
        s4 = filename_to_song("10,000 Reasons (Bless The Lord) (D) - D - 2026-08-02.mp4")
        self.assertIsNotNone(s4)
        self.assertEqual(s4.title, "10,000 Reasons (Bless The Lord)")
        self.assertEqual(s4.key, "D")
        self.assertEqual(s4.date, "2026-08-02")
        self.assertEqual(song_to_filename(s4, ext=".mp4"), "10,000 Reasons (Bless The Lord) - D - 2026-08-02.mp4")

        # User example 5: 'Angels We Have Heard On High (1) - E - 2024-11-17.mp4' (unchanged)
        s5 = filename_to_song("Angels We Have Heard On High (1) - E - 2024-11-17.mp4")
        self.assertIsNotNone(s5)
        self.assertEqual(s5.title, "Angels We Have Heard On High (1)")
        self.assertEqual(s5.key, "E")
        self.assertEqual(s5.date, "2024-11-17")
        self.assertEqual(song_to_filename(s5, ext=".mp4"), "Angels We Have Heard On High (1) - E - 2024-11-17.mp4")

        # User example 6: Embedded parenthetical key that does NOT match filename key (unchanged)
        s6 = filename_to_song("Angels We Have Heard On High (G) - E - 2024-11-17.mp4")
        self.assertIsNotNone(s6)
        self.assertEqual(s6.title, "Angels We Have Heard On High (G)")
        self.assertEqual(s6.key, "E")
        self.assertEqual(s6.date, "2024-11-17")
        self.assertEqual(song_to_filename(s6, ext=".mp4"), "Angels We Have Heard On High (G) - E - 2024-11-17.mp4")

        # User example 7: Exact match key with duplicate track suffix
        s7 = filename_to_song("10,000 Reasons (Bless The Lord) (D) (2) - D - 2026-08-02.mp4")
        self.assertIsNotNone(s7)
        self.assertEqual(s7.title, "10,000 Reasons (Bless The Lord) (2)")
        self.assertEqual(s7.key, "D")
        self.assertEqual(s7.date, "2026-08-02")
        self.assertEqual(song_to_filename(s7, ext=".mp4"), "10,000 Reasons (Bless The Lord) (2) - D - 2026-08-02.mp4")


if __name__ == '__main__':
    unittest.main()
