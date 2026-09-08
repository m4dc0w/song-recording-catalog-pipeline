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
        # Option 3 (all dates) for staging date prompt, "y" for move_songs verification
        mock_input.side_effect = ["3", "y"]
        
        pipeline_orchestrator.main(["--service-type", "123", "--publish-staging", "--publish-verified", "--make-videos"])
        
        mock_prompt_plan.assert_not_called()
        mock_copy_songs.assert_called_once()
        mock_move_songs.assert_called_once()
        mock_make_videos.assert_called_once()

    @patch('pipeline_orchestrator.copy_songs')
    @patch('pipeline_orchestrator.move_songs')
    @patch('pipeline_orchestrator.make_videos')
    @patch('pipeline_orchestrator.prompt_for_plan')
    def test_main_post_processing_staging_only_with_all_flag(self, mock_prompt_plan, mock_make_videos, mock_move_songs, mock_copy_songs):
        """When --publish-staging is passed with --all, date prompting is bypassed and all songs are staged."""
        pipeline_orchestrator.main(["--service-type", "123", "--publish-staging", "--all"])
        
        mock_prompt_plan.assert_not_called()
        mock_copy_songs.assert_called_once()
        kwargs = mock_copy_songs.call_args[1]
        self.assertIsNone(kwargs.get("target_date"))
        self.assertIsNone(kwargs.get("start_date"))
        self.assertIsNone(kwargs.get("end_date"))
        mock_move_songs.assert_not_called()
        mock_make_videos.assert_not_called()

    @patch('pipeline_orchestrator.copy_songs')
    @patch('pipeline_orchestrator.move_songs')
    @patch('pipeline_orchestrator.make_videos')
    @patch('pipeline_orchestrator.input')
    @patch('pipeline_orchestrator.prompt_for_plan')
    def test_main_post_processing_staging_only_prompts_for_date(self, mock_prompt_plan, mock_input, mock_make_videos, mock_move_songs, mock_copy_songs):
        """When --publish-staging is passed without date flags, it defaults to prompting for the dates."""
        mock_input.side_effect = ["1", "2026-09-06"]
        pipeline_orchestrator.main(["--service-type", "123", "--publish-staging"])
        
        mock_prompt_plan.assert_not_called()
        mock_copy_songs.assert_called_once()
        kwargs = mock_copy_songs.call_args[1]
        self.assertEqual(kwargs.get("target_date"), "2026-09-06")
        self.assertIsNone(kwargs.get("start_date"))
        self.assertIsNone(kwargs.get("end_date"))
        mock_move_songs.assert_not_called()
        mock_make_videos.assert_not_called()

    @patch('pipeline_orchestrator.copy_songs')
    @patch('pipeline_orchestrator.move_songs')
    @patch('pipeline_orchestrator.make_videos')
    @patch('pipeline_orchestrator.input')
    @patch('pipeline_orchestrator.prompt_for_plan')
    def test_main_post_processing_publish_verified_only(self, mock_prompt_plan, mock_input, mock_make_videos, mock_move_songs, mock_copy_songs):
        """When --publish-verified is passed alone without dates, it prompts for dates and moves verified songs upon confirmation."""
        # Date prompt option 1 + date, then verification "y"
        mock_input.side_effect = ["1", "2026-09-06", "y"]
        
        pipeline_orchestrator.main(["--service-type", "123", "--publish-verified"])
        
        mock_prompt_plan.assert_not_called()
        mock_copy_songs.assert_not_called()
        mock_move_songs.assert_called_once()
        kwargs = mock_move_songs.call_args[1]
        self.assertEqual(kwargs.get("target_date"), "2026-09-06")
        self.assertIsNone(kwargs.get("start_date"))
        self.assertIsNone(kwargs.get("end_date"))
        mock_make_videos.assert_not_called()

    @patch('pipeline_orchestrator.copy_songs')
    @patch('pipeline_orchestrator.move_songs')
    @patch('pipeline_orchestrator.make_videos')
    @patch('pipeline_orchestrator.input')
    @patch('pipeline_orchestrator.prompt_for_plan')
    def test_main_post_processing_publish_verified_only_with_all_flag(self, mock_prompt_plan, mock_input, mock_make_videos, mock_move_songs, mock_copy_songs):
        """When --publish-verified is passed with --all, date prompting is bypassed."""
        mock_input.return_value = "y"
        
        pipeline_orchestrator.main(["--service-type", "123", "--publish-verified", "--all"])
        
        mock_prompt_plan.assert_not_called()
        mock_copy_songs.assert_not_called()
        mock_move_songs.assert_called_once()
        kwargs = mock_move_songs.call_args[1]
        self.assertIsNone(kwargs.get("target_date"))
        self.assertIsNone(kwargs.get("start_date"))
        self.assertIsNone(kwargs.get("end_date"))
        mock_make_videos.assert_not_called()

    @patch('pipeline_orchestrator.copy_songs')
    @patch('pipeline_orchestrator.move_songs')
    @patch('pipeline_orchestrator.make_videos')
    @patch('pipeline_orchestrator.input')
    @patch('pipeline_orchestrator.prompt_for_plan')
    def test_main_post_processing_make_videos_only_prompts_for_date(self, mock_prompt_plan, mock_input, mock_make_videos, mock_move_songs, mock_copy_songs):
        """When --make-videos is passed alone without dates, it prompts for dates."""
        mock_input.side_effect = ["1", "2026-09-06"]
        
        pipeline_orchestrator.main(["--service-type", "123", "--make-videos"])
        
        mock_prompt_plan.assert_not_called()
        mock_copy_songs.assert_not_called()
        mock_move_songs.assert_not_called()
        mock_make_videos.assert_called_once()
        kwargs = mock_make_videos.call_args[1]
        self.assertEqual(kwargs.get("target_date"), "2026-09-06")
        self.assertIsNone(kwargs.get("start_date"))
        self.assertIsNone(kwargs.get("end_date"))

    @patch('pipeline_orchestrator.copy_songs')
    @patch('pipeline_orchestrator.move_songs')
    @patch('pipeline_orchestrator.make_videos')
    @patch('pipeline_orchestrator.prompt_for_plan')
    def test_main_post_processing_make_videos_only_with_all_flag(self, mock_prompt_plan, mock_make_videos, mock_move_songs, mock_copy_songs):
        """When --make-videos is passed with --all, date prompting is bypassed."""
        pipeline_orchestrator.main(["--service-type", "123", "--make-videos", "--all"])
        
        mock_prompt_plan.assert_not_called()
        mock_copy_songs.assert_not_called()
        mock_move_songs.assert_not_called()
        mock_make_videos.assert_called_once()
        kwargs = mock_make_videos.call_args[1]
        self.assertIsNone(kwargs.get("target_date"))
        self.assertIsNone(kwargs.get("start_date"))
        self.assertIsNone(kwargs.get("end_date"))

    @patch('pipeline_orchestrator.copy_songs')
    @patch('pipeline_orchestrator.move_songs')
    @patch('pipeline_orchestrator.make_videos')
    @patch('pipeline_orchestrator.input')
    @patch('pipeline_orchestrator.prompt_for_plan')
    def test_main_post_processing_verified_and_videos_prompts_date_once(self, mock_prompt_plan, mock_input, mock_make_videos, mock_move_songs, mock_copy_songs):
        """When --publish-verified and --make-videos are run together without dates, date prompt is only presented once."""
        # 1: Option 1 for date, 2026-09-06: Date string, y: Verification confirmation
        mock_input.side_effect = ["1", "2026-09-06", "y"]

        pipeline_orchestrator.main(["--service-type", "123", "--publish-verified", "--make-videos"])

        mock_prompt_plan.assert_not_called()
        mock_copy_songs.assert_not_called()
        mock_move_songs.assert_called_once()
        self.assertEqual(mock_move_songs.call_args[1].get("target_date"), "2026-09-06")
        mock_make_videos.assert_called_once()
        self.assertEqual(mock_make_videos.call_args[1].get("target_date"), "2026-09-06")

    @patch('pipeline_orchestrator.copy_songs')
    @patch('pipeline_orchestrator.move_songs')
    @patch('pipeline_orchestrator.make_videos')
    @patch('pipeline_orchestrator.input')
    @patch('pipeline_orchestrator.prompt_for_plan')
    def test_main_post_processing_verified_and_videos_with_explicit_date(self, mock_prompt_plan, mock_input, mock_make_videos, mock_move_songs, mock_copy_songs):
        """When explicit --date is passed with post-processing flags, date prompting is completely bypassed."""
        mock_input.return_value = "y"

        pipeline_orchestrator.main(["--service-type", "123", "--date", "2026-09-06", "--publish-verified", "--make-videos"])

        mock_prompt_plan.assert_not_called()
        mock_copy_songs.assert_not_called()
        mock_move_songs.assert_called_once()
        self.assertEqual(mock_move_songs.call_args[1].get("target_date"), "2026-09-06")
        mock_make_videos.assert_called_once()
        self.assertEqual(mock_make_videos.call_args[1].get("target_date"), "2026-09-06")

    @patch('pipeline_orchestrator.copy_songs')
    @patch('pipeline_orchestrator.move_songs')
    @patch('pipeline_orchestrator.make_videos')
    @patch('pipeline_orchestrator.input')
    @patch('pipeline_orchestrator.prompt_for_plan')
    def test_main_post_processing_all_three_steps_prompts_date_once(self, mock_prompt_plan, mock_input, mock_make_videos, mock_move_songs, mock_copy_songs):
        """When --publish-staging, --publish-verified, and --make-videos are run together, date prompt is asked only once."""
        mock_input.side_effect = ["1", "2026-09-06", "y"]

        pipeline_orchestrator.main(["--service-type", "123", "--publish-staging", "--publish-verified", "--make-videos"])

        mock_prompt_plan.assert_not_called()
        mock_copy_songs.assert_called_once()
        self.assertEqual(mock_copy_songs.call_args[1].get("target_date"), "2026-09-06")
        mock_move_songs.assert_called_once()
        self.assertEqual(mock_move_songs.call_args[1].get("target_date"), "2026-09-06")
        mock_make_videos.assert_called_once()
        self.assertEqual(mock_make_videos.call_args[1].get("target_date"), "2026-09-06")

    @patch('pipeline_orchestrator.copy_songs')
    @patch('pipeline_orchestrator.move_songs')
    @patch('pipeline_orchestrator.make_videos')
    @patch('pipeline_orchestrator.input')
    @patch('pipeline_orchestrator.prompt_for_plan')
    def test_main_post_processing_declined_verification(self, mock_prompt_plan, mock_input, mock_make_videos, mock_move_songs, mock_copy_songs):
        """When the user does not enter 'y' to verify songs, move_songs and make_videos must not be executed."""
        # Option 3 for staging date prompt, "n" for verification prompt
        mock_input.side_effect = ["3", "n"]
        
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

    @patch('pipeline_orchestrator.prompt_for_service_type')
    @patch('pipeline_orchestrator.prompt_for_plan')
    @patch('pipeline_orchestrator.fetch_service_plan')
    @patch('pipeline_orchestrator.discover_raw_audio')
    @patch('pipeline_orchestrator.segment_service_audio')
    @patch('pipeline_orchestrator.copy_songs')
    @patch('pipeline_orchestrator.move_songs')
    @patch('pipeline_orchestrator.make_videos')
    @patch('pipeline_orchestrator.input')
    def test_main_pipeline_default_zero_args_scopes_staging_to_target_date(self, mock_input, mock_make_videos, mock_move_songs, mock_copy_songs, mock_segment, mock_discover, mock_fetch_plan, mock_prompt_plan, mock_prompt_st):
        """Interactive Sunday run locks a single target date and passes that target_date to copy_songs."""
        mock_input.return_value = "y"
        mock_prompt_st.return_value = "123"
        mock_prompt_plan.return_value = ("456", "2026-09-06")
        mock_fetch_plan.return_value = MagicMock()
        mock_discover.return_value = ["/path/to/R_20260906-103109.wav"]

        pipeline_orchestrator.main([])

        mock_copy_songs.assert_called_once()
        kwargs = mock_copy_songs.call_args[1]
        self.assertEqual(kwargs.get("target_date"), "2026-09-06")

    @patch('pipeline_orchestrator.copy_songs')
    @patch('pipeline_orchestrator.fetch_service_plan')
    def test_main_post_processing_with_date_flag(self, mock_fetch_plan, mock_copy_songs):
        """Standalone post-processing with --date scopes copy_songs to that date without running main pipeline."""
        pipeline_orchestrator.main(["--publish-staging", "--date", "2026-09-06"])

        mock_fetch_plan.assert_not_called()
        mock_copy_songs.assert_called_once()
        kwargs = mock_copy_songs.call_args[1]
        self.assertEqual(kwargs.get("target_date"), "2026-09-06")

    @patch('pipeline_orchestrator.copy_songs')
    @patch('pipeline_orchestrator.fetch_service_plan')
    def test_main_post_processing_with_date_range_flags(self, mock_fetch_plan, mock_copy_songs):
        """Standalone post-processing with --start-date and --end-date scopes copy_songs to that timeframe."""
        pipeline_orchestrator.main(["--publish-staging", "--start-date", "2026-08-01", "--end-date", "2026-08-31"])

        mock_fetch_plan.assert_not_called()
        mock_copy_songs.assert_called_once()
        kwargs = mock_copy_songs.call_args[1]
        self.assertEqual(kwargs.get("start_date"), "2026-08-01")
        self.assertEqual(kwargs.get("end_date"), "2026-08-31")

    @patch('pipeline_orchestrator.input')
    def test_prompt_for_date_filter_option_1_single_date(self, mock_input):
        mock_input.side_effect = ["1", "2026-09-06"]
        target, start, end = pipeline_orchestrator.prompt_for_date_filter()
        self.assertEqual(target, "2026-09-06")
        self.assertIsNone(start)
        self.assertIsNone(end)

    @patch('pipeline_orchestrator.input')
    def test_prompt_for_date_filter_option_2_range(self, mock_input):
        mock_input.side_effect = ["2", "2026-08-01", "2026-08-31"]
        target, start, end = pipeline_orchestrator.prompt_for_date_filter()
        self.assertIsNone(target)
        self.assertEqual(start, "2026-08-01")
        self.assertEqual(end, "2026-08-31")

    @patch('pipeline_orchestrator.input')
    def test_prompt_for_date_filter_option_3_all(self, mock_input):
        mock_input.side_effect = ["3"]
        target, start, end = pipeline_orchestrator.prompt_for_date_filter()
        self.assertIsNone(target)
        self.assertIsNone(start)
        self.assertIsNone(end)

    @patch('pipeline_orchestrator.input')
    def test_prompt_for_date_filter_direct_date(self, mock_input):
        mock_input.side_effect = ["2026-09-06"]
        target, start, end = pipeline_orchestrator.prompt_for_date_filter()
        self.assertEqual(target, "2026-09-06")
        self.assertIsNone(start)
        self.assertIsNone(end)

    @patch('pipeline_orchestrator.input')
    def test_prompt_for_date_filter_invalid_then_valid(self, mock_input):
        mock_input.side_effect = ["99", "1", "invalid-date", "2026-09-06"]
        target, start, end = pipeline_orchestrator.prompt_for_date_filter()
        self.assertEqual(target, "2026-09-06")
        self.assertIsNone(start)
        self.assertIsNone(end)

    @patch('pipeline_orchestrator.copy_songs')
    def test_main_mismatched_start_date_without_end_date(self, mock_copy_songs):
        pipeline_orchestrator.main(["--publish-staging", "--start-date", "2026-08-01"])
        mock_copy_songs.assert_not_called()

    @patch('pipeline_orchestrator.input')
    def test_prompt_for_date_filter_custom_labels_option_3(self, mock_input):
        mock_input.side_effect = ["3"]
        target, start, end = pipeline_orchestrator.prompt_for_date_filter(
            title="Date Filter for Video Generation",
            all_label="generate videos for all songs"
        )
        self.assertIsNone(target)
        self.assertIsNone(start)
        self.assertIsNone(end)

    @patch('pipeline_orchestrator.input')
    def test_prompt_for_date_filter_custom_labels_option_2_range(self, mock_input):
        mock_input.side_effect = ["2", "2026-08-01", "2026-08-31"]
        target, start, end = pipeline_orchestrator.prompt_for_date_filter(
            title="Date Filter for Publishing Verified Songs",
            all_label="move all verified songs"
        )
        self.assertIsNone(target)
        self.assertEqual(start, "2026-08-01")
        self.assertEqual(end, "2026-08-31")

if __name__ == '__main__':
    unittest.main(verbosity=2)
