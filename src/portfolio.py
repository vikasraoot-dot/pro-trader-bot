from typing import Dict, List
from .config import Config
from .utils import throttle_similar

def enforce_portfolio_limits(cfg: Config, open_positions: Dict[str, float], proposed: List[str], equity: float):
    # open_positions: symbol -> notional_exposure
    net_exposure = sum(abs(v) for v in open_positions.values()) / max(1.0, equity)
    allowed = []
    if net_exposure >= cfg.risk.max_net_exposure_pct:
        return allowed
    # Throttle by correlation groups (placeholder: deterministic order)
    candidates = throttle_similar(proposed, cfg.portfolio.correlation_block_threshold)
    for sym in candidates:
        pos_notional = abs(open_positions.get(sym, 0.0))
        if pos_notional / equity >= cfg.risk.max_position_pct: 
            continue
        # sector cap omitted for brevity (requires sector map/lookup)
        allowed.append(sym)
        if (sum(abs(open_positions.get(s,0.0)) for s in allowed) / equity) >= cfg.risk.max_net_exposure_pct:
            break
    return allowed

