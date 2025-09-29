import pandas as pd, numpy as np
from typing import Tuple

def sharpe(returns: pd.Series) -> float:
    if returns.std() == 0: return 0.0
    return (returns.mean() / returns.std()) * np.sqrt(252*26)  # 15m bars ~ 26/day

def max_drawdown(equity: pd.Series) -> float:
    roll_max = equity.cummax()
    dd = (equity / roll_max) - 1.0
    return dd.min()

def calmar(equity: pd.Series) -> float:
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (252/len(equity)) - 1 if len(equity)>1 else 0
    mdd = abs(max_drawdown(equity)) or 1e-6
    return cagr / mdd

def summarize_metrics(equity: pd.Series, trades: pd.DataFrame) -> str:
    if equity.empty:
        return "No results.\n"
    ret = equity.pct_change().dropna()
    s = sharpe(ret)
    mdd = max_drawdown(equity)
    cal = calmar(equity)
    pf = (trades.loc[trades["R"]>0,"R"].sum() / abs(trades.loc[trades["R"]<0,"R"].sum())) if not trades.empty else 0
    hr = (trades["R"]>0).mean() if not trades.empty else 0
    lines = [
        f"Bars: {len(equity)}",
        f"Sharpe: {s:.2f}",
        f"MaxDD: {mdd:.2%}",
        f"Calmar: {cal:.2f}",
        f"ProfitFactor: {pf:.2f}",
        f"HitRate: {hr:.2%}",
        f"Trades: {len(trades)}",
        f"Final Equity (normed): {equity.iloc[-1]:.4f}",
    ]
    return "\n".join(lines) + "\n"

