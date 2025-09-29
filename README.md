# Pro Trader Bot (EMA/ADX with MTF Regime & Professional Guardrails)

A production-minded trading bot for US equities using:
- 15m EMA(9/21) continuation with ADX/RSI and EMA-slope gating
- 1h regime alignment (trend/chop/high-vol) and portfolio/drawdown controls
- Idempotent OMS with brackets, reconciliation, and a daily PnL report
- Realistic backtests (spread + fees + slippage + ATR touch-logic)
- JSON logs, Pydantic config schema, tests + CI

## Quick start

1. **Install deps**
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt

