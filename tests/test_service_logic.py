"""Tests for service.py — non-pywin32-dependent logic only."""

from __future__ import annotations

import threading

import pytest

from service import service_main


class TestServiceMain:
    def test_service_main_accepts_event(self):
        import inspect
        sig = inspect.signature(service_main)
        assert "service_event" in sig.parameters

    def test_service_main_event_type_hint(self):
        import inspect
        sig = inspect.signature(service_main)
        param = sig.parameters["service_event"]
        assert "threading.Event" in str(param.annotation)

    def test_service_main_is_callable(self):
        assert callable(service_main)
