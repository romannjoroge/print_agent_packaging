"""Tests for the diagnostics helpers in config_gui.py.

These helpers are plain, tkinter-free logic: parsing the service log,
classifying test-print failures into user-facing warnings, and collecting
configuration warnings. The GUI only wires these into widgets.
"""

from __future__ import annotations

import pytest


SAMPLE_LOG = """\
2026-08-03 08:30:00,123 [INFO] print_agent.orchestrator: Loaded config with 2 printer(s)
2026-08-03 08:30:01,456 [ERROR] print_agent.orchestrator: Print job 3 failed on Sales Office Printer: IPP rejected: HTTP 404
2026-08-03 08:30:02,789 [WARNING] print_agent.orchestrator: Cannot connect to receipt_main: Failed to connect to 192.168.1.100:9100: [Errno 113] No route to host
"""


# --- parse_service_log ---

class TestParseServiceLog:
    def test_parses_standard_lines(self):
        from config_gui import parse_service_log
        entries = parse_service_log(SAMPLE_LOG)
        assert len(entries) == 3
        assert entries[0].timestamp == "2026-08-03 08:30:00"
        assert entries[0].level == "INFO"
        assert "Loaded config" in entries[0].message

    def test_empty_text_returns_empty_list(self):
        from config_gui import parse_service_log
        assert parse_service_log("") == []
        assert parse_service_log("   \n") == []

    def test_ignores_blank_lines(self):
        from config_gui import parse_service_log
        entries = parse_service_log("\n" + SAMPLE_LOG + "\n\n")
        assert len(entries) == 3

    def test_appends_continuation_lines_to_previous_entry(self):
        from config_gui import parse_service_log
        text = (
            "2026-08-03 08:30:01,456 [ERROR] name: first line\n"
            "  File \"C:\\\\x.py\", line 12, in foo\n"
            "    raise ValueError(\"boom\")\n"
            "2026-08-03 08:30:02,789 [INFO] name: second line\n"
        )
        entries = parse_service_log(text)
        assert len(entries) == 2
        assert "first line" in entries[0].message
        assert "ValueError" in entries[0].message
        assert "second line" in entries[1].message

    def test_respects_max_entries(self):
        from config_gui import parse_service_log
        lines = [f"2026-08-03 08:30:{i:02d},000 [INFO] name: msg {i}" for i in range(50)]
        entries = parse_service_log("\n".join(lines), max_entries=10)
        assert len(entries) == 10
        assert entries[-1].message == "name: msg 49"


# --- DiagnosticsLog ---

class TestDiagnosticsLog:
    def test_add_and_entries(self):
        from config_gui import DiagnosticsLog
        log = DiagnosticsLog()
        log.add("WARNING", "something odd")
        log.add("ERROR", "something broke")
        entries = log.entries
        assert len(entries) == 2
        assert entries[0].level == "WARNING"
        assert entries[1].message == "something broke"

    def test_caps_at_max_entries(self):
        from config_gui import DiagnosticsLog
        log = DiagnosticsLog(max_entries=3)
        for i in range(10):
            log.add("INFO", f"entry {i}")
        assert len(log.entries) == 3
        assert log.entries[-1].message == "entry 9"

    def test_to_text_includes_timestamp_level_and_message(self):
        from config_gui import DiagnosticsLog
        log = DiagnosticsLog()
        log.add("ERROR", "boom")
        text = log.to_text()
        assert "[ERROR]" in text
        assert "boom" in text
        assert text.startswith("20")  # timestamp year prefix

    def test_to_text_empty(self):
        from config_gui import DiagnosticsLog
        assert DiagnosticsLog().to_text() == ""


# --- combined_log_entries ---

class TestCombinedLogEntries:
    def test_sorts_newest_first(self):
        from config_gui import LogEntry, combined_log_entries
        old = LogEntry("2026-08-03 08:00:00", "INFO", "old")
        new = LogEntry("2026-08-03 09:00:00", "ERROR", "new")
        entries = combined_log_entries([old], [new])
        assert [e.message for e in entries] == ["new", "old"]

    def test_empty_inputs(self):
        from config_gui import combined_log_entries
        assert combined_log_entries([], []) == []


# --- service_log_warnings ---

class TestServiceLogWarnings:
    def test_ipp_404_creates_ipp_warning(self):
        from config_gui import LogEntry, service_log_warnings
        entry = LogEntry(
            "2026-08-03 08:30:01",
            "ERROR",
            "Print job 3 failed on Sales Office Printer: IPP rejected: HTTP 404",
        )
        warnings = service_log_warnings([entry])
        assert len(warnings) == 1
        assert "IPP" in warnings[0]
        assert "Sales Office Printer" in warnings[0]

    def test_print_rejected_404_creates_ipp_warning(self):
        from config_gui import LogEntry, service_log_warnings
        entry = LogEntry("2026-08-03 08:30:01", "ERROR", "Print rejected: HTTP 404")
        warnings = service_log_warnings([entry])
        assert len(warnings) == 1
        assert "IPP" in warnings[0]

    def test_auth_failure_creates_api_key_warning(self):
        from config_gui import LogEntry, service_log_warnings
        entry = LogEntry(
            "2026-08-03 08:30:01",
            "ERROR",
            "Authentication failed for GET http://x/receipt_printer/pending_jobs (401 Unauthorized)",
        )
        warnings = service_log_warnings([entry])
        assert len(warnings) == 1
        assert "API key" in warnings[0]

    def test_odoo_404_creates_module_warning(self):
        from config_gui import LogEntry, service_log_warnings
        entry = LogEntry(
            "2026-08-03 08:30:01",
            "ERROR",
            "HTTP 404 from GET http://localhost:8069/receipt_printer/pending_jobs",
        )
        warnings = service_log_warnings([entry])
        assert len(warnings) == 1
        assert "404" in warnings[0]
        assert "module" in warnings[0]

    def test_unreachable_printer_warning(self):
        from config_gui import LogEntry, service_log_warnings
        entry = LogEntry(
            "2026-08-03 08:30:01",
            "WARNING",
            "Cannot connect to receipt_main: Failed to connect to 192.168.1.100:9100: refused",
        )
        warnings = service_log_warnings([entry])
        assert len(warnings) == 1
        assert "reach" in warnings[0].lower()
        assert "receipt_main" in warnings[0]

    def test_timeout_creates_timeout_warning(self):
        from config_gui import LogEntry, service_log_warnings
        entry = LogEntry(
            "2026-08-03 08:30:01",
            "ERROR",
            "Timeout fetching jobs: Read timed out (read timeout=10.0)",
        )
        warnings = service_log_warnings([entry])
        assert len(warnings) == 1
        assert "time" in warnings[0].lower()

    def test_connection_error_creates_odoo_warning(self):
        from config_gui import LogEntry, service_log_warnings
        entry = LogEntry(
            "2026-08-03 08:30:01",
            "ERROR",
            "Connection error: HTTPConnectionPool(host='localhost', port=8069): refused",
        )
        warnings = service_log_warnings([entry])
        assert len(warnings) == 1
        assert "Odoo" in warnings[0]

    def test_unknown_lines_produce_no_warnings(self):
        from config_gui import LogEntry, service_log_warnings
        entry = LogEntry("2026-08-03 08:30:01", "INFO", "Loaded config with 2 printer(s)")
        assert service_log_warnings([entry]) == []

    def test_warnings_are_deduplicated(self):
        from config_gui import LogEntry, service_log_warnings
        entries = [
            LogEntry("t1", "ERROR", "Print rejected: HTTP 404"),
            LogEntry("t2", "ERROR", "Print rejected: HTTP 404"),
        ]
        assert len(service_log_warnings(entries)) == 1


# --- classify_test_print_error ---

