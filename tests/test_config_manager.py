"""Tests for config_manager.py — CRUD operations on print_agent config."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from config_manager import ConfigManager, ConfigManagerError


# --- Fixtures ---

@pytest.fixture
def sample_config_data():
    """Minimal valid config dict."""
    return {
        "odoo_url": "http://localhost:8069",
        "printers": [
            {
                "name": "receipt_main",
                "connection_type": "network",
                "host": "192.168.1.100",
                "port": 9100,
                "api_key": "key-network",
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


@pytest.fixture
def config_file(tmp_path, sample_config_data):
    """Write sample config to a temp file and return its path."""
    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(sample_config_data, default_flow_style=False, sort_keys=False))
    return path


@pytest.fixture
def manager(config_file):
    """Return a ConfigManager loaded from the sample config file."""
    return ConfigManager(config_file)


# --- Load tests ---

class TestLoad:
    def test_load_valid_config(self, manager):
        assert manager.odoo_url == "http://localhost:8069"
        assert len(manager.list_printers()) == 2

    def test_load_missing_file_raises(self, tmp_path):
        with pytest.raises(ConfigManagerError, match="not found"):
            ConfigManager(tmp_path / "nonexistent.yaml")

    def test_load_invalid_yaml_raises(self, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text("{{{{invalid")
        with pytest.raises(ConfigManagerError, match="Invalid YAML"):
            ConfigManager(path)

    def test_load_missing_odoo_url_raises(self, tmp_path):
        path = tmp_path / "no_url.yaml"
        path.write_text(yaml.dump({"printers": []}))
        with pytest.raises(ConfigManagerError, match="odoo_url"):
            ConfigManager(path)

    def test_load_missing_printers_raises(self, tmp_path):
        path = tmp_path / "no_printers.yaml"
        path.write_text(yaml.dump({"odoo_url": "http://x"}))
        with pytest.raises(ConfigManagerError, match="printers"):
            ConfigManager(path)


# --- List printers tests ---

class TestListPrinters:
    def test_returns_all_printers(self, manager):
        printers = manager.list_printers()
        assert len(printers) == 2
        names = {p["name"] for p in printers}
        assert names == {"receipt_main", "receipt_usb"}

    def test_returns_dicts_with_expected_keys(self, manager):
        printers = manager.list_printers()
        p = printers[0]
        assert "name" in p
        assert "connection_type" in p
        assert "api_key" in p

    def test_empty_list_when_no_printers(self, tmp_path):
        path = tmp_path / "empty.yaml"
        path.write_text(yaml.dump({"odoo_url": "http://x", "printers": []}))
        mgr = ConfigManager(path)
        assert mgr.list_printers() == []


# --- Add printer tests ---

class TestAddPrinter:
    def test_add_network_printer(self, manager):
        printer = {
            "name": "new_net",
            "connection_type": "network",
            "host": "10.0.0.1",
            "port": 9100,
            "api_key": "key-new",
        }
        manager.add_printer(printer)
        names = {p["name"] for p in manager.list_printers()}
        assert "new_net" in names

    def test_add_usb_printer(self, manager):
        printer = {
            "name": "new_usb",
            "connection_type": "usb",
            "vendor_id": 0x1234,
            "product_id": 0x5678,
            "api_key": "key-new-usb",
        }
        manager.add_printer(printer)
        names = {p["name"] for p in manager.list_printers()}
        assert "new_usb" in names

    def test_add_duplicate_name_raises(self, manager):
        printer = {
            "name": "receipt_main",
            "connection_type": "network",
            "host": "10.0.0.1",
            "api_key": "key-dup",
        }
        with pytest.raises(ConfigManagerError, match="already exists"):
            manager.add_printer(printer)

    def test_add_network_missing_host_raises(self, manager):
        printer = {
            "name": "bad_net",
            "connection_type": "network",
            "api_key": "key-bad",
        }
        with pytest.raises(ConfigManagerError, match="host"):
            manager.add_printer(printer)

    def test_add_usb_missing_ids_raises(self, manager):
        printer = {
            "name": "bad_usb",
            "connection_type": "usb",
            "api_key": "key-bad",
        }
        with pytest.raises(ConfigManagerError, match="vendor_id.*product_id|device_path"):
            manager.add_printer(printer)

    def test_add_unknown_type_raises(self, manager):
        printer = {
            "name": "bad_type",
            "connection_type": "bluetooth",
            "api_key": "key-bad",
        }
        with pytest.raises(ConfigManagerError, match="Unknown connection type"):
            manager.add_printer(printer)

    def test_add_missing_name_raises(self, manager):
        printer = {
            "connection_type": "network",
            "host": "10.0.0.1",
            "api_key": "key",
        }
        with pytest.raises(ConfigManagerError, match="name"):
            manager.add_printer(printer)

    def test_add_missing_api_key_raises(self, manager):
        printer = {
            "name": "no_key",
            "connection_type": "network",
            "host": "10.0.0.1",
        }
        with pytest.raises(ConfigManagerError, match="api_key"):
            manager.add_printer(printer)


# --- Update printer tests ---

class TestUpdatePrinter:
    def test_update_host(self, manager):
        manager.update_printer("receipt_main", {"host": "10.0.0.99"})
        printers = manager.list_printers()
        main = next(p for p in printers if p["name"] == "receipt_main")
        assert main["host"] == "10.0.0.99"

    def test_update_port(self, manager):
        manager.update_printer("receipt_main", {"port": 9200})
        printers = manager.list_printers()
        main = next(p for p in printers if p["name"] == "receipt_main")
        assert main["port"] == 9200

    def test_update_api_key(self, manager):
        manager.update_printer("receipt_usb", {"api_key": "new-key"})
        printers = manager.list_printers()
        usb = next(p for p in printers if p["name"] == "receipt_usb")
        assert usb["api_key"] == "new-key"

    def test_update_nonexistent_raises(self, manager):
        with pytest.raises(ConfigManagerError, match="not found"):
            manager.update_printer("ghost", {"host": "x"})

    def test_update_preserves_other_fields(self, manager):
        manager.update_printer("receipt_main", {"host": "10.0.0.99"})
        printers = manager.list_printers()
        main = next(p for p in printers if p["name"] == "receipt_main")
        assert main["port"] == 9100
        assert main["api_key"] == "key-network"

    def test_update_validates_result(self, manager):
        with pytest.raises(ConfigManagerError):
            manager.update_printer("receipt_main", {"host": ""})


# --- Remove printer tests ---

class TestRemovePrinter:
    def test_remove_existing(self, manager):
        manager.remove_printer("receipt_main")
        names = {p["name"] for p in manager.list_printers()}
        assert "receipt_main" not in names
        assert len(manager.list_printers()) == 1

    def test_remove_nonexistent_raises(self, manager):
        with pytest.raises(ConfigManagerError, match="not found"):
            manager.remove_printer("ghost")

    def test_remove_all(self, manager):
        manager.remove_printer("receipt_main")
        manager.remove_printer("receipt_usb")
        assert manager.list_printers() == []


# --- Save tests ---

class TestSave:
    def test_save_writes_valid_yaml(self, manager, tmp_path):
        out = tmp_path / "out.yaml"
        manager.save(out)
        loaded = yaml.safe_load(out.read_text())
        assert loaded["odoo_url"] == "http://localhost:8069"
        assert len(loaded["printers"]) == 2

    def test_save_to_default_path(self, config_file):
        mgr = ConfigManager(config_file)
        mgr.add_printer({
            "name": "extra",
            "connection_type": "network",
            "host": "10.0.0.5",
            "api_key": "k",
        })
        mgr.save()
        reloaded = ConfigManager(config_file)
        names = {p["name"] for p in reloaded.list_printers()}
        assert "extra" in names

    def test_save_atomic_no_corruption_on_crash(self, manager, config_file, monkeypatch):
        """Simulate a crash mid-save by making the temp file write fail.
        The original file should remain intact."""
        original_content = config_file.read_text()

        original_replace = os.replace

        def failing_replace(src, dst):
            raise OSError("simulated disk full")

        monkeypatch.setattr(os, "replace", failing_replace)
        with pytest.raises(OSError):
            manager.save(config_file)

        # Original file must be untouched
        assert config_file.read_text() == original_content

    def test_save_roundtrip_preserves_data(self, manager, tmp_path):
        out = tmp_path / "roundtrip.yaml"
        manager.save(out)
        reloaded = ConfigManager(out)
        assert reloaded.list_printers() == manager.list_printers()
        assert reloaded.odoo_url == manager.odoo_url


# --- Odoo URL tests ---

class TestOdooUrl:
    def test_get_url(self, manager):
        assert manager.odoo_url == "http://localhost:8069"

    def test_set_url(self, manager):
        manager.odoo_url = "http://example.com:8069"
        assert manager.odoo_url == "http://example.com:8069"

    def test_set_empty_url_raises(self, manager):
        with pytest.raises(ConfigManagerError, match="odoo_url"):
            manager.odoo_url = ""
