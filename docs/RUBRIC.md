# Code Quality Rubric (Top-Scoring)

**A. Arch & Separation (20)**
- Layered modules (config, data, indicators, strategy, risk/portfolio, OMS/broker, reconcile/report)
- Clear contracts & pure functions for indicators; no side effects
- Small, composable scripts for CLI

**B. Determinism & Safety (20)**
- Closed-bar only, NYSE calendar/holidays, bar-close grace
- Idempotent COIDs; pre-close flatten; retries/backoff; error budgets
- Portfolio caps, daily DD kill-switch, cool-offs

**C. Research Fidelity (20)**
- Backtest: spread/fees/slippage, ATR touch logic, OOS splits
- Metrics beyond Sharpe; reproducible seeds; artifacts

**D. Observability (15)**
- JSON logs; metrics counters; daily PnL summary
- Clear signal reasons in logs

**E. Tests & CI (15)**
- Unit/property tests for indicators
- Sizing & risk tests; config validation tests
- CI that runs tests and artifacts a small backtest report

**F. Docs & Runbook (10)**
- README with quick start, opinions
- Incident playbook (flatten, 422 storms, data outage)

