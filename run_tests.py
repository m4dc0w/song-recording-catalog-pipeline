#!/usr/bin/env python3
import unittest
import sys
import os

def main():
    """
    Discovers and runs all tests matching the '*_test.py' pattern
    across the entire repository structure.
    """
    # Ensure standard fallback environment variables for headless/CI test discovery
    os.environ.setdefault("RAW_AUDIO_DIR", os.path.join(os.getcwd(), "raw_audio"))
    os.environ.setdefault("PROCESSED_AUDIO_DIR", os.path.join(os.getcwd(), "processed_audio"))
    os.environ.setdefault("STAGING_AUDIO_DIR", os.path.join(os.getcwd(), "staging_audio"))
    os.environ.setdefault("VERIFIED_AUDIO_DIR", os.path.join(os.getcwd(), "verified_audio"))
    os.environ.setdefault("VIDEOS_DIR", os.path.join(os.getcwd(), "verified_audio", "Videos"))
    os.environ.setdefault("PCO_APP_ID", "mock_app_id")
    os.environ.setdefault("PCO_SECRET", "mock_secret")
    os.environ.setdefault("GEMINI_API_KEY", "mock_gemini_api_key")

    print("🚀 Discovering and running all unit tests...")
    print("=" * 60)
    
    test_loader = unittest.TestLoader()
    # Discover all *_test.py files starting from the root directory
    test_suite = test_loader.discover(start_dir=os.getcwd(), pattern='*_test.py')
    
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    
    # Exit with a non-zero status code if any tests failed
    sys.exit(not result.wasSuccessful())

if __name__ == '__main__':
    main()
