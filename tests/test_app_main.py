"""
Unit tests for app/logger.py
Covers: setup_logger() returns a configured Logger; module-level `logger` works.
"""
import os
import sys
import logging
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


class TestSetupLogger:
    """Tests for app.logger.setup_logger()"""

    def test_setup_logger_returns_logger(self):
        from app.logger import setup_logger
        log = setup_logger("test_neuron_setup")
        assert isinstance(log, logging.Logger)

    def test_logger_name_matches(self):
        from app.logger import setup_logger
        log = setup_logger("my_test_logger")
        assert log.name == "my_test_logger"

    def test_logger_level_is_debug(self):
        from app.logger import setup_logger
        log = setup_logger("level_check_logger")
        assert log.level == logging.DEBUG

    def test_logger_has_at_least_one_handler(self):
        from app.logger import setup_logger
        log = setup_logger("handler_check_logger")
        # May inherit handlers from root, so check effective handlers
        assert len(log.handlers) >= 0  # at minimum, no error
        # Effective handler check (propagation + root)
        assert log.hasHandlers()

    def test_logger_no_duplicate_handlers(self):
        """Calling setup_logger twice for same name shouldn't duplicate handlers."""
        from app.logger import setup_logger
        log1 = setup_logger("dedup_test_logger")
        handler_count_1 = len(log1.handlers)
        log2 = setup_logger("dedup_test_logger")
        handler_count_2 = len(log2.handlers)
        assert handler_count_1 == handler_count_2

    def test_default_name_is_neuron(self):
        from app.logger import setup_logger
        log = setup_logger()
        assert log.name == "neuron"

    def test_console_handler_is_stream_handler(self):
        from app.logger import setup_logger
        log = setup_logger("stream_handler_test")
        stream_handlers = [h for h in log.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) >= 1

    def test_handler_formatter_set(self):
        from app.logger import setup_logger
        log = setup_logger("formatter_test_logger_unique")
        for handler in log.handlers:
            assert handler.formatter is not None


class TestModuleLevelLogger:
    """Tests for the pre-built `logger` instance in app.logger."""

    def test_module_logger_exists(self):
        from app.logger import logger
        assert logger is not None

    def test_module_logger_is_logger_instance(self):
        from app.logger import logger
        assert isinstance(logger, logging.Logger)

    def test_module_logger_can_log_info(self):
        from app.logger import logger
        try:
            logger.info("Test info message from unit test")
        except Exception as e:
            pytest.fail(f"logger.info() raised: {e}")

    def test_module_logger_can_log_warning(self):
        from app.logger import logger
        try:
            logger.warning("Test warning message from unit test")
        except Exception as e:
            pytest.fail(f"logger.warning() raised: {e}")

    def test_module_logger_can_log_error(self):
        from app.logger import logger
        try:
            logger.error("Test error message from unit test")
        except Exception as e:
            pytest.fail(f"logger.error() raised: {e}")

    def test_module_logger_can_log_debug(self):
        from app.logger import logger
        try:
            logger.debug("Test debug message from unit test")
        except Exception as e:
            pytest.fail(f"logger.debug() raised: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
