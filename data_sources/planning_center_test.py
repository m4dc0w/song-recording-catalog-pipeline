import os
import unittest
from unittest.mock import patch, MagicMock

import requests
from core.schemas import ServicePlan
from data_sources.planning_center import fetch_service_plan


class TestPlanningCenterAPI(unittest.TestCase):
    """Test suite for the Planning Center API data ingestion module."""

    def setUp(self) -> None:
        """Sets up mock environment variables for the tests."""
        # Temporarily inject fake credentials into the environment for the test runtime
        os.environ["PCO_APP_ID"] = "mock_app_id"
        os.environ["PCO_SECRET"] = "mock_secret"

    def tearDown(self) -> None:
        """Cleans up the environment after tests run."""
        os.environ.pop("PCO_APP_ID", None)
        os.environ.pop("PCO_SECRET", None)

    @patch("data_sources.planning_center.PCO_APP_ID", "")
    @patch("data_sources.planning_center.PCO_SECRET", "")
    def test_fetch_service_plan_missing_credentials(self) -> None:
        """Ensures the function halts if environment variables are missing."""
        with self.assertRaisesRegex(ValueError, "Planning Center credentials missing"):
            fetch_service_plan("123", "456", "2026-09-06")

    @patch("data_sources.planning_center.requests.get")
    def test_fetch_service_plan_http_error(self, mock_get) -> None:
        """Ensures HTTP errors (like 404 Not Found) bubble up correctly."""
        # Setup a mock response that throws an HTTPError
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        with self.assertRaises(requests.exceptions.HTTPError):
            fetch_service_plan("123", "456", "2026-09-06")

    @patch("data_sources.planning_center.requests.get")
    def test_fetch_service_plan_success(self, mock_get) -> None:
        """Verifies successful JSON parsing and mapping to dataclasses."""
        # 1. Setup mock PCO JSON response
        mock_json_data = {
            "data": [
                {
                    "type": "Item",
                    "attributes": {
                        "item_type": "header",
                        "title": "Welcome & Announcements"
                    }
                },
                {
                    "type": "Item",
                    "attributes": {
                        "item_type": "song",
                        "title": "Amazing Grace",
                        "description": "G"
                    }
                },
                {
                    "type": "Item",
                    "attributes": {
                        "item_type": "song",
                        "title": "A Song With No Key"
                    }
                }
            ]
        }
        
        mock_response = MagicMock()
        mock_response.json.return_value = mock_json_data
        mock_get.return_value = mock_response

        # 2. Execute
        result_plan = fetch_service_plan("123", "456", "2026-09-06")

        # 3. Assertions
        # Verify the API was called with the right endpoint and auth
        mock_get.assert_called_once()
        self.assertIn("service_types/123/plans/456/items", mock_get.call_args[0][0])
        self.assertEqual(mock_get.call_args[1]["auth"], ("mock_app_id", "mock_secret"))

        # Verify the returned object is a valid ServicePlan
        self.assertIsInstance(result_plan, ServicePlan)
        self.assertEqual(result_plan.date, "2026-09-06")
        
        # Verify it skipped the "header" and only captured the 2 "songs"
        self.assertEqual(len(result_plan.songs), 2)
        
        # Verify the song data mapped correctly
        self.assertEqual(result_plan.songs[0].title, "Amazing Grace")
        self.assertEqual(result_plan.songs[0].key, "G")
        self.assertEqual(result_plan.songs[1].title, "A Song With No Key")
        self.assertEqual(result_plan.songs[1].key, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
