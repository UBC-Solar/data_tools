import logging
import sys
import pathlib
from logging.handlers import RotatingFileHandler


def configure_logger(logger: logging.Logger, log_file_path: pathlib.Path, max_log_file_size_mb: int = 5) -> None:
    """
    Configure a Logger to use stdout for INFO logs, and STDERR for error logs, and put DEBUG logs
    into a log file.

    :param logger: the logger that will be configured
    :param log_file_path: the path to the log file for DEBUG logs to be stored
    :param max_log_file_size_mb: maximum size for the DEBUG log file, in MB.
    """
    std_formatter = logging.Formatter("%(name)s %(levelname)s: %(message)s")

    # log lower levels to stdout
    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    stdout_handler.addFilter(lambda rec: logging.INFO >= rec.levelno > logging.DEBUG)
    stdout_handler.setFormatter(std_formatter)

    # log higher levels to stderr (red)
    stderr_handler = logging.StreamHandler(stream=sys.stderr)
    stderr_handler.addFilter(lambda rec: rec.levelno > logging.INFO)
    stderr_handler.setFormatter(std_formatter)

    log_file_str: str = str(log_file_path)
    if not log_file_str.endswith(".log"):
        log_file_str += ".log"
    max_file_size = max_log_file_size_mb * 1024 * 1024

    # Create a handler for file output
    file_handler = RotatingFileHandler(log_file_str, maxBytes=max_file_size, backupCount=3)
    file_handler.setLevel(logging.DEBUG)  # Log DEBUG and higher to the file
    file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_formatter)

    logger.handlers.clear()

    # Add handlers to the logger
    logger.addHandler(stdout_handler)
    logger.addHandler(stderr_handler)
    logger.addHandler(file_handler)

    logger.setLevel(logging.DEBUG)
