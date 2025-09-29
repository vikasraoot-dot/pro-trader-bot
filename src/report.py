import os, json
from pathlib import Path
from datetime import datetime
from .config import Config
from .logging_utils import get_logger

class DailyReporter:
    def __init__(self, cfg: Config, logger=None, oms=None, reconciler=None):
        self.cfg = cfg
        self.logger = logger or get_logger("report")
        self.oms = oms
        self.rec = reconciler
        self.outdir = Path(cfg.reporting.outdir)
        self.outdir.mkdir(parents=True, exist_ok=True)
        self._emitted = False

    def maybe_emit_daily(self):
        if not self._emitted:
            self.emit_daily(always=True)
            self._emitted = True

    def emit_daily(self, always: bool=False):
        # Minimal: dump snapshot of positions & orders
        pos = self.oms.broker.positions()
        orders = self.oms.broker.open_orders()
        payload = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "positions": pos,
            "open_orders": orders,
        }
        path = self.outdir / f"daily_{payload['date']}.json"
        path.write_text(json.dumps(payload, indent=2))
        self.logger.info({"event":"daily_report_written","path":str(path)})

        # Slack webhook optional
        hook = os.getenv("SLACK_WEBHOOK_URL", "") or self.cfg.reporting.slack_webhook
        if hook:
            try:
                import requests
                requests.post(hook, json={"text": f"[Daily Report] {payload['date']}\nPositions: {len(pos)} | OpenOrders: {len(orders)}"})
            except Exception:
                pass

