"""Run the automated test suite."""
import os
import pytest
os.environ.setdefault("USE_MODEL", "0")
raise SystemExit(pytest.main(["-q", "tests"]))
