#!/bin/bash
export BROWSER=true
echo "Running unit tests..."
if ! PYTHONPATH=. python3 -m unittest discover -s tests -p "test_*.py"; then
    echo "ERROR: Unit tests failed!"
    exit 1
fi
