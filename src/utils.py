import hashlib
from typing import List
from pathlib import Path
import os

def bps(x: float) -> float:
    return x * 1e-4

def gen_coid(symbol: str, ts_key: str, payload: str) -> str:
    h = hashlib.md5(payload.encode("utf-8")).hexdigest()[:10]
    return f"{symbol}-{ts_key}-{h}"

def throttle_similar(symbols: List[str], corr_threshold: float) -> List[str]:
    # Placeholder policy: simple alphabetical throttle for similar symbols group.
    # (A real impl would use rolling correlations; kept simple to avoid heavy deps.)
    return sorted(set(symbols))  # deterministic order

def _parse_tickers_text(text: str) -> List[str]:
    raw: List[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # allow comma/semicolon separated on a single line
        parts = [p.strip() for p in line.replace(";", ",").split(",") if p.strip()]
        raw.extend(parts)
    # normalize & dedupe
    uniq: List[str] = []
    seen = set()
    for tok in raw:
        sym = tok.upper()
        if sym not in seen:
            seen.add(sym)
            uniq.append(sym)
    return uniq

def read_tickers_file(path: str = "tickers.txt") -> List[str]:
    """
    Reads tickers from a text file (default: repo-root tickers.txt).
    - One ticker per line; commas/semicolons allowed.
    - Blank lines and lines starting with '#' are ignored.
    - Returns uppercase, de-duplicated list.
    Fallbacks:
      1) Env var TICKERS (comma/semicolon separated)
      2) Minimal defaults if still empty
    """
    p = Path(path)
    if p.exists() and p.is_file():
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
            tickers = _parse_tickers_text(text)
            if tickers:
                return tickers
        except Exception:
            pass

    env_val = os.environ.get("TICKERS", "")
    if env_val:
        tickers = _parse_tickers_text(env_val)
        if tickers:
            return tickers

    return ["NVDA", "MSFT", "AMD", "AAPL", "TSLA"]