class TestClassifyTestPrintError:
    IPP_PRINTER = {
        "name": "hp_office",
        "connection_type": "ipp",
        "host": "192.168.1.50",
        "port": 631,
    }

    def test_ipp_404_gives_ipp_specific_warning(self):
        from config_gui import classify_test_print_error
        warning = classify_test_print_error(
            self.IPP_PRINTER, status_code=404, error_text="Not Found"
        )
        assert warning is not None
        assert "IPP" in warning
        assert "192.168.1.50" in warning

    def test_network_404_gives_odoo_module_warning(self):
        from config_gui import classify_test_print_error
        warning = classify_test_print_error(
            {"connection_type": "network", "name": "receipt_main"},
            status_code=404,
            error_text="Not Found",
        )
        assert warning is not None
        assert "Odoo" in warning
        assert "module" in warning

    def test_401_gives_api_key_warning(self):
        from config_gui import classify_test_print_error
        warning = classify_test_print_error(
            {"connection_type": "network"}, status_code=401, error_text="Unauthorized"
        )
        assert warning is not None
        assert "API key" in warning

    def test_generic_http_error(self):
        from config_gui import classify_test_print_error
        warning = classify_test_print_error(
            {"connection_type": "network"}, status_code=500, error_text="Internal Server Error"
        )
        assert warning is not None
        assert "500" in warning

    def test_connection_error_mentions_odoo_url(self):
        from config_gui import classify_test_print_error
        warning = classify_test_print_error(
            {"connection_type": "network"},
            error_text="Max retries exceeded ... Connection refused",
            odoo_url="http://localhost:8069",
        )
        assert warning is not None
        assert "localhost:8069" in warning

    def test_timeout_warning(self):
        from config_gui import classify_test_print_error
        warning = classify_test_print_error(
            {"connection_type": "network"},
            error_text="Read timed out (read timeout=10.0)",
        )
        assert warning is not None
        assert "time" in warning.lower()

    def test_no_warning_on_success(self):
        from config_gui import classify_test_print_error
        assert classify_test_print_error(
            {"connection_type": "network"}, status_code=200, error_text="ok"
        ) is None
        assert classify_test_print_error(
            {"connection_type": "network"}, status_code=None, error_text=""
        ) is None


# --- config_warnings ---

class TestConfigWarnings:
    def test_empty_odoo_url(self):
        from config_gui import config_warnings
        warnings = config_warnings("", [])
        assert any("empty" in w.lower() for w in warnings)

    def test_odoo_url_missing_scheme(self):
        from config_gui import config_warnings
        warnings = config_warnings("localhost:8069", [])
        assert any("http://" in w and "https://" in w for w in warnings)

    def test_no_printers_warning(self):
        from config_gui import config_warnings
        warnings = config_warnings("http://localhost:8069", [])
        assert any("no printers" in w.lower() for w in warnings)

    def test_valid_config_no_warnings(self):
        from config_gui import config_warnings
        printers = [
            {
                "name": "net",
                "connection_type": "network",
                "host": "10.0.0.1",
                "port": 9100,
                "api_key": "k",
            },
            {
                "name": "ipp",
                "connection_type": "ipp",
                "host": "10.0.0.2",
                "port": 631,
                "printer_uri": "ipp://10.0.0.2/printers/HP",
                "api_key": "k",
            },
        ]
        assert config_warnings("http://localhost:8069", printers) == []

    def test_ipp_printer_on_raw_port_9100_warning(self):
        from config_gui import config_warnings
        printers = [
            {
                "name": "hp",
                "connection_type": "ipp",
                "host": "10.0.0.2",
                "port": 9100,
                "api_key": "k",
            }
        ]
        warnings = config_warnings("http://localhost:8069", printers)
        assert len(warnings) == 1
        assert "hp" in warnings[0]
        assert "631" in warnings[0]

    def test_ipp_uri_missing_scheme_warning(self):
        from config_gui import config_warnings
        printers = [
            {
                "name": "hp",
                "connection_type": "ipp",
                "host": "10.0.0.2",
                "port": 631,
                "printer_uri": "10.0.0.2/printers/HP",
                "api_key": "k",
            }
        ]
        warnings = config_warnings("http://localhost:8069", printers)
        assert len(warnings) == 1
        assert "ipp://" in warnings[0]

    def test_ipp_uri_valid_scheme_no_warning(self):
        from config_gui import config_warnings
        printers = [
            {
                "name": "hp",
                "connection_type": "ipp",
                "host": "10.0.0.2",
                "port": 631,
                "printer_uri": "http://10.0.0.2:631/printers/HP",
                "api_key": "k",
            }
        ]
        assert config_warnings("http://localhost:8069", printers) == []
