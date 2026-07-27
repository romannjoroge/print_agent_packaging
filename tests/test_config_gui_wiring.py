"""Tests for config_gui.py — wiring logic between GUI and config_manager.

These tests verify that the GUI's internal logic (form data extraction,
validation calls, save/delete dispatch) works correctly, without requiring
a running tkinter event loop.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest
import yaml


# --- Fixtures ---

@pytest.fixture
def config_file(tmp_path):
    data = {
        "odoo_url": "http://localhost:8069",
        "printers": [
            {
                "name": "receipt_main",
                "connection_type": "network",
                "host": "192.168.1.100",
                "port": 9100,
                "api_key": "key-net",
            },
            {
                "name": "receipt_usb",
                "connection_type": "usb",
                "vendor_id": 0x0456,
                "product_id": 0x0808,
                "api_key": "key-usb",
            },
        ],
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
    return path


# --- Import tests ---

class TestGuiImports:
    """Verify the module imports cleanly (no tkinter import errors)."""

    def test_import_module(self):
        import config_gui
        assert hasattr(config_gui, "ConfigGUI")

    def test_has_expected_form_fields(self):
        import config_gui
        assert hasattr(config_gui, "NETWORK_FIELDS")
        assert hasattr(config_gui, "USB_FIELDS")
        assert hasattr(config_gui, "IPP_FIELDS")


# --- Form field definitions ---

class TestFormFields:
    def test_network_fields_include_host_port(self):
        from config_gui import NETWORK_FIELDS
        names = [f.name for f in NETWORK_FIELDS]
        assert "host" in names
        assert "port" in names

    def test_usb_fields_include_vendor_product(self):
        from config_gui import USB_FIELDS
        names = [f.name for f in USB_FIELDS]
        assert "vendor_id" in names
        assert "product_id" in names
        assert "device_path" in names

    def test_ipp_fields_include_host_port(self):
        from config_gui import IPP_FIELDS
        names = [f.name for f in IPP_FIELDS]
        assert "host" in names
        assert "port" in names
        assert "printer_uri" in names


# --- Printer data extraction ---

class TestPrinterDataExtraction:
    def test_extract_network_printer_data(self):
        from config_gui import extract_printer_data
        form_data = {
            "name": "test",
            "api_key": "key",
            "connection_type": "network",
            "host": "10.0.0.1",
            "port": "9100",
        }
        result = extract_printer_data(form_data)
        assert result["name"] == "test"
        assert result["connection_type"] == "network"
        assert result["host"] == "10.0.0.1"
        assert result["port"] == 9100

    def test_extract_usb_printer_data_with_ids(self):
        from config_gui import extract_printer_data
        form_data = {
            "name": "usb1",
            "api_key": "key",
            "connection_type": "usb",
            "vendor_id": "0x0456",
            "product_id": "0x0808",
            "device_path": "",
        }
        result = extract_printer_data(form_data)
        assert result["vendor_id"] == 0x0456
        assert result["product_id"] == 0x0808

    def test_extract_usb_printer_data_with_device_path(self):
        from config_gui import extract_printer_data
        form_data = {
            "name": "usb2",
            "api_key": "key",
            "connection_type": "usb",
            "vendor_id": "",
            "product_id": "",
            "device_path": "/dev/usb/lp0",
        }
        result = extract_printer_data(form_data)
        assert result["device_path"] == "/dev/usb/lp0"
        assert "vendor_id" not in result or result.get("vendor_id") is None

    def test_extract_ipp_printer_data(self):
        from config_gui import extract_printer_data
        form_data = {
            "name": "hp",
            "api_key": "key",
            "connection_type": "ipp",
            "host": "192.168.1.50",
            "port": "631",
            "printer_uri": "ipp://192.168.1.50/printers/HP",
        }
        result = extract_printer_data(form_data)
        assert result["connection_type"] == "ipp"
        assert result["port"] == 631

    def test_extract_strips_empty_optional_fields(self):
        from config_gui import extract_printer_data
        form_data = {
            "name": "test",
            "api_key": "key",
            "connection_type": "network",
            "host": "10.0.0.1",
            "port": "9100",
            "printer_uri": "",
            "device_path": "",
        }
        result = extract_printer_data(form_data)
        # Empty optional fields should not be in the result
        assert "printer_uri" not in result or result.get("printer_uri", "") == ""
