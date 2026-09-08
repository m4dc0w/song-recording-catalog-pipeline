import os
import unittest
from unittest.mock import patch, MagicMock

import requests
from core.schemas import ServicePlan, PlanSummary
from data_sources.planning_center import (
    fetch_service_plan,
    fetch_recent_plans,
    fetch_service_types,
    _make_pco_request,
    parse_pco_plan_date,
    parse_pco_date,
)
from core.schemas import ServiceType


class TestPlanningCenterAPI(unittest.TestCase):
    """Test suite for the Planning Center API data ingestion module."""

    @patch("data_sources.planning_center.PCO_APP_ID", "")
    @patch("data_sources.planning_center.PCO_SECRET", "")
    def test_fetch_service_plan_missing_credentials(self) -> None:
        """Ensures the function halts if environment variables are missing."""
        with self.assertRaisesRegex(ValueError, "Planning Center credentials missing"):
            fetch_service_plan("123", "456", "2026-09-06")

    @patch("data_sources.planning_center.PCO_APP_ID", "mock_app_id")
    @patch("data_sources.planning_center.PCO_SECRET", "mock_secret")
    @patch("data_sources.planning_center.requests.get")
    def test_fetch_service_plan_http_error(self, mock_get) -> None:
        """Ensures HTTP errors (like 404 Not Found) bubble up correctly."""
        # Setup a mock response that throws an HTTPError
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        with self.assertRaises(requests.exceptions.HTTPError):
            fetch_service_plan("123", "456", "2026-09-06")

    @patch("data_sources.planning_center.PCO_APP_ID", "mock_app_id")
    @patch("data_sources.planning_center.PCO_SECRET", "mock_secret")
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

    @patch("data_sources.planning_center.PCO_APP_ID", "")
    @patch("data_sources.planning_center.PCO_SECRET", "")
    def test_fetch_recent_plans_missing_credentials(self) -> None:
        """Ensures fetch_recent_plans halts if environment variables are missing."""
        with self.assertRaisesRegex(ValueError, "Planning Center credentials missing"):
            fetch_recent_plans("123")

    @patch("data_sources.planning_center.PCO_APP_ID", "mock_app_id")
    @patch("data_sources.planning_center.PCO_SECRET", "mock_secret")
    @patch("data_sources.planning_center.requests.get")
    def test_fetch_recent_plans_http_error(self, mock_get) -> None:
        """Ensures HTTP errors are caught when fetching recent plans."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("401 Unauthorized")
        mock_get.return_value = mock_response

        with self.assertRaises(requests.exceptions.HTTPError):
            fetch_recent_plans("123")

    @patch("data_sources.planning_center.PCO_APP_ID", "mock_app_id")
    @patch("data_sources.planning_center.PCO_SECRET", "mock_secret")
    @patch("data_sources.planning_center.requests.get")
    def test_fetch_recent_plans_success(self, mock_get) -> None:
        """Verifies successful mapping of recent plans to PlanSummary dataclasses."""
        mock_json_data = {
            "data": [
                {
                    "id": "67890",
                    "attributes": {
                        "dates": "September 6, 2026",
                        "title": "Vision Sunday"
                    }
                },
                {
                    "id": "67891",
                    "attributes": {
                        "dates": "August 30, 2026",
                        "title": None
                    }
                }
            ]
        }
        
        mock_response = MagicMock()
        mock_response.json.return_value = mock_json_data
        mock_get.return_value = mock_response

        # Execute
        recent_plans = fetch_recent_plans("123", limit=2)

        # Assertions
        mock_get.assert_called_once()
        self.assertIn("service_types/123/plans", mock_get.call_args[0][0])
        self.assertEqual(mock_get.call_args[1]["params"], {"per_page": 2, "order": "-sort_date", "filter": "past"})
        
        self.assertEqual(len(recent_plans), 2)
        
        # Verify first plan mapped correctly to PlanSummary dataclass
        self.assertIsInstance(recent_plans[0], PlanSummary)
        self.assertEqual(recent_plans[0].id, "67890")
        self.assertEqual(recent_plans[0].dates, "September 6, 2026")
        self.assertEqual(recent_plans[0].dates_raw, "September 6, 2026")
        self.assertEqual(recent_plans[0].date, "2026-09-06")
        self.assertEqual(recent_plans[0].title, "Vision Sunday")
        
        # Verify second plan mapped correctly and handled null title safely
        self.assertIsInstance(recent_plans[1], PlanSummary)
        self.assertEqual(recent_plans[1].id, "67891")
        self.assertEqual(recent_plans[1].dates, "August 30, 2026")
        self.assertEqual(recent_plans[1].dates_raw, "August 30, 2026")
        self.assertEqual(recent_plans[1].date, "2026-08-30")
        self.assertEqual(recent_plans[1].title, "")

    def test_parse_pco_plan_date(self) -> None:
        """Verifies parsing of various Planning Center date string formats."""
        self.assertEqual(parse_pco_plan_date("September 6, 2026"), "2026-09-06")
        self.assertEqual(parse_pco_plan_date("September 6, 2026 at 10:30am"), "2026-09-06")
        self.assertEqual(parse_pco_plan_date("Sep 6, 2026"), "2026-09-06")
        self.assertEqual(parse_pco_plan_date("2026-09-06"), "2026-09-06")
        self.assertIsNone(parse_pco_plan_date("Not A Date"))
        self.assertIsNone(parse_pco_plan_date(""))
        self.assertIsNone(parse_pco_plan_date(None))
        # Verify parse_pco_date alias matches
        self.assertEqual(parse_pco_date("September 6, 2026"), "2026-09-06")


    @patch("data_sources.planning_center.PCO_APP_ID", "")
    @patch("data_sources.planning_center.PCO_SECRET", "")
    def test_fetch_service_types_missing_credentials(self) -> None:
        with self.assertRaisesRegex(ValueError, "Planning Center credentials missing"):
            fetch_service_types()

    @patch("data_sources.planning_center.PCO_APP_ID", "mock_app_id")
    @patch("data_sources.planning_center.PCO_SECRET", "mock_secret")
    @patch("data_sources.planning_center.requests.get")
    def test_fetch_service_types_http_error(self, mock_get) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("401 Unauthorized")
        mock_get.return_value = mock_response
        with self.assertRaises(requests.exceptions.HTTPError):
            fetch_service_types()

    @patch("data_sources.planning_center.PCO_APP_ID", "mock_app_id")
    @patch("data_sources.planning_center.PCO_SECRET", "mock_secret")
    @patch("data_sources.planning_center.requests.get")
    def test_fetch_service_types_success(self, mock_get) -> None:
        mock_json_data = {
            "data": [
                {
                    "id": "111",
                    "attributes": {
                        "name": "Sunday Morning"
                    }
                },
                {
                    "id": "222",
                    "attributes": {
                        "name": None
                    }
                }
            ]
        }
        
        mock_response = MagicMock()
        mock_response.json.return_value = mock_json_data
        mock_get.return_value = mock_response

        service_types = fetch_service_types()

        mock_get.assert_called_once()
        self.assertIn("service_types", mock_get.call_args[0][0])
        
        self.assertEqual(len(service_types), 2)
        
        self.assertIsInstance(service_types[0], ServiceType)
        self.assertEqual(service_types[0].id, "111")
        self.assertEqual(service_types[0].name, "Sunday Morning")
        
        self.assertIsInstance(service_types[1], ServiceType)
        self.assertEqual(service_types[1].id, "222")
        self.assertEqual(service_types[1].name, "Unknown Service Type")

    @patch("data_sources.planning_center.time.sleep")
    @patch("data_sources.planning_center.requests.get")
    def test_make_pco_request_handles_429(self, mock_get, mock_sleep) -> None:
        """Verifies that 429 rate limit responses trigger retry backoff with Retry-After delay."""
        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.headers = {"Retry-After": "5"}

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = {"data": []}

        mock_get.side_effect = [mock_429, mock_200]

        result = _make_pco_request("http://test.url")

        self.assertEqual(result, {"data": []})
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once_with(5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
