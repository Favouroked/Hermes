import logging


def setup_logger(name: str = __name__, level: int = logging.INFO) -> logging.Logger:
    """
    Configure and return a logger instance with specified name and level.

    Args:
        name: Logger name (defaults to module name)
        level: Logging level (defaults to INFO)

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

    return logger


def get_logger(name: str = __name__) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (defaults to module name)

    Returns:
        Configured logger instance
    """
    return setup_logger(name)
