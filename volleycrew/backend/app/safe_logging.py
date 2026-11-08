"""Production exception logs report types, never driver tracebacks or request values."""

import logging


class ExceptionTypeOnly(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info:
            kind = record.exc_info[0]
            record.msg = "Service exception (%s)"
            record.args = (kind.__name__ if kind else "unknown",)
            record.exc_info = None
            record.exc_text = None
        return True
