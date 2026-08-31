"""
CertVerify Test Runner Script
Usage:
    python run_tests.py
    python run_tests.py -v
    python run_tests.py tests/test_b2b.py
"""
import sys
import pytest

if __name__ == "__main__":
    args = sys.argv[1:] if len(sys.argv) > 1 else ["-v", "--tb=short"]
    print("=" * 60)
    print(" Running CertVerify API Automated Test Suite")
    print("=" * 60)
    exit_code = pytest.main(args)
    sys.exit(exit_code)
