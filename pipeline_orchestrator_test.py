import unittest
from unittest.mock import patch, MagicMock
import sys
import pipeline_orchestrator

class TestPipelineOrchestrator(unittest.TestCase):
    
    @patch('pipeline_orchestrator.fetch_service_types')
    @patch('pipeline_orchestrator.input')
    def test_prompt_for_service_type(self, mock_input, mock_fetch_service_types):
        mock_st = MagicMock()
        mock_st.id = "123"
        mock_st.name = "Sunday Morning"
        mock_fetch_service_types.return_value = [mock_st]
        
        mock_input.return_value = "1"
        
        result = pipeline_orchestrator.prompt_for_service_type()
        
        self.assertEqual(result, "123")
        mock_input.assert_called_once()
        
    @patch('pipeline_orchestrator.fetch_recent_plans')
    @patch('pipeline_orchestrator.input')
    def test_prompt_for_plan(self, mock_input, mock_fetch_recent_plans):
        mock_plan = MagicMock()
        mock_plan.id = "456"
        mock_plan.dates = "September 6, 2026"
        mock_plan.title = "Vision Sunday"
        mock_fetch_recent_plans.return_value = [mock_plan]
        
        mock_input.return_value = "1"
        
        result = pipeline_orchestrator.prompt_for_plan("123")
        
        self.assertEqual(result, ("456", "2026-09-06"))
        mock_input.assert_called_once()

    @patch('pipeline_orchestrator.prompt_for_service_type')
    @patch('pipeline_orchestrator.prompt_for_plan')
    @patch('pipeline_orchestrator.fetch_service_plan')
    @patch('pipeline_orchestrator.discover_raw_audio')
    @patch('pipeline_orchestrator.segment_service_audio')
    @patch('pipeline_orchestrator.copy_songs')
    @patch('pipeline_orchestrator.move_songs')
    @patch('pipeline_orchestrator.make_videos')
    @patch('pipeline_orchestrator.input')
    def test_main_pipeline_default_zero_args(self, mock_input, mock_make_videos, mock_move_songs, mock_copy_songs, mock_segment, mock_discover, mock_fetch_plan, mock_prompt_plan, mock_prompt_st):
        """When args length is zero (e.g. running python3 pipeline_orchestrator.py), it runs segmentation AND post-processing by default."""
        mock_prompt_st.return_value = "123"
        mock_prompt_plan.return_value = ("456", "2026-09-06")
        
        mock_plan_obj = MagicMock()
        mock_fetch_plan.return_value = mock_plan_obj
        mock_discover.return_value = ["/path/to/R_20260906-103109.wav"]
        mock_input.return_value = "y"
        
        pipeline_orchestrator.main([])
        
        mock_prompt_st.assert_called_once()
        mock_prompt_plan.assert_called_once_with("123")
        mock_fetch_plan.assert_called_once_with("123", "456", "2026-09-06")
        mock_discover.assert_called_once()
        mock_segment.assert_called_once_with(mock_plan_obj)
        mock_copy_songs.assert_called_once()
        mock_move_songs.assert_called_once()
        mock_make_videos.assert_called_once()

    @patch('pipeline_orchestrator.fetch_service_plan')
    @patch('pipeline_orchestrator.discover_raw_audio')
    @patch('pipeline_orchestrator.segment_service_audio')
    @patch('pipeline_orchestrator.copy_songs')
    @patch('pipeline_orchestrator.move_songs')
    @patch('pipeline_orchestrator.make_videos')
    def test_main_pipeline_execution_with_flags(self, mock_make_videos, mock_move_songs, mock_copy_songs, mock_segment, mock_discover, mock_fetch_plan):
        """When specific flags are provided (e.g. --plan-id and --date), post-processing is not run unless explicitly requested."""
        mock_plan_obj = MagicMock()
        mock_fetch_plan.return_value = mock_plan_obj
        mock_discover.return_value = ["/path/to/R_20260906-103109.wav"]
        
        pipeline_orchestrator.main(["--service-type", "123", "--plan-id", "456", "--date", "2026-09-06"])
        
        mock_fetch_plan.assert_called_once_with("123", "456", "2026-09-06")
        mock_discover.assert_called_once()
        mock_segment.assert_called_once_with(mock_plan_obj)
        mock_copy_songs.assert_not_called()
        mock_move_songs.assert_not_called()
        mock_make_videos.assert_not_called()

    @patch('pipeline_orchestrator.prompt_for_service_type')
    @patch('pipeline_orchestrator.prompt_for_plan')
    @patch('pipeline_orchestrator.fetch_service_plan')
    @patch('pipeline_orchestrator.discover_raw_audio')
    @patch('pipeline_orchestrator.segment_service_audio')
    @patch('pipeline_orchestrator.copy_songs')
    @patch('pipeline_orchestrator.move_songs')
    @patch('pipeline_orchestrator.make_videos')
    def test_main_pipeline_skip_post_processing(self, mock_make_videos, mock_move_songs, mock_copy_songs, mock_segment, mock_discover, mock_fetch_plan, mock_prompt_plan, mock_prompt_st):
        """When --skip-post-processing flag is passed, post-processing is omitted."""
        mock_prompt_st.return_value = "123"
        mock_prompt_plan.return_value = ("456", "2026-09-06")
        mock_plan_obj = MagicMock()
        mock_fetch_plan.return_value = mock_plan_obj
        mock_discover.return_value = ["/path/to/R_20260906-103109.wav"]

        pipeline_orchestrator.main(["--skip-post-processing"])

        mock_segment.assert_called_once_with(mock_plan_obj)
        mock_copy_songs.assert_not_called()
        mock_move_songs.assert_not_called()
        mock_make_videos.assert_not_called()

    @patch('pipeline_orchestrator.copy_songs')
    @patch('pipeline_orchestrator.move_songs')
    @patch('pipeline_orchestrator.make_videos')
    @patch('pipeline_orchestrator.input')
    @patch('pipeline_orchestrator.prompt_for_plan')
    def test_main_post_processing(self, mock_prompt_plan, mock_input, mock_make_videos, mock_move_songs, mock_copy_songs):
        mock_input.return_value = "y"
        
        pipeline_orchestrator.main(["--service-type", "123", "--publish-staging", "--publish-verified", "--make-videos"])
        
        mock_prompt_plan.assert_not_called()
        mock_copy_songs.assert_called_once()
        mock_move_songs.assert_called_once()
        mock_make_videos.assert_called_once()

    @patch('pipeline_orchestrator.copy_songs')
    @patch('pipeline_orchestrator.move_songs')
    @patch('pipeline_orchestrator.make_videos')
    @patch('pipeline_orchestrator.prompt_for_plan')
    def test_main_post_processing_staging_only(self, mock_prompt_plan, mock_make_videos, mock_move_songs, mock_copy_songs):
        """When --publish-staging is passed alone, only copy_songs is called and verified move is skipped."""
        pipeline_orchestrator.main(["--service-type", "123", "--publish-staging"])
        
        mock_prompt_plan.assert_not_called()
        mock_copy_songs.assert_called_once()
        mock_move_songs.assert_not_called()
        mock_make_videos.assert_not_called()

    @patch('pipeline_orchestrator.copy_songs')
    @patch('pipeline_orchestrator.move_songs')
    @patch('pipeline_orchestrator.make_videos')
    @patch('pipeline_orchestrator.input')
    @patch('pipeline_orchestrator.prompt_for_plan')
    def test_main_post_processing_publish_verified_only(self, mock_prompt_plan, mock_input, mock_make_videos, mock_move_songs, mock_copy_songs):
        """When --publish-verified is passed alone, copy_songs is skipped and only verified move is performed upon confirmation."""
        mock_input.return_value = "y"
        
        pipeline_orchestrator.main(["--service-type", "123", "--publish-verified"])
        
        mock_prompt_plan.assert_not_called()
        mock_copy_songs.assert_not_called()
        mock_move_songs.assert_called_once()
        mock_make_videos.assert_not_called()

    @patch('pipeline_orchestrator.copy_songs')
    @patch('pipeline_orchestrator.move_songs')
    @patch('pipeline_orchestrator.make_videos')
    @patch('pipeline_orchestrator.input')
    @patch('pipeline_orchestrator.prompt_for_plan')
    def test_main_post_processing_declined_verification(self, mock_prompt_plan, mock_input, mock_make_videos, mock_move_songs, mock_copy_songs):
        """When the user does not enter 'y' to verify songs, move_songs and make_videos must not be executed."""
        mock_input.return_value = "n"
        
        pipeline_orchestrator.main(["--service-type", "123", "--publish-staging", "--publish-verified", "--make-videos"])
        
        mock_prompt_plan.assert_not_called()
        mock_copy_songs.assert_called_once()
        mock_move_songs.assert_not_called()
        mock_make_videos.assert_not_called()

    @patch('pipeline_orchestrator.fetch_service_plan')
    @patch('pipeline_orchestrator.discover_raw_audio')
    @patch('pipeline_orchestrator.segment_service_audio')
    def test_main_pipeline_missing_raw_audio_dir(self, mock_segment, mock_discover, mock_fetch_plan):
        mock_fetch_plan.return_value = MagicMock()
        mock_discover.side_effect = FileNotFoundError("Raw audio directory does not exist")

        pipeline_orchestrator.main(["--service-type", "123", "--plan-id", "456", "--date", "2026-09-06"])

        mock_discover.assert_called_once()
        mock_segment.assert_not_called()

    @patch('pipeline_orchestrator.fetch_service_plan')
    @patch('pipeline_orchestrator.discover_raw_audio')
    @patch('pipeline_orchestrator.segment_service_audio')
    def test_main_pipeline_no_matching_audio_files(self, mock_segment, mock_discover, mock_fetch_plan):
        mock_fetch_plan.return_value = MagicMock()
        mock_discover.return_value = []

        pipeline_orchestrator.main(["--service-type", "123", "--plan-id", "456", "--date", "2026-09-06"])

        mock_discover.assert_called_once()
        mock_segment.assert_not_called()

    @patch('pipeline_orchestrator.prompt_for_service_type')
    @patch('pipeline_orchestrator.prompt_for_plan')
    @patch('pipeline_orchestrator.fetch_service_plan')
    @patch('pipeline_orchestrator.discover_raw_audio')
    @patch('pipeline_orchestrator.segment_service_audio')
    @patch('pipeline_orchestrator.copy_songs')
    @patch('pipeline_orchestrator.move_songs')
    @patch('pipeline_orchestrator.make_videos')
    def test_main_pipeline_file_exists_error_exits_before_post_processing(self, mock_make_videos, mock_move_songs, mock_copy_songs, mock_segment, mock_discover, mock_fetch_plan, mock_prompt_plan, mock_prompt_st):
        """When segmentation raises FileExistsError, pipeline exits early to avoid publishing verified songs."""
        mock_prompt_st.return_value = "123"
        mock_prompt_plan.return_value = ("456", "2026-09-06")
        mock_fetch_plan.return_value = MagicMock()
        mock_discover.return_value = ["/path/to/R_20260906-103109.wav"]
        mock_segment.side_effect = FileExistsError("Output directory already exists")

        pipeline_orchestrator.main([])

        mock_segment.assert_called_once()
        mock_copy_songs.assert_not_called()
        mock_move_songs.assert_not_called()
        mock_make_videos.assert_not_called()

if __name__ == '__main__':
    unittest.main(verbosity=2)
