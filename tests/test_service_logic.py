"""Tests for service.py — non-pywin32-dependent logic only.

Windows service registration/lifecycle cannot be meaningfully unit tested
— those go in the manual checklist.
"""

from __future__ import annotations

import threading

import pytest

from service import service_main


# --- service_main wiring tests ---

class TestServiceMain:
    """Verify that service_main uses the service_event correctly."""

    def test_service_main_accepts_event(self):
        """service_main must accept a threading.Event parameter."""
        import inspect
        sig = inspect.signature(service_main)
        assert "service_event" in sig.parameters

    def test_service_main_event_type_hint(self):
        """service_event should be annotated as threading.Event."""
        import inspect
        sig = inspect.signature(service_main)
        param = sig.parameters["service_event"]
        # from __future__ import annotations makes annotations strings
        assert "threading.Event" in str(param.annotation)


# --- parse_service_args tests ---

class TestParseServiceArgs:
    def test_parse_config_path(self):
        from service import parse_service_args
        args = parse_service_args(["--config", "myconfig.yaml"])
        assert args.config == "myconfig.yaml"

    def test_parse_default_config(self):
        from service import parse_service_args
        args = parse_service_args([])
        assert args.config == "config.yaml"

    def test_parse_verbose(self):
        from service import parse_service_args
        args = parse_service_args(["--verbose"])
        assert args.verbose is True

    def test_parse_no_verbose(self):
        from service import parse_service_args
        args = parse_service_args([])
        assert args.verbose is False

    def test_parse_job_delay(self):
        from service import parse_service_args
        args = parse_service_args(["--job-delay", "5.0"])
        assert args.job_delay == 5.0

    def test_parse_default_job_delay(self):
        from service import parse_service_args
        args = parse_service_args([])
        assert args.job_delay == 2.0
