"""Legacy test entry point; run pytest through python -m pytest -q instead."""
import pytest
raise SystemExit(pytest.main(["-q", "tests"]))
