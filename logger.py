"""
# logger.py
# Logging basic config
"""

import logging


def setup_logging():
    """ Define basic logger config """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
