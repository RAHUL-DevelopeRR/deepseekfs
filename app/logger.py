"""Logging Configuration"""
import io
import logging
import os
import sys

def setup_logger(name: str = "neuron") -> logging.Logger:
    """Configure logger with console + file output"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_handler = None
    if "NEURON_LOG_STDERR" in os.environ:
        stream = getattr(sys, "stderr", None)
    else:
        stream = getattr(sys, "stdout", None) or getattr(sys, "stderr", None)
    stream_buffer = getattr(stream, "buffer", None)
    if stream_buffer is not None:
        # Windowed PyInstaller apps may have no stdout/stderr. Source runs and
        # console builds still get UTF-8-safe console logging.
        utf8_stream = io.TextIOWrapper(stream_buffer, encoding="utf-8", errors="replace")
        console_handler = logging.StreamHandler(utf8_stream)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
    
    # File handler (persists logs for crash debugging)
    try:
        from app.config import STORAGE_DIR
        log_dir = STORAGE_DIR
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(
            log_dir / "neuron.log", encoding="utf-8", errors="replace"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
    except Exception:
        file_handler = None
    
    if not logger.handlers:
        if console_handler:
            logger.addHandler(console_handler)
        if file_handler:
            logger.addHandler(file_handler)
    
    return logger

logger = setup_logger()
