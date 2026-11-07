"""
Comprehensive End-to-End Platform Test Suite (Checks A through AH).
Executes against an isolated test database with zero data pollution on the development database.
"""
import sys
import os
sys.path.insert(0, os.path.abspath("."))

from tests.test_isolated_e2e import run_isolated_full_e2e

def run_all_e2e_checks():
    run_isolated_full_e2e()

if __name__ == "__main__":
    run_all_e2e_checks()
