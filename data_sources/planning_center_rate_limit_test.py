import unittest
from unittest.mock import patch, MagicMock
from data_sources.planning_center import _make_pco_request
import requests

class TestPCORateLimit(unittest.TestCase):
    @patch('data_sources.planning_center.time.sleep')
    @patch('data_sources.planning_center.requests.get')
    def test_make_pco_request_handles_429(self, mock_get, mock_sleep):
        # Mock first call returning 429, second call returning 200
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

if __name__ == '__main__':
    unittest.main()
