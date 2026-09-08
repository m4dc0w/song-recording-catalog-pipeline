import unittest
from unittest.mock import patch, MagicMock
import sys
import pipeline_orchestrator_backfill

class TestPipelineOrchestratorBackfill(unittest.TestCase):
    
    @patch('pipeline_orchestrator_backfill.input')
    def test_prompt_for_dates_success(self, mock_input):
        mock_input.side_effect = ["2026-01-01", "2026-01-31"]
        start, end = pipeline_orchestrator_backfill.prompt_for_dates()
        self.assertEqual(start, "2026-01-01")
        self.assertEqual(end, "2026-01-31")

    @patch('pipeline_orchestrator_backfill.input')
    def test_prompt_for_dates_retry_on_invalid(self, mock_input):
        # First return invalid date, then valid
        mock_input.side_effect = ["invalid", "2026-01-31", "2026-01-01", "2026-01-31"]
        start, end = pipeline_orchestrator_backfill.prompt_for_dates()
        self.assertEqual(start, "2026-01-01")
        self.assertEqual(end, "2026-01-31")
        self.assertEqual(mock_input.call_count, 4)

    def test_parse_pco_date(self):
        dt = pipeline_orchestrator_backfill.parse_pco_date("September 6, 2026")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 9)
        self.assertEqual(dt.day, 6)
        
        self.assertIsNone(pipeline_orchestrator_backfill.parse_pco_date("Invalid Date Format"))

    @patch('pipeline_orchestrator_backfill.argparse.ArgumentParser.parse_args')
    @patch('pipeline_orchestrator_backfill.prompt_for_service_type')
    @patch('pipeline_orchestrator_backfill.prompt_for_dates')
    @patch('pipeline_orchestrator_backfill.fetch_recent_plans')
    @patch('pipeline_orchestrator_backfill.discover_raw_audio')
    @patch('pipeline_orchestrator_backfill.fetch_service_plan')
    @patch('pipeline_orchestrator_backfill.segment_service_audio')
    @patch('pipeline_orchestrator_backfill.time.sleep')
    def test_main_backfill_execution(self, mock_sleep, mock_segment, mock_fetch_plan, mock_discover, mock_fetch_recent, mock_prompt_dates, mock_prompt_st, mock_parse_args):
        mock_args = MagicMock()
        mock_args.service_type = None
        mock_args.start_date = None
        mock_args.end_date = None
        mock_args.limit = 100
        mock_parse_args.return_value = mock_args
        
        mock_prompt_st.return_value = "123"
        mock_prompt_dates.return_value = ("2026-09-01", "2026-09-30")
        
        mock_plan1 = MagicMock()
        mock_plan1.id = "456"
        mock_plan1.dates = "September 6, 2026"
        mock_plan1.title = "Vision Sunday"
        
        mock_plan2 = MagicMock()
        mock_plan2.id = "789"
        mock_plan2.dates = "August 30, 2026" # Out of bounds
        
        mock_plan3 = MagicMock()
        mock_plan3.id = "000"
        mock_plan3.dates = "September 13, 2026" # Fails during processing
        
        mock_fetch_recent.return_value = [mock_plan1, mock_plan2, mock_plan3]
        
        # Only plan1 and plan3 should make it past the date filter
        
        mock_discover.side_effect = [
            ["/path/to/R_20260906-103109.wav"], # success for plan1
            [] # fail (empty) for plan3
        ]
        
        mock_plan_details = MagicMock()
        mock_fetch_plan.return_value = mock_plan_details
        
        pipeline_orchestrator_backfill.main()
        
        mock_prompt_st.assert_called_once()
        mock_prompt_dates.assert_called_once()
        mock_fetch_recent.assert_called_once_with("123", limit=100, start_date="2026-09-01", end_date="2026-09-30")
        
        # Called for Sept 6 and Sept 13
        self.assertEqual(mock_discover.call_count, 2)
        
        # Called only for Sept 6 because Sept 13 threw FileNotFoundError on empty discover
        mock_fetch_plan.assert_called_once_with("123", "456", "2026-09-06")
        
        mock_segment.assert_called_once_with(mock_plan_details)
        
        # Sleep called twice, once for each plan that we attempted to process
        self.assertEqual(mock_sleep.call_count, 2)

    @patch('pipeline_orchestrator_backfill.argparse.ArgumentParser.parse_args')
    @patch('pipeline_orchestrator_backfill.prompt_for_service_type')
    @patch('pipeline_orchestrator_backfill.prompt_for_dates')
    @patch('pipeline_orchestrator_backfill.fetch_recent_plans')
    @patch('pipeline_orchestrator_backfill.discover_raw_audio')
    def test_main_backfill_missing_raw_audio_dir(self, mock_discover, mock_fetch_recent, mock_prompt_dates, mock_prompt_st, mock_parse_args):
        mock_args = MagicMock()
        mock_args.service_type = "123"
        mock_args.start_date = "2026-09-01"
        mock_args.end_date = "2026-09-30"
        mock_parse_args.return_value = mock_args

        mock_plan = MagicMock()
        mock_plan.id = "456"
        mock_plan.dates = "September 6, 2026"
        mock_plan.title = "Vision Sunday"
        mock_fetch_recent.return_value = [mock_plan]

        mock_discover.side_effect = FileNotFoundError("Raw audio directory does not exist")

        pipeline_orchestrator_backfill.main()

        mock_fetch_recent.assert_called_once()
        mock_discover.assert_called_once()

    def test_argument_parser_default_limit(self):
        with patch.object(sys, 'argv', ['pipeline_orchestrator_backfill.py']):
            with patch('pipeline_orchestrator_backfill.prompt_for_service_type', return_value="123"):
                with patch('pipeline_orchestrator_backfill.prompt_for_dates', return_value=("2026-09-01", "2026-09-30")):
                    with patch('pipeline_orchestrator_backfill.fetch_recent_plans', return_value=[]) as mock_fetch:
                        with self.assertRaises(SystemExit):
                            pipeline_orchestrator_backfill.main()
                        mock_fetch.assert_called_once_with("123", limit=100, start_date="2026-09-01", end_date="2026-09-30")

    @patch('pipeline_orchestrator_backfill.fetch_recent_plans')
    @patch('pipeline_orchestrator_backfill.discover_raw_audio')
    @patch('pipeline_orchestrator_backfill.fetch_service_plan')
    @patch('pipeline_orchestrator_backfill.segment_service_audio')
    @patch('pipeline_orchestrator_backfill.time.sleep')
    @patch('pipeline_orchestrator_backfill.copy_songs')
    def test_main_backfill_with_publish_staging_scopes_to_timeframe(self, mock_copy_songs, mock_sleep, mock_segment, mock_fetch_plan, mock_discover, mock_fetch_recent):
        mock_plan = MagicMock()
        mock_plan.id = "456"
        mock_plan.dates = "September 6, 2026"
        mock_plan.title = "Vision Sunday"
        mock_fetch_recent.return_value = [mock_plan]
        mock_discover.return_value = ["/path/to/R_20260906-103109.wav"]
        mock_fetch_plan.return_value = MagicMock()

        pipeline_orchestrator_backfill.main([
            "--service-type", "123",
            "--start-date", "2026-09-01",
            "--end-date", "2026-09-30",
            "--publish-staging"
        ])

        mock_copy_songs.assert_called_once()
        kwargs = mock_copy_songs.call_args[1]
        self.assertEqual(kwargs.get("start_date"), "2026-09-01")
        self.assertEqual(kwargs.get("end_date"), "2026-09-30")

    @patch('pipeline_orchestrator_backfill.fetch_recent_plans')
    @patch('pipeline_orchestrator_backfill.copy_songs')
    def test_main_backfill_post_processing_only(self, mock_copy_songs, mock_fetch_recent):
        pipeline_orchestrator_backfill.main([
            "--start-date", "2026-08-01",
            "--end-date", "2026-08-31",
            "--publish-staging",
            "--post-processing-only"
        ])

        # Segmentation / plan fetching must be skipped in post-processing-only mode
        mock_fetch_recent.assert_not_called()
        mock_copy_songs.assert_called_once()
        kwargs = mock_copy_songs.call_args[1]
        self.assertEqual(kwargs.get("start_date"), "2026-08-01")
        self.assertEqual(kwargs.get("end_date"), "2026-08-31")

if __name__ == '__main__':
    unittest.main(verbosity=2)
