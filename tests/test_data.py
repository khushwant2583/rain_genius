from agent.data import annual_rainfall_mm

def test_missing_dataset(monkeypatch, tmp_path):
    monkeypatch.setenv("RAIN_DATA_DIR", str(tmp_path))
    # Reload module to pick up configured path
    import importlib, agent.data as data
    importlib.reload(data)
    assert data.annual_rainfall_mm("Jalore")["status"] == "missing_dataset"
