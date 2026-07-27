"""Tests for service.py — non-pywin32-dependent logic only.

Windows service registration/lifecycle (install, start, stop, remove)
cannot be meaningfully unit tested — those go in the manual checklist.
"""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from service import ServiceStopEvent, parse_service_args


# --- Fixtures ---

@pytest.fixture
def config_file(tmp_path):
    """Write a valid config to a temp file."""
    data = {
        "odoo_url": "http://localhost:8069",
        "printers": [
            {
                "name": "test_printer",
                "connection_type": "network",
                "host": "192.168.1.100",
                "port": 9100,
                "api_key": "test-key",
            }
        ],
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
    return path


# --- ServiceStopEvent tests ---

class TestServiceStopEvent:
    def test_initial_state_not_set(self):
        event = ServiceStopEvent()
        assert not event.is_stopped

    def test_signal_sets_stopped(self):
        event = ServiceStopEvent()
        event.signal()
        assert event.is_stopped

    def test_signal_idempotent(self):
        event = ServiceStopEvent()
        event.signal()
        event.signal()
        assert event.is_stopped

    def test_wait_returns_immediately_when_set(self):
        event = ServiceStopEvent()
        event.signal()
        event.wait(timeout=1.0)
        # Should not hang

    def test_wait_blocks_until_signaled(self):
        event = ServiceStopEvent()
        signaled = []

        def signaler():
            import time
            time.sleep(0.1)
            event.signal()
            signaled.append(True)

        t = threading.Thread(target=signaler)
        t.start()
        event.wait(timeout=2.0)
        t.join()
        assert event.is_stopped
        assert signaled

    def test_wait_respects_timeout(self):
        event = ServiceStopEvent()
        event.wait(timeout=0.05)
        assert not event.is_stopped


# --- parse_service_args tests ---

class TestParseServiceArgs:
    def test_parse_config_path(self):
        args = parse_service_args(["--config", "myconfig.yaml"])
        assert args.config == "myconfig.yaml"

    def test_parse_default_config(self):
        args = parse_service_args([])
        assert args.config == "config.yaml"

    def test_parse_verbose(self):
        args = parse_service_args(["--verbose"])
        assert args.verbose is True

    def test_parse_no_verbose(self):
        args = parse_service_args([])
        assert args.verbose is False

    def test_parse_job_delay(self):
        args = parse_service_args(["--job-delay", "5.0"])
        assert args.job_delay == 5.0

    def test_parse_default_job_delay(self):
        args = parse_service_args([])
        assert args.job_delay == 2.0
