#!/bin/bash
# Critical test runner — run BEFORE any deployment
# Per QTS Section 9.2: All critical tests must pass before deploy.
set -e

echo "=== Running CRITICAL test suite ==="

echo "--- AI Validator (100% required) ---"
python -m pytest tests/unit/test_ai_validator.py -v --tb=short

echo "--- Risk Engine (100% required) ---"
python -m pytest tests/unit/test_risk_engine.py -v --tb=short

echo "--- Pip Math (100% required) ---"
python -m pytest tests/unit/test_pip_math.py -v --tb=short

echo "--- Position Sizer ---"
python -m pytest tests/unit/test_position_sizer.py -v --tb=short

echo "--- Data Failure Chaos Tests ---"
python -m pytest tests/chaos/test_data_failures.py -v --tb=short

echo "--- Broker Failure Chaos Tests ---"
python -m pytest tests/chaos/test_broker_failures.py -v --tb=short

echo "--- Crash Recovery Chaos Tests ---"
python -m pytest tests/chaos/test_crash_recovery.py -v --tb=short

echo "--- Failover Tests ---"
python -m pytest tests/chaos/test_failover.py -v --tb=short

echo "--- Security Tests ---"
python -m pytest tests/security/ -v --tb=short

echo "--- Signal Pipeline Integration ---"
python -m pytest tests/integration/test_signal_pipeline.py -v --tb=short

echo "=== ALL CRITICAL TESTS PASSED ==="
echo "Safe to deploy."
