#!/usr/bin/env python3
import unittest
import sys
import os

def main():
    """
    Discovers and runs all tests matching the '*_test.py' pattern
    across the entire repository structure.
    """
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
