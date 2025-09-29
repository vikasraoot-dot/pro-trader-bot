from pydantic import BaseModel, Field, ValidationError
from typing import List, Dict, Optional
import yaml, sys

class GeneralCfg(BaseModel):
    timezone: str
    seed: int = 42
    rth_only: bool = True
    bar_timeframe: str = "15m"
    htf_timeframe: str = "60m"
    flatten_minutes_before_close: int = 7
    bar_close_grace_sec: int = 10

class UniverseCfg(BaseModel):
    min_price: float = 5.0
    min_dollar_vol_20d: float = 5_000_000
    exclude: List[str] = []

class StrategyCfg(BaseModel):
    ema_fast: int = 9
    ema_slow: int = 21
    adx_len: int = 14
    rsi_len: int = 14
    ema_slope_bps: float = 12.0
    adx_min: float = 22.0
    rsi_min: float = 50.0
    rsi_max: float = 75.0
    htf_align_required: bool = True

class RegimeCfg(BaseModel):
    trend_adx_min: float = 20.0
    chop_adx_max: float = 15.0
    high_vol_mult: float = 2.0

class RiskCfg(BaseModel):
    account_risk_per_trade: float = 0.005
    atr_k_stop: float = 1.5
    take_profit_R: float = 1.3
    be_bump_at_R: float = 0.5
    partial_take_R: float = 1.0
    partial_take_pct: float = 0.5
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    min_notional: float = 200.0
    max_position_pct: float = 0.10
    max_net_exposure_pct: float = 0.60
    max_sector_pct: float = 0.25
    max_daily_loss_pct: float = 0.02
    max_concurrent_positions: int = 3
    symbol_cooloff_min: int = 45
    spread_bps_max: float = 15.0

class PortfolioCfg(BaseModel):
    correlation_block_threshold: float = 0.85
    sector_map: Dict[str, str] = {}

class ExecutionCfg(BaseModel):
    time_in_force: str = "day"
    allow_short: bool = False

class ReportingCfg(BaseModel):
    enable_daily_email: bool = False
    email_to: List[str] = []
    slack_webhook: str = ""
    outdir: str = "reports"

class Config(BaseModel):
    general: GeneralCfg
    universe: UniverseCfg
    strategy: StrategyCfg
    regime: RegimeCfg
    risk: RiskCfg
    portfolio: PortfolioCfg
    execution: ExecutionCfg
    reporting: ReportingCfg

def load_config(path: str) -> Config:
    with open(path, "r") as f:
        raw = yaml.safe_load(f)
    try:
        return Config(**raw)
    except ValidationError as e:
        print("Config validation failed:", e, file=sys.stderr)
        raise

