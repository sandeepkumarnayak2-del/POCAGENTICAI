import logging, sys, structlog

def configure_logging():
    logging.basicConfig(
        format="%(message)s", stream=sys.stdout,
        level=getattr(logging, "INFO")
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        #Only process INFO and higher.”
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )
#OP dashboard. on infra level
logger = structlog.get_logger()
