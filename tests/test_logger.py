import logging
import re

from utils import setup_logging


def test_setup_logging_clears_existing_handlers_without_touching_root():
    root_before = len(logging.getLogger().handlers)

    setup_logging(logging.INFO)
    first_count = len(logging.getLogger("etl_virtuellaherbariet").handlers)

    setup_logging(logging.INFO)
    second_count = len(logging.getLogger("etl_virtuellaherbariet").handlers)
    root_after = len(logging.getLogger().handlers)

    assert first_count == 2
    assert second_count == 2
    assert root_before == root_after


def test_json_logging_format():
    logger = setup_logging(logging.INFO)

    file_handler = logger.handlers[0]
    output = file_handler.formatter.format(
        logging.LogRecord(
            name="etl_virtuellaherbariet.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello-json",
            args=(),
            exc_info=None,
        )
    )
    assert "INFO - hello-json" in output
    assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - INFO - hello-json$", output)
