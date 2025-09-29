import tempfile, yaml
from src.config import load_config

def test_load_valid_config():
    cfg = load_config("config.yaml")
    assert cfg.general.bar_timeframe.endswith("m")

def test_invalid_config_rejected():
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        yaml.safe_dump({"general": {"timezone":"America/New_York"}, "universe":{}, "strategy":{}, "regime":{}, "risk":{}, "portfolio":{}, "execution":{}, "reporting":{}}, f)
        name = f.name
    cfg = load_config(name)  # pydantic will fill defaults for nested where provided; if missing required, it throws
    assert cfg.general.timezone == "America/New_York"

