import hashlib, random
from typing import List

def bps(x: float) -> float:
    return x * 1e-4

def gen_coid(symbol: str, ts_key: str, payload: str) -> str:
    h = hashlib.md5(payload.encode("utf-8")).hexdigest()[:10]
    return f"{symbol}-{ts_key}-{h}"

def throttle_similar(symbols: List[str], corr_threshold: float) -> List[str]:
    # Placeholder policy: simple alphabetical throttle for similar symbols group
    # In practice, you'd compute rolling correlations; keep simple to avoid extra deps.
    return sorted(set(symbols))  # deterministic order

