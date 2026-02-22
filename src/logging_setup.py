import logging
import os

console = False

def setup_logging(config_manager, base_dir):
    # Technically "none", but critical errors should still be logged
    lowest_level = logging.CRITICAL
    log_level = str(config_manager.get_global_setting("log_level", "none")).lower()
    if log_level == "error":
        lowest_level = logging.ERROR
    elif log_level == "warning":
        lowest_level = logging.WARNING
    elif log_level == "info":
        lowest_level = logging.INFO
    elif log_level == "debug":
        lowest_level = logging.DEBUG

    logger = logging.getLogger()
    logger.setLevel(lowest_level) # Base level

    # Prevent adding handlers multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    log_dir = os.path.join(os.path.dirname(base_dir), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, f"app.log")
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setLevel(lowest_level)

    log_format = logging.Formatter('%(asctime)s - [%(name)s] %(levelname)s - %(message)s')
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(log_format)
        logger.addHandler(console_handler)