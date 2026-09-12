# SPDX-License-Identifier: MIT
"""Unit tests for logging configuration and CLI verbosity flags (SPEC-021)."""
import logging
from pathlib import Path
import pytest
from convert import (
    configure_logging,
    parse_arguments,
    NLP_LOGGERS,
    TRACE_LEVEL,
)


def test_configure_logging_verbose_0_debug_nlp_false():
    """verbose=0, debug_nlp=False sets root and NLP loggers to INFO."""
    configure_logging(verbose=0, debug_nlp=False)
    assert logging.getLogger().level == logging.INFO
    for name in NLP_LOGGERS:
        assert logging.getLogger(name).level == logging.INFO


def test_configure_logging_verbose_1_debug_nlp_false():
    """verbose=1, debug_nlp=False sets root to DEBUG and NLP loggers to INFO."""
    configure_logging(verbose=1, debug_nlp=False)
    assert logging.getLogger().level == logging.DEBUG
    for name in NLP_LOGGERS:
        assert logging.getLogger(name).level == logging.INFO


def test_configure_logging_verbose_2_debug_nlp_false():
    """verbose=2, debug_nlp=False sets root to DEBUG and NLP loggers to DEBUG."""
    configure_logging(verbose=2, debug_nlp=False)
    assert logging.getLogger().level == logging.DEBUG
    for name in NLP_LOGGERS:
        assert logging.getLogger(name).level == logging.DEBUG


def test_configure_logging_verbose_1_debug_nlp_true():
    """verbose=1, debug_nlp=True sets root to DEBUG and NLP loggers to DEBUG."""
    configure_logging(verbose=1, debug_nlp=True)
    assert logging.getLogger().level == logging.DEBUG
    for name in NLP_LOGGERS:
        assert logging.getLogger(name).level == logging.DEBUG


def test_configure_logging_debug_nlp_only():
    """verbose=0, debug_nlp=True sets NLP loggers to DEBUG."""
    configure_logging(verbose=0, debug_nlp=True)
    for name in NLP_LOGGERS:
        assert logging.getLogger(name).level == logging.DEBUG


def test_configure_logging_debug_sql_true():
    """debug_sql=True sets root logger to TRACE_LEVEL while NLP loggers stay INFO."""
    configure_logging(verbose=0, debug_sql=True, debug_nlp=False)
    assert logging.getLogger().level == TRACE_LEVEL
    for name in NLP_LOGGERS:
        assert logging.getLogger(name).level == logging.INFO


def test_parse_arguments_verbose_count():
    """CLI parsing properly counts -v / --verbose occurrences."""
    args_default = parse_arguments(["dummy_input.txt"])
    assert args_default.verbose == 0
    assert args_default.debug_nlp is False

    args_v = parse_arguments(["dummy_input.txt", "-v"])
    assert args_v.verbose == 1
    assert args_v.debug_nlp is False

    args_vv = parse_arguments(["dummy_input.txt", "-vv"])
    assert args_vv.verbose == 2
    assert args_vv.debug_nlp is False

    args_vvv = parse_arguments(["dummy_input.txt", "-vvv"])
    assert args_vvv.verbose == 3
    assert args_vvv.debug_nlp is False

    args_verbose = parse_arguments(["dummy_input.txt", "--verbose"])
    assert args_verbose.verbose == 1

    args_multi = parse_arguments(["dummy_input.txt", "-v", "--verbose"])
    assert args_multi.verbose == 2


def test_parse_arguments_debug_nlp():
    """CLI parsing properly sets debug_nlp flag."""
    args = parse_arguments(["dummy_input.txt", "--debug-nlp"])
    assert args.debug_nlp is True
    assert args.verbose == 0

    args_combined = parse_arguments(["dummy_input.txt", "-v", "--debug-nlp"])
    assert args_combined.debug_nlp is True
    assert args_combined.verbose == 1


def test_nlp_logger_level_filtering():
    """NLP loggers are disabled for DEBUG under -v, but enabled under -vv or --debug-nlp."""
    configure_logging(verbose=1, debug_nlp=False)
    nlp_logger = logging.getLogger("ingredient-parser")
    assert not nlp_logger.isEnabledFor(logging.DEBUG)
    assert nlp_logger.isEnabledFor(logging.INFO)

    configure_logging(verbose=2, debug_nlp=False)
    assert nlp_logger.isEnabledFor(logging.DEBUG)

    configure_logging(verbose=1, debug_nlp=True)
    assert nlp_logger.isEnabledFor(logging.DEBUG)
