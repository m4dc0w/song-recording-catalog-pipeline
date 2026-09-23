import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from core.schemas import Song
from post_processing.make_composite_stems import (
    resolve_device,
    resolve_song,
    check_stem_exists,
    save_audio_stem,
    generate_composite_stems_for_file,
    make_composite_stems,
    main,
    FT_TARGETS,
    SIX_TARGETS,
    ALL_COMPOSITE_STEMS,
)


class TestMakeCompositeStems(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.src_dir = os.path.join(self.test_dir, "verified")
        self.dest_dir = os.path.join(self.test_dir, "stems")
        os.makedirs(self.src_dir, exist_ok=True)
        os.makedirs(self.dest_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_resolve_device_explicit(self):
        self.assertEqual(resolve_device("mps"), "mps")
        self.assertEqual(resolve_device("cuda"), "cuda")
        self.assertEqual(resolve_device("cpu"), "cpu")

    def test_resolve_device_env(self):
        with patch.dict(os.environ, {"STEMS_DEVICE": "cuda"}):
            self.assertEqual(resolve_device(None), "cuda")

    @patch('torch.cuda.is_available', return_value=True)
    def test_resolve_device_auto_cuda(self, mock_cuda):
        with patch.dict(os.environ, {"STEMS_DEVICE": ""}):
            self.assertEqual(resolve_device(None), "cuda")

    @patch('torch.cuda.is_available', return_value=False)
    def test_resolve_device_auto_mps(self, mock_cuda):
        mock_mps = MagicMock()
        mock_mps.is_available.return_value = True
        with patch.dict(os.environ, {"STEMS_DEVICE": ""}):
            with patch('torch.backends.mps', mock_mps, create=True):
                self.assertEqual(resolve_device(None), "mps")

    @patch('torch.cuda.is_available', return_value=False)
    def test_resolve_device_auto_cpu_fallback(self, mock_cuda):
        mock_mps = MagicMock()
        mock_mps.is_available.return_value = False
        with patch.dict(os.environ, {"STEMS_DEVICE": ""}):
            with patch('torch.backends.mps', mock_mps, create=True):
                self.assertEqual(resolve_device(None), "cpu")

    def test_resolve_song(self):
        # From Song dataclass directly
        song = Song(title="Amazing Grace", key="E", date="2026-09-06")
        self.assertEqual(resolve_song(song), song)

        # From standardized filename string
        resolved = resolve_song("Amazing Grace - E - 2026-09-06.wav")
        self.assertEqual(resolved.title, "Amazing Grace")
        self.assertEqual(resolved.key, "E")
        self.assertEqual(resolved.date, "2026-09-06")

        # From parenthetical key filename
        resolved_paren = resolve_song("Yet Not I But Through Christ In Me (D) - 2026-08-02.wav")
        self.assertEqual(resolved_paren.title, "Yet Not I But Through Christ In Me")
        self.assertEqual(resolved_paren.key, "D")
        self.assertEqual(resolved_paren.date, "2026-08-02")

        # From plain name string
        resolved_plain = resolve_song("Custom Track.wav")
        self.assertEqual(resolved_plain.title, "Custom Track")

    def test_check_stem_exists(self):
        out_path = Path(self.dest_dir)
        song_name = "Test Song"
        
        # Initially doesn't exist
        self.assertFalse(check_stem_exists(out_path, song_name, "drums"))
        self.assertFalse(check_stem_exists(out_path, song_name, "vocal"))

        # Create drums stem
        (out_path / f"{song_name} - drums.wav").touch()
        self.assertTrue(check_stem_exists(out_path, song_name, "drums"))

        # Create vocal stem as 'vocals.wav' and check both 'vocal' and 'vocals'
        (out_path / f"{song_name} - vocals.wav").touch()
        self.assertTrue(check_stem_exists(out_path, song_name, "vocal"))
        self.assertTrue(check_stem_exists(out_path, song_name, "vocals"))

        # Check with Song object directly
        song_obj = Song(title="Test Song")
        self.assertTrue(check_stem_exists(out_path, song_obj, "drums"))
        self.assertTrue(check_stem_exists(out_path, song_obj, "vocal"))

        # Check with filename containing key and date
        song_with_key = Song(title="Amazing Grace", key="E", date="2026-09-06")
        self.assertFalse(check_stem_exists(out_path, song_with_key, "bass"))
        (out_path / "Amazing Grace - E - 2026-09-06 - bass.wav").touch()
        self.assertTrue(check_stem_exists(out_path, song_with_key, "bass"))
        self.assertTrue(check_stem_exists(out_path, "Amazing Grace - E - 2026-09-06.wav", "bass"))

    @patch('torchaudio.save')
    @patch('demucs.api.Separator')
    def test_generate_composite_stems_for_file_success(self, mock_separator_cls, mock_audio_save):
        mock_ft_sep = MagicMock()
        mock_ft_sep.samplerate = 44100
        mock_ft_sep.separate_audio_file.return_value = (
            None,
            {
                "vocals": "tensor_vocals",
                "drums": "tensor_drums",
                "bass": "tensor_bass",
                "other": "tensor_other_ft",
            }
        )

        mock_6s_sep = MagicMock()
        mock_6s_sep.samplerate = 44100
        mock_6s_sep.separate_audio_file.return_value = (
            None,
            {
                "vocals": "tensor_vocals_discarded",
                "drums": "tensor_drums_discarded",
                "bass": "tensor_bass_discarded",
                "guitar": "tensor_guitar",
                "piano": "tensor_piano",
                "other": "tensor_other",
            }
        )

        def separator_factory(model, device):
            if model == "htdemucs_ft":
                return mock_ft_sep
            elif model == "htdemucs_6s":
                return mock_6s_sep
            raise ValueError(f"Unknown model {model}")

        mock_separator_cls.side_effect = separator_factory

        input_wav = os.path.join(self.src_dir, "Amazing Grace - E - 2026-09-06.wav")
        Path(input_wav).touch()

        out_dir = generate_composite_stems_for_file(
            input_file=input_wav,
            output_base_dir=self.dest_dir,
            device="mps"
        )

        expected_folder = Path(self.dest_dir) / "Amazing Grace - E - 2026-09-06 - Stems"
        self.assertEqual(out_dir, expected_folder)
        self.assertTrue(expected_folder.is_dir())

        # Check Separator instantiations
        self.assertEqual(mock_separator_cls.call_count, 2)
        mock_separator_cls.assert_any_call(model="htdemucs_ft", device="mps")
        mock_separator_cls.assert_any_call(model="htdemucs_6s", device="mps")

        # Check that torchaudio.save was called for all 7 stems
        # Expected stem files: vocal, drums, bass, other_ft, guitar, piano, other
        self.assertEqual(mock_audio_save.call_count, 7)
        saved_paths = [call_args[0][0] for call_args in mock_audio_save.call_args_list]

        song_base = "Amazing Grace - E - 2026-09-06"
        for stem in ["vocal", "drums", "bass", "other_ft", "guitar", "piano", "other"]:
            expected_file = str(expected_folder / f"{song_base} - {stem}.wav")
            self.assertIn(expected_file, saved_paths)

    @patch('torchaudio.save')
    @patch('demucs.api.Separator')
    def test_generate_composite_stems_for_file_with_parenthetical_key_normalization(self, mock_separator_cls, mock_audio_save):
        mock_ft = MagicMock()
        mock_ft.samplerate = 44100
        mock_ft.separate_audio_file.return_value = (None, {"vocals": "v", "drums": "d", "bass": "b", "other": "o_ft"})
        mock_6s = MagicMock()
        mock_6s.samplerate = 44100
        mock_6s.separate_audio_file.return_value = (None, {"guitar": "g", "piano": "p", "other": "o"})

        mock_separator_cls.side_effect = lambda model, device: mock_ft if model == "htdemucs_ft" else mock_6s

        # Input with parenthetical key in filename
        input_wav = os.path.join(self.src_dir, "Yet Not I But Through Christ In Me (D) - 2026-08-02.wav")
        Path(input_wav).touch()

        out_dir = generate_composite_stems_for_file(
            input_file=input_wav,
            output_base_dir=self.dest_dir,
        )

        expected_folder = Path(self.dest_dir) / "Yet Not I But Through Christ In Me - D - 2026-08-02 - Stems"
        self.assertEqual(out_dir, expected_folder)
        self.assertTrue(expected_folder.is_dir())

        saved_paths = [call_args[0][0] for call_args in mock_audio_save.call_args_list]
        expected_stem = str(expected_folder / "Yet Not I But Through Christ In Me - D - 2026-08-02 - vocal.wav")
        self.assertIn(expected_stem, saved_paths)

    @patch('demucs.api.Separator')
    def test_generate_composite_stems_skips_when_all_stems_exist(self, mock_separator_cls):
        song_base = "Build My Life - 2026-09-13"
        input_wav = os.path.join(self.src_dir, f"{song_base}.wav")
        Path(input_wav).touch()

        stem_dir = Path(self.dest_dir) / f"{song_base} - Stems"
        stem_dir.mkdir(parents=True, exist_ok=True)
        for stem in ALL_COMPOSITE_STEMS:
            (stem_dir / f"{song_base} - {stem}.wav").touch()

        out_dir = generate_composite_stems_for_file(
            input_file=input_wav,
            output_base_dir=self.dest_dir,
            overwrite=False
        )

        self.assertEqual(out_dir, stem_dir)
        mock_separator_cls.assert_not_called()

    @patch('torchaudio.save')
    @patch('demucs.api.Separator')
    def test_generate_composite_stems_overwrite_flag(self, mock_separator_cls, mock_save):
        mock_ft_sep = MagicMock()
        mock_ft_sep.samplerate = 44100
        mock_ft_sep.separate_audio_file.return_value = (None, {"vocals": "v", "drums": "d", "bass": "b", "other": "o_ft"})
        mock_6s_sep = MagicMock()
        mock_6s_sep.samplerate = 44100
        mock_6s_sep.separate_audio_file.return_value = (None, {"guitar": "g", "piano": "p", "other": "o"})

        def separator_factory(model, device):
            return mock_ft_sep if model == "htdemucs_ft" else mock_6s_sep

        mock_separator_cls.side_effect = separator_factory

        song_base = "Build My Life - 2026-09-13"
        input_wav = os.path.join(self.src_dir, f"{song_base}.wav")
        Path(input_wav).touch()

        stem_dir = Path(self.dest_dir) / f"{song_base} - Stems"
        stem_dir.mkdir(parents=True, exist_ok=True)
        for stem in ALL_COMPOSITE_STEMS:
            (stem_dir / f"{song_base} - {stem}.wav").touch()

        # Run with overwrite=True
        generate_composite_stems_for_file(
            input_file=input_wav,
            output_base_dir=self.dest_dir,
            overwrite=True
        )

        self.assertEqual(mock_separator_cls.call_count, 2)
        self.assertEqual(mock_save.call_count, 7)

    def test_make_composite_stems_source_dir_not_found(self):
        res = make_composite_stems(
            src_dir="/non/existent/path/for/stems",
            dest_dir=self.dest_dir
        )
        self.assertEqual(res, [])

    def test_make_composite_stems_missing_numpy_dependency(self):
        orig_import = __import__

        def custom_import(name, *args, **kwargs):
            if name.startswith("demucs"):
                raise ImportError("No module named 'numpy'")
            return orig_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=custom_import):
            with patch('builtins.print') as mock_print:
                res = make_composite_stems(src_dir=self.src_dir, dest_dir=self.dest_dir)
                self.assertEqual(res, [])
                printed = " ".join(str(call_args[0][0]) for call_args in mock_print.call_args_list if call_args[0])
                self.assertIn("No module named 'numpy'", printed)
                self.assertIn("pip install demucs torchaudio torch numpy torchcodec", printed)

    def test_generate_composite_stems_for_file_missing_numpy_dependency(self):
        orig_import = __import__

        def custom_import(name, *args, **kwargs):
            if name.startswith("demucs"):
                raise ImportError("No module named 'numpy'")
            return orig_import(name, *args, **kwargs)

        input_wav = os.path.join(self.src_dir, "Song.wav")
        Path(input_wav).touch()

        with patch('builtins.__import__', side_effect=custom_import):
            with self.assertRaises(ImportError) as ctx:
                generate_composite_stems_for_file(input_file=input_wav, output_base_dir=self.dest_dir)
            self.assertIn("No module named 'numpy'", str(ctx.exception))
            self.assertIn("numpy", str(ctx.exception))
            self.assertIn("torchcodec", str(ctx.exception))

    @patch('torchaudio.save')
    def test_save_audio_stem_success(self, mock_torchaudio_save):
        out_file = Path(self.dest_dir) / "test.wav"
        mock_tensor = MagicMock()
        save_audio_stem(out_file, mock_tensor, sample_rate=44100)
        # Natively calls torchaudio.save without unsupported encoding/bits_per_sample kwargs
        mock_torchaudio_save.assert_called_once_with(
            str(out_file),
            mock_tensor,
            44100,
        )

    @patch('torchaudio.save')
    def test_save_audio_stem_torchcodec_fallback_failure_raises_clear_error(self, mock_torchaudio_save):
        out_file = Path(self.dest_dir) / "test_torchcodec.wav"
        mock_tensor = MagicMock()
        mock_torchaudio_save.side_effect = RuntimeError(
            "TorchCodec is required for save_with_torchcodec. Please install torchcodec to use this function."
        )

        with self.assertRaises(RuntimeError) as ctx:
            save_audio_stem(out_file, mock_tensor, sample_rate=44100)
        self.assertIn("TorchCodec is required", str(ctx.exception))
        self.assertIn("pip install torchcodec", str(ctx.exception))

    @patch('torchaudio.save')
    def test_save_audio_stem_generic_error_re_raised(self, mock_torchaudio_save):
        out_file = Path(self.dest_dir) / "test_ioerr.wav"
        mock_tensor = MagicMock()
        mock_torchaudio_save.side_effect = OSError("Disk full")

        with self.assertRaises(OSError) as ctx:
            save_audio_stem(out_file, mock_tensor, sample_rate=44100)
        self.assertIn("Disk full", str(ctx.exception))

    @patch('torchaudio.save')
    def test_save_audio_stem_native_call_no_unsupported_kwargs(self, mock_torchaudio_save):
        out_file = Path(self.dest_dir) / "test_native.wav"
        mock_tensor = MagicMock()

        save_audio_stem(out_file, mock_tensor, sample_rate=44100)

        # Confirm torchaudio.save was invoked natively with no unsupported kwargs
        mock_torchaudio_save.assert_called_once_with(str(out_file), mock_tensor, 44100)
        _, call_kwargs = mock_torchaudio_save.call_args
        self.assertNotIn("encoding", call_kwargs)
        self.assertNotIn("bits_per_sample", call_kwargs)

    def test_make_composite_stems_no_wav_files(self):
        res = make_composite_stems(
            src_dir=self.src_dir,
            dest_dir=self.dest_dir
        )
        self.assertEqual(res, [])

    @patch('post_processing.make_composite_stems.generate_composite_stems_for_file')
    def test_make_composite_stems_date_filtering(self, mock_gen):
        mock_gen.side_effect = lambda input_file, output_base_dir, **kw: Path(output_base_dir) / f"{Path(input_file).stem} - Stems"

        # Create files for two different dates
        Path(os.path.join(self.src_dir, "Song A - 2026-09-06.wav")).touch()
        Path(os.path.join(self.src_dir, "Song B - 2026-09-13.wav")).touch()

        # Filter by single date
        res = make_composite_stems(
            src_dir=self.src_dir,
            dest_dir=self.dest_dir,
            target_date="2026-09-06"
        )
        self.assertEqual(len(res), 1)
        self.assertIn("Song A - 2026-09-06 - Stems", res[0])
        mock_gen.assert_called_once()
        self.assertIn("Song A - 2026-09-06.wav", mock_gen.call_args[1]["input_file"])

        mock_gen.reset_mock()

        # Filter by date range
        res_range = make_composite_stems(
            src_dir=self.src_dir,
            dest_dir=self.dest_dir,
            start_date="2026-09-01",
            end_date="2026-09-20"
        )
        self.assertEqual(len(res_range), 2)
        self.assertEqual(mock_gen.call_count, 2)

        mock_gen.reset_mock()

        # Filter with no match
        res_none = make_composite_stems(
            src_dir=self.src_dir,
            dest_dir=self.dest_dir,
            target_date="2026-01-01"
        )
        self.assertEqual(res_none, [])
        mock_gen.assert_not_called()

    @patch('post_processing.make_composite_stems.make_composite_stems')
    def test_cli_main_args(self, mock_make_stems):
        cli_args = [
            "--src-dir", self.src_dir,
            "--dest-dir", self.dest_dir,
            "--date", "2026-09-06",
            "--device", "mps",
            "--overwrite"
        ]
        main(cli_args)
        mock_make_stems.assert_called_once_with(
            src_dir=self.src_dir,
            dest_dir=self.dest_dir,
            device="mps",
            target_date="2026-09-06",
            start_date=None,
            end_date=None,
            overwrite=True
        )

    @patch('sys.exit')
    def test_cli_main_conflicting_dates(self, mock_exit):
        cli_args = [
            "--date", "2026-09-06",
            "--start-date", "2026-09-01",
            "--end-date", "2026-09-30"
        ]
        main(cli_args)
        mock_exit.assert_called_once_with(1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
