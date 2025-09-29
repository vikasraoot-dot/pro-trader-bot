import json, logging, sys, time

class JsonFormatter(logging.Formatter):
    def format(self, record):
        base = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if isinstance(record.args, dict):
            base.update(record.args)
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            base.update(record.extra)
        return json.dumps(base)

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(JsonFormatter())
        logger.addHandler(h)
    return logger

