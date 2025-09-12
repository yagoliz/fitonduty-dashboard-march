#!/usr/bin/env python3
"""Test runner for FitonDuty March Dashboard"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_tests(test_type=None, verbose=False, coverage=False, file_pattern=None):
    """Run tests with specified options"""
    
    cmd = ["python", "-m", "pytest"]
    
    # Add verbosity
    if verbose:
        cmd.append("-v")
    
    # Add coverage
    if coverage:
        cmd.extend(["--cov=.", "--cov-report=html", "--cov-report=term-missing"])
    
    # Filter by test type
    if test_type:
        cmd.extend(["-m", test_type])
    
    # Filter by file pattern
    if file_pattern:
        cmd.append(f"tests/**/*{file_pattern}*")
    else:
        cmd.append("tests/")
    
    print(f"Running command: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"Tests failed with exit code {e.returncode}")
        return e.returncode
    except KeyboardInterrupt:
        print("\nTests interrupted by user")
        return 1


def main():
    parser = argparse.ArgumentParser(description="Run FitonDuty March Dashboard tests")
    
    parser.add_argument(
        "--type", "-t",
        choices=["unit", "integration", "slow", "database"],
        help="Run specific type of tests"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Run tests with verbose output"
    )
    
    parser.add_argument(
        "--coverage", "-c",
        action="store_true",
        help="Run tests with coverage report"
    )
    
    parser.add_argument(
        "--file", "-f",
        help="Run tests matching file pattern"
    )
    
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Run quick tests only (excludes slow and database tests)"
    )
    
    args = parser.parse_args()
    
    if args.quick:
        test_type = "unit and not slow and not database"
    else:
        test_type = args.type
    
    return run_tests(
        test_type=test_type,
        verbose=args.verbose,
        coverage=args.coverage,
        file_pattern=args.file
    )


if __name__ == "__main__":
    sys.exit(main())