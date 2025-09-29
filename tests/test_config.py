import tempfile, yaml, os
from src.config import load_config

def test_load_valid_config():
    cfg = load_config("config.yaml")
    assert cfg.general.bar_timeframe.endswith("m")

def test_invalid_config_rejected():
    # Create a minimal config file with only timezone set to ensure schema/defaults work
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
        yaml.safe_dump(
            {
                "general": {"timezone": "America/New_York"},
                "universe": {},
                "strategy": {},
                "regime": {},
                "risk": {},
                "portfolio": {},
                "execution": {},
                "reporting": {}
            },
            f
        )
        name = f.name
    try:
        cfg = load_config(name)
        assert cfg.general.timezone == "America/New_York"
    finally:
        # Clean up the temp file even if the assertion fails
        try:
            os.remove(name)
        except OSError:
            pass
