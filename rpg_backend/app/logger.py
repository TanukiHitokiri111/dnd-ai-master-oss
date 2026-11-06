import logging
import sys


def setup_logger(name: str = "rpg") -> logging.Logger:
    """Единый логгер. Пишет в stdout — Docker и systemd журналируют его сами."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    ))
    logger.addHandler(handler)
    return logger


logger = setup_logger()
