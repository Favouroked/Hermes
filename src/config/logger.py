import logging
import os
from typing import Optional


def setup_logger(
    name: str = __name__, level: int = logging.INFO, file_path: Optional[str] = None
) -> logging.Logger:
    """
    Configure and return a logger instance with specified name and level.

    Args:
        name: Logger name (defaults to module name)
        level: Logging level (defaults to INFO)
        file_path: Optional path to log file. If provided, logs will be written to this file

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    logger.setLevel(level)

    formatter = logging.Formatter(
        "[%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if file_path:
        file_handler = logging.FileHandler(file_path)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = __name__, file_path: Optional[str] = None) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (defaults to module name)
        file_path: Optional path to log file. If provided, logs will be written to this file

    Returns:
        Configured logger instance
    """

    logs_file = os.getenv("LOGS_FILE")
    if logs_file and not file_path:
        file_path = logs_file

    return setup_logger(name, file_path=file_path)
