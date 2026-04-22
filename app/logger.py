"""Logging Configuration"""
import logging
import sys
from pathlib import Path

def setup_logger(name: str = "neuron") -> logging.Logger:
    """Configure logger with console + file output"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler (wrap stdout to handle Unicode on Windows cp1252)
    import io
    utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    console_handler = logging.StreamHandler(utf8_stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # File handler (persists logs for crash debugging)
    try:
        log_dir = Path(__file__).resolve().parent.parent / "storage"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(
            log_dir / "neuron.log", encoding="utf-8", errors="replace"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
    except Exception:
        file_handler = None
    
    if not logger.handlers:
        logger.addHandler(console_handler)
        if file_handler:
            logger.addHandler(file_handler)
    
    return logger

logger = setup_logger()
