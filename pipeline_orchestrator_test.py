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

    @patch('pipeline_orchestrator.argparse.ArgumentParser.parse_args')
    @patch('pipeline_orchestrator.prompt_for_service_type')
    @patch('pipeline_orchestrator.prompt_for_plan')
    @patch('pipeline_orchestrator.fetch_service_plan')
    @patch('pipeline_orchestrator.discover_raw_audio')
    @patch('pipeline_orchestrator.segment_service_audio')
    def test_main_pipeline_execution(self, mock_segment, mock_discover, mock_fetch_plan, mock_prompt_plan, mock_prompt_st, mock_parse_args):
        mock_args = MagicMock()
        mock_args.service_type = None
        mock_args.plan_id = None
        mock_args.date = None
        mock_args.audio_file = None
        mock_args.publish_verified = False
        mock_args.make_videos = False
        mock_parse_args.return_value = mock_args
        
        mock_prompt_st.return_value = "123"
        mock_prompt_plan.return_value = ("456", "2026-09-06")
        
        mock_plan_obj = MagicMock()
        mock_fetch_plan.return_value = mock_plan_obj
        
        mock_discover.return_value = ["/path/to/R_20260906-103109.wav"]
        
        pipeline_orchestrator.main()
        
        mock_prompt_st.assert_called_once()
        mock_prompt_plan.assert_called_once_with("123")
        mock_fetch_plan.assert_called_once_with("123", "456", "2026-09-06")
        mock_discover.assert_called_once()
        mock_segment.assert_called_once_with(mock_plan_obj)
        
    @patch('pipeline_orchestrator.argparse.ArgumentParser.parse_args')
    @patch('pipeline_orchestrator.copy_songs')
    @patch('pipeline_orchestrator.move_songs')
    @patch('pipeline_orchestrator.make_videos')
    @patch('pipeline_orchestrator.input')
    def test_main_post_processing(self, mock_input, mock_make_videos, mock_move_songs, mock_copy_songs, mock_parse_args):
        mock_args = MagicMock()
        mock_args.service_type = "123"
        mock_args.plan_id = None
        mock_args.date = None
        mock_args.audio_file = None
        mock_args.publish_verified = True
        mock_args.make_videos = True
        mock_parse_args.return_value = mock_args
        
        mock_input.return_value = "y"
        
        pipeline_orchestrator.main()
        
        mock_copy_songs.assert_called_once()
        mock_move_songs.assert_called_once()
        mock_make_videos.assert_called_once()

    @patch('pipeline_orchestrator.argparse.ArgumentParser.parse_args')
    @patch('pipeline_orchestrator.prompt_for_service_type')
    @patch('pipeline_orchestrator.prompt_for_plan')
    @patch('pipeline_orchestrator.fetch_service_plan')
    @patch('pipeline_orchestrator.discover_raw_audio')
    @patch('pipeline_orchestrator.segment_service_audio')
    def test_main_pipeline_missing_raw_audio_dir(self, mock_segment, mock_discover, mock_fetch_plan, mock_prompt_plan, mock_prompt_st, mock_parse_args):
        mock_args = MagicMock()
        mock_args.service_type = "123"
        mock_args.plan_id = "456"
        mock_args.date = "2026-09-06"
        mock_args.audio_file = None
        mock_args.publish_verified = False
        mock_args.make_videos = False
        mock_parse_args.return_value = mock_args

        mock_fetch_plan.return_value = MagicMock()
        mock_discover.side_effect = FileNotFoundError("Raw audio directory does not exist")

        pipeline_orchestrator.main()

        mock_discover.assert_called_once()
        mock_segment.assert_not_called()

    @patch('pipeline_orchestrator.argparse.ArgumentParser.parse_args')
    @patch('pipeline_orchestrator.prompt_for_service_type')
    @patch('pipeline_orchestrator.prompt_for_plan')
    @patch('pipeline_orchestrator.fetch_service_plan')
    @patch('pipeline_orchestrator.discover_raw_audio')
    @patch('pipeline_orchestrator.segment_service_audio')
    def test_main_pipeline_no_matching_audio_files(self, mock_segment, mock_discover, mock_fetch_plan, mock_prompt_plan, mock_prompt_st, mock_parse_args):
        mock_args = MagicMock()
        mock_args.service_type = "123"
        mock_args.plan_id = "456"
        mock_args.date = "2026-09-06"
        mock_args.audio_file = None
        mock_args.publish_verified = False
        mock_args.make_videos = False
        mock_parse_args.return_value = mock_args

        mock_fetch_plan.return_value = MagicMock()
        mock_discover.return_value = []

        pipeline_orchestrator.main()

        mock_discover.assert_called_once()
        mock_segment.assert_not_called()

if __name__ == '__main__':
    unittest.main(verbosity=2)
