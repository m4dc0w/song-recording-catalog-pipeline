import os
import tempfile
import unittest
import wave
from unittest.mock import patch, MagicMock
from post_processing.make_videos import make_videos

class TestMakeVideos(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.src_dir = os.path.join(self.temp_dir.name, "src")
        self.dest_dir = os.path.join(self.temp_dir.name, "dest")
        os.makedirs(self.src_dir)
        os.makedirs(self.dest_dir)
        
        self.bg_image = os.path.join(self.temp_dir.name, "bg.png")
        with open(self.bg_image, 'w') as f:
            f.write("dummy image")

    def tearDown(self):
        self.temp_dir.cleanup()
        
    def create_dummy_wav(self, path):
        with wave.open(path, 'w') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b'\x00\x00' * 44100)

    @patch('subprocess.run')
    def test_make_videos_success(self, mock_subprocess):
        mock_result = MagicMock()
        mock_result.stderr = 'some log text { "input_i": "-20.0", "input_tp": "-2.0", "input_lra": "5.0", "input_thresh": "-30.0", "target_offset": "0.5" } end log'
        mock_subprocess.return_value = mock_result
        
        self.create_dummy_wav(os.path.join(self.src_dir, "Test - Song.wav"))
        make_videos(self.src_dir, self.dest_dir, bg_image_path=self.bg_image, ffmpeg_path="ffmpeg")
        
        self.assertEqual(mock_subprocess.call_count, 2)
        pass2_call = mock_subprocess.call_args_list[1][0][0]
        pass2_cmd_str = " ".join(pass2_call)
        self.assertIn("Test - Song.wav", pass2_cmd_str)
        self.assertIn("fontsize=48", pass2_cmd_str)

    @patch('subprocess.run')
    def test_make_videos_wraps_long_titles(self, mock_subprocess):
        mock_result = MagicMock()
        mock_result.stderr = 'some log text { "input_i": "-20.0", "input_tp": "-2.0", "input_lra": "5.0", "input_thresh": "-30.0", "target_offset": "0.5" } end log'
        mock_subprocess.return_value = mock_result
        
        long_name = "01 - All Hail King Jesus (Live at Passion 2020 Acoustic Session).wav"
        self.create_dummy_wav(os.path.join(self.src_dir, long_name))
        
        # Capture text written to temporary text files
        written_texts = []
        original_tempfile = tempfile.NamedTemporaryFile
        def mock_named_tempfile(*args, **kwargs):
            tf = original_tempfile(*args, **kwargs)
            orig_write = tf.write
            def capturing_write(data):
                written_texts.append(data)
                return orig_write(data)
            tf.write = capturing_write
            return tf

        with patch('post_processing.make_videos.tempfile.NamedTemporaryFile', side_effect=mock_named_tempfile):
            make_videos(self.src_dir, self.dest_dir, bg_image_path=self.bg_image, ffmpeg_path="ffmpeg")

        self.assertTrue(len(written_texts) > 0)
        # Check that the long subtitle was wrapped across multiple lines
        self.assertIn("\n", written_texts[0])
        # Check that individual lines do not exceed the wrapping width
        for line in written_texts[0].split("\n"):
            self.assertLessEqual(len(line), 35)

    def test_make_videos_skips_existing(self):
        self.create_dummy_wav(os.path.join(self.src_dir, "ExistingSong.wav"))
        
        with open(os.path.join(self.dest_dir, "ExistingSong.mp4"), 'w') as f:
            f.write("dummy video")
            
        with patch('subprocess.run') as mock_subprocess:
            make_videos(self.src_dir, self.dest_dir, bg_image_path=self.bg_image)
            mock_subprocess.assert_not_called()

if __name__ == '__main__':
    unittest.main()
