#!/bin/sh
# Ghost Stack Test Suite & Coverage Enforcer

if [ "$1" = "--no-venv" ]; then
    echo "--- CI Mode: Using System Python ---"
    pytest --cov=src tests/ --cov-report=term-missing --cov-fail-under=80
else
    echo "--- Local Mode: Using uv run ---"
    uv run pytest --cov=src tests/ --cov-report=term-missing --cov-fail-under=80
fi

RESULT=$?

if [ $RESULT -eq 0 ]; then
    echo "SUCCESS: Tests passed and coverage is sufficient."
else
    echo "FAILURE: Tests failed or coverage is below 80%."
    exit 1
fi
