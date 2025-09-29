# Runbook / Incident Playbook

## Normal ops
- Start live: `python scripts/live_trader.py --config config.local.yaml`
- Backtest: `python scripts/backtest.py --config config.local.yaml --tickers NVDA,MSFT --start 2024-01-01 --end 2024-12-31`
- Daily summary: `python scripts/daily_report.py --config config.local.yaml`

## Checks before market
- API creds present; clock says open today; symbols pass liquidity screens
- Config schema validated; logs show timezone, seed, bar_close_grace

## Incidents
- **422 / invalid bracket**: router retries with jitter; verify prices and min tick; if persists, reduce TP/SL precision and re-post
- **Duplicate orders**: COID scheme prevents dupes; cancel stale GTCs via `oms.reap_stale()`
- **Partial fills**: reconciliation loop re-queries fills + positions; children repaired or canceled accordingly
- **Data outage / delayed bars**: last-bar closure oracle waits `bar_close_grace_sec`; bot skips that cycle if late
- **Daily loss breach**: auto-flatten + lockout until next session
- **Flatten EOD**: `flatten_minutes_before_close` triggers; verify flat then email summary

## Manual overrides
- Immediate flatten: kill running loop; `oms.flatten_all()` script hook (TODO: add as aux script if desired)

