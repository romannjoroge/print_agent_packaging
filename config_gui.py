"""Desktop GUI for configuring print_agent printers using tkinter.

Screens:
- Printer list (name, type, status)
- Add/edit form (fields conditional on connection type)
- Delete with confirmation
- Test Print action

On save, the config file's mtime changes, which the orchestrator detects
on its next poll cycle and reloads automatically.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from config_manager import ConfigManager, ConfigManagerError


@dataclass
class FormField:
    """Definition of a form field for a printer connection type."""
    name: str
    label: str
    field_type: str = "text"  # text, int, hex


NETWORK_FIELDS = [
    FormField("host", "Host"),
    FormField("port", "Port", "int"),
    FormField("api_key", "API Key"),
]

USB_FIELDS = [
    FormField("vendor_id", "Vendor ID (hex)", "hex"),
    FormField("product_id", "Product ID (hex)", "hex"),
    FormField("device_path", "Device Path"),
    FormField("api_key", "API Key"),
]

IPP_FIELDS = [
    FormField("host", "Host"),
    FormField("port", "Port", "int"),
    FormField("printer_uri", "Printer URI (optional)"),
    FormField("api_key", "API Key"),
]

FIELDS_BY_TYPE = {
    "network": NETWORK_FIELDS,
    "usb": USB_FIELDS,
    "ipp": IPP_FIELDS,
}


def extract_printer_data(form_data: dict) -> dict:
    """Extract and type-convert printer data from form fields.

    Converts numeric fields (port, vendor_id, product_id) from strings
    to ints. Strips empty optional fields.
    """
    result = {"name": form_data["name"]}
    conn_type = form_data.get("connection_type", "network")
    result["connection_type"] = conn_type
    result["api_key"] = form_data.get("api_key", "")

    if conn_type == "network":
        result["host"] = form_data.get("host", "")
        port = form_data.get("port", "")
        if port:
            result["port"] = int(port)
        else:
            result["port"] = 9100

    elif conn_type == "usb":
        vendor = form_data.get("vendor_id", "")
        product = form_data.get("product_id", "")
        device_path = form_data.get("device_path", "")

        if vendor:
            result["vendor_id"] = int(vendor, 16) if vendor.startswith("0x") else int(vendor)
        if product:
            result["product_id"] = int(product, 16) if product.startswith("0x") else int(product)
        if device_path:
            result["device_path"] = device_path

    elif conn_type == "ipp":
        result["host"] = form_data.get("host", "")
        port = form_data.get("port", "")
        if port:
            result["port"] = int(port)
        else:
            result["port"] = 631
        uri = form_data.get("printer_uri", "")
        if uri:
            result["printer_uri"] = uri

    return result


# --- Diagnostics helpers (plain logic, no tkinter required) ---

_LOG_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d{3} "
    r"\[(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL)\] (?P<msg>.+)$"
)


@dataclass
class LogEntry:
    """A single log line (or block) from the service log."""

    timestamp: str
    level: str
    message: str

    @property
    def full_text(self) -> str:
        return f"{self.timestamp} [{self.level}] {self.message}"


def parse_service_log(text: str, max_entries: int = 200) -> list[LogEntry]:
    """Parse print_agent_service.log text into LogEntry objects.

    Multi-line tracebacks are appended to the preceding entry so copied
    diagnostics include the full error context.
    """
    entries: list[LogEntry] = []
    for line in text.splitlines():
        match = _LOG_LINE_RE.match(line)
        if match:
            entries.append(
                LogEntry(match.group("ts"), match.group("level"), match.group("msg"))
            )
        elif entries and line.strip():
            entries[-1].message += "\n" + line
    if max_entries and len(entries) > max_entries:
        return entries[-max_entries:]
    return entries


class DiagnosticsLog:
    """Bounded in-memory log of session diagnostics (GUI events)."""

    def __init__(self, max_entries: int = 200) -> None:
        self._max_entries = max_entries
        self._entries: list[LogEntry] = []

    def add(self, level: str, message: str) -> None:
        self._entries.append(
            LogEntry(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), level, message)
        )
        if len(self._entries) > self._max_entries:
            del self._entries[: len(self._entries) - self._max_entries]

    @property
    def entries(self) -> list[LogEntry]:
        return list(self._entries)

    def to_text(self) -> str:
        return "\n".join(e.full_text for e in self._entries)


def combined_log_entries(
    service_entries: list[LogEntry], session_entries: list[LogEntry]
) -> list[LogEntry]:
    """Merge service-log and GUI-session entries, newest first."""
    merged = list(service_entries) + list(session_entries)
    merged.sort(key=lambda e: e.timestamp, reverse=True)
    return merged


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _extract_printer_name(message: str) -> str | None:
    for pattern in (r"\bon\s+([^:]+):", r"\bto\s+([^:]+):", r"\bfor\s+([^:]+):"):
        match = re.search(pattern, message)
        if match:
            return match.group(1).strip()
    return None


def service_log_warnings(entries: list[LogEntry]) -> list[str]:
    """Map known service-log error patterns to user-friendly warnings."""
    warnings: list[str] = []
    for entry in entries:
        message = entry.message
        low = message.lower()
        printer = _extract_printer_name(message)

        if "404" in message and ("ipp rejected" in low or "print rejected" in low):
            name = f"'{printer}' " if printer else ""
            warnings.append(
                f"IPP printer {name}returned HTTP 404. The printer may not support "
                "IPP at this address/port — check the Printer URI and that the port "
                "is the IPP port (usually 631)."
            )
        elif "ipp error" in low:
            name = f"'{printer}' " if printer else ""
            warnings.append(
                f"IPP printer {name}reported an IPP protocol error. Check the Printer "
                "URI and IPP support on the device."
            )
        elif "print rejected" in low:
            warnings.append(f"A printer rejected a print job: {message.strip()}")
        elif "authentication failed" in low or "401" in message:
            warnings.append(
                "Odoo rejected an API key (401 Unauthorized). Check the printer's "
                "API key in Odoo and that it matches the configured key."
            )
        elif "http 404 from" in low:
            warnings.append(
                "Odoo returned HTTP 404 for a request. The receipt_printer module may "
                "not be installed or enabled in Odoo — check the Odoo URL and module."
            )
        elif "failed to connect to" in low:
            name = f"'{printer}' " if printer else ""
            warnings.append(
                f"Printer {name}could not be reached. Check that it is powered on, on "
                "the network, and that the host/port are correct."
            )
        elif "timed out" in low or "timeout" in low:
            warnings.append(
                "A request timed out. Check that the Odoo server and printers are "
                "reachable from this machine."
            )
        elif "connection error" in low:
            warnings.append(
                "Could not connect to Odoo. Check the Odoo URL and that the server is "
                "running and reachable."
            )
    return _dedupe(warnings)


def classify_test_print_error(
    printer: dict | None,
    status_code: int | None = None,
    error_text: str = "",
    odoo_url: str = "",
) -> str | None:
    """Return a user-friendly warning for a failed Test Print, or None."""
    low = error_text.lower()

    if status_code == 404:
        if printer and printer.get("connection_type") == "ipp":
            host = printer.get("host", "")
            port = printer.get("port", "")
            return (
                f"IPP printer '{printer.get('name', '')}' returned HTTP 404 "
                f"({host}:{port}). The printer may not support IPP at this "
                "address/port. Check the Printer URI and port (IPP usually uses 631)."
            )
        return (
            "Odoo returned HTTP 404 for the test print route. The receipt_printer "
            "module may not be installed or enabled in Odoo — check the Odoo URL "
            "and module."
        )
    if status_code == 401:
        return (
            "Odoo rejected the API key (401 Unauthorized). Check the printer's API "
            "key in Odoo and that it matches the configured key."
        )
    if status_code is not None and status_code >= 400:
        return f"Odoo returned HTTP {status_code} for the test print request."
    if (
        "connectionerror" in low
        or "connection error" in low
        or "connection refused" in low
        or "max retries exceeded" in low
    ):
        target = odoo_url or "the configured Odoo URL"
        return (
            f"Could not reach Odoo at {target}. Check the URL and that the server "
            "is running and reachable."
        )
    if "timed out" in low or "timeout" in low:
        return (
            "The request to Odoo timed out. Check that the server is running and "
            "reachable from this machine."
        )
    return None


def config_warnings(odoo_url: str, printers: list[dict]) -> list[str]:
    """Return configuration issues worth surfacing to the user."""
    warnings: list[str] = []
    if not odoo_url:
        warnings.append(
            "Odoo URL is empty. The service cannot fetch print jobs until it is set."
        )
    elif not re.match(r"^https?://", odoo_url):
        warnings.append(
            "Odoo URL does not start with http:// or https:// — the service may not "
            "be able to reach Odoo."
        )
    if not printers:
        warnings.append(
            "No printers are configured yet. Use Add to create one, then click Save."
        )
    for printer in printers:
        if printer.get("connection_type") != "ipp":
            continue
        name = printer.get("name", "")
        port = printer.get("port")
        if port == 9100:
            warnings.append(
                f"IPP printer '{name}' uses port {port}. IPP usually runs on port "
                "631 — if printing fails, change the port to 631 or provide a "
                "Printer URI."
            )
        uri = printer.get("printer_uri", "")
        if uri and not (uri.startswith("ipp://") or uri.startswith("http://")):
            warnings.append(
                f"IPP printer '{name}' has a Printer URI that does not start with "
                "ipp:// or http://."
            )
    return warnings


# --- tkinter GUI (imported lazily to allow testing on headless systems) ---

def _import_tk():
    import tkinter as tk
    from tkinter import ttk, messagebox
    return tk, ttk, messagebox


class ConfigGUI:
    """Main configuration GUI window."""

    def __init__(self, config_path: str | Path = "config.yaml") -> None:
        tk, ttk, messagebox = _import_tk()

        self._tk = tk
        self._ttk = ttk
        self._messagebox = messagebox
        self._config_path = Path(config_path)
        self._manager = ConfigManager(self._config_path)
        self._log_path = self._config_path.resolve().parent / "print_agent_service.log"
        self._session_log = DiagnosticsLog()
        self._display_entries: list[LogEntry] = []
        self._warnings: list[str] = []
        self._test_warning: str | None = None
        self._root = tk.Tk()
        self._root.title("Print Agent Configuration")
        self._root.geometry("700x500")
        self._root.minsize(600, 400)

        self._build_ui()
        self._refresh_printer_list()
        self._refresh_diagnostics()

    def _build_ui(self) -> None:
        tk, ttk, messagebox = self._tk, self._ttk, self._messagebox

        # Main frame
        main_frame = ttk.Frame(self._root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Odoo URL
        url_frame = ttk.LabelFrame(main_frame, text="Odoo Connection", padding=5)
        url_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(url_frame, text="Odoo URL:").pack(side=tk.LEFT)
        self._url_var = tk.StringVar(value=self._manager.odoo_url)
        ttk.Entry(url_frame, textvariable=self._url_var, width=50).pack(
            side=tk.LEFT, padx=(5, 0), fill=tk.X, expand=True
        )

        # Printer list
        list_frame = ttk.LabelFrame(main_frame, text="Printers", padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self._printer_tree = ttk.Treeview(
            list_frame,
            columns=("name", "type", "host"),
            show="headings",
            selectmode="browse",
        )
        self._printer_tree.heading("name", text="Name")
        self._printer_tree.heading("type", text="Type")
        self._printer_tree.heading("host", text="Host/Device")
        self._printer_tree.column("name", width=150)
        self._printer_tree.column("type", width=80)
        self._printer_tree.column("host", width=250)
        self._printer_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self._printer_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._printer_tree.configure(yscrollcommand=scrollbar.set)

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="Add", command=self._on_add).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Edit", command=self._on_edit).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Delete", command=self._on_delete).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Test Print", command=self._on_test_print).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(side=tk.RIGHT, padx=2)

        # Diagnostics: warning banner + copyable error-log dropdown
        diag_frame = ttk.LabelFrame(main_frame, text="Diagnostics / Error Log", padding=5)
        diag_frame.pack(fill=tk.X)

        self._warning_label = tk.Label(
            diag_frame,
            text="",
            anchor=tk.W,
            justify=tk.LEFT,
            wraplength=660,
            padx=6,
            pady=4,
        )
        self._warning_label.pack(fill=tk.X, pady=(0, 4))

        log_row = ttk.Frame(diag_frame)
        log_row.pack(fill=tk.X)

        ttk.Label(log_row, text="Error log:").pack(side=tk.LEFT)
        self._log_combo_var = tk.StringVar()
        self._log_combo = ttk.Combobox(
            log_row,
            textvariable=self._log_combo_var,
            state="readonly",
            height=10,
        )
        self._log_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        ttk.Button(log_row, text="Copy", command=self._on_copy_log).pack(side=tk.LEFT, padx=1)
        ttk.Button(log_row, text="Copy All", command=self._on_copy_all_log).pack(side=tk.LEFT, padx=1)
        ttk.Button(log_row, text="Refresh", command=self._refresh_diagnostics).pack(side=tk.LEFT, padx=1)
        ttk.Button(log_row, text="Open Log File", command=self._on_open_log_file).pack(side=tk.LEFT, padx=1)

    # --- Diagnostics wiring ---

    def _read_service_log(self) -> list[LogEntry]:
        """Read and parse the tail of the service log file."""
        try:
            text = self._log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        return parse_service_log(text, max_entries=200)

    def _refresh_diagnostics(self) -> None:
        """Recompute warnings and rebuild the error-log dropdown contents."""
        service_entries = self._read_service_log()
        self._display_entries = combined_log_entries(
            service_entries, self._session_log.entries
        )

        warnings = config_warnings(
            self._manager.odoo_url, self._manager.list_printers()
        )
        warnings.extend(service_log_warnings(service_entries))
        if self._test_warning:
            warnings.append(self._test_warning)
        self._warnings = _dedupe(warnings)

        self._update_warning_banner()
        self._refresh_log_entries()

    def _update_warning_banner(self) -> None:
        """Show detected warnings in amber, or a calm 'all good' state."""
        if self._warnings:
            self._warning_label.configure(
                text="\n".join(f"• {w}" for w in self._warnings),
                bg="#FFF3CD",
                fg="#856404",
                relief="solid",
            )
        else:
            self._warning_label.configure(
                text="No issues detected.",
                bg="#E8F5E9",
                fg="#1B5E20",
                relief="flat",
            )

    def _refresh_log_entries(self) -> None:
        """Populate the dropdown with the newest log entries first."""
        values = [e.full_text for e in self._display_entries]
        self._log_combo["values"] = values
        if values:
            self._log_combo_var.set(values[0])
        else:
            self._log_combo_var.set("No log entries yet.")

    def _record_log(self, level: str, message: str) -> None:
        """Add a session log entry and refresh the diagnostics panel."""
        self._session_log.add(level, message)
        self._refresh_diagnostics()

    def _copy_to_clipboard(self, text: str) -> None:
        self._root.clipboard_clear()
        self._root.clipboard_append(text)
        self._root.update()

    def _on_copy_log(self) -> None:
        text = self._log_combo_var.get()
        if text:
            self._copy_to_clipboard(text)
            self._messagebox.showinfo(
                "Copied", "Selected log entry copied to clipboard."
            )
        else:
            self._messagebox.showwarning(
                "Nothing to Copy", "There is no log entry to copy."
            )

    def _on_copy_all_log(self) -> None:
        text = "\n".join(e.full_text for e in self._display_entries)
        if text:
            self._copy_to_clipboard(text)
            self._messagebox.showinfo(
                "Copied", "Full error log copied to clipboard."
            )
        else:
            self._messagebox.showwarning(
                "Nothing to Copy", "There are no log entries to copy."
            )

    def _on_open_log_file(self) -> None:
        import os

        if not self._log_path.exists():
            self._messagebox.showwarning(
                "Log File Not Found",
                f"Service log not found at:\n{self._log_path}",
            )
            return
        try:
            os.startfile(str(self._log_path))
        except Exception as e:
            self._messagebox.showerror("Cannot Open Log", str(e))

    def _refresh_printer_list(self) -> None:
        for item in self._printer_tree.get_children():
            self._printer_tree.delete(item)

        for p in self._manager.list_printers():
            host = p.get("host", p.get("device_path", ""))
            self._printer_tree.insert(
                "", self._tk.END, values=(p["name"], p["connection_type"], host)
            )

    def _get_selected_printer_name(self) -> str | None:
        selection = self._printer_tree.selection()
        if not selection:
            return None
        values = self._printer_tree.item(selection[0], "values")
        return values[0] if values else None

    def _on_add(self) -> None:
        self._open_printer_form()

    def _on_edit(self) -> None:
        name = self._get_selected_printer_name()
        if not name:
            self._messagebox.showwarning("No Selection", "Please select a printer to edit.")
            return
        printers = self._manager.list_printers()
        printer = next((p for p in printers if p["name"] == name), None)
        if printer:
            self._open_printer_form(printer)

    def _on_delete(self) -> None:
        name = self._get_selected_printer_name()
        if not name:
            self._messagebox.showwarning("No Selection", "Please select a printer to delete.")
            return
        if self._messagebox.askyesno("Confirm Delete", f"Delete printer '{name}'?"):
            try:
                self._manager.remove_printer(name)
                self._record_log("INFO", f"Deleted printer '{name}'.")
                self._refresh_printer_list()
            except ConfigManagerError as e:
                self._record_log("ERROR", f"Delete failed for '{name}': {e}")
                self._messagebox.showerror("Error", str(e))

    def _on_test_print(self) -> None:
        name = self._get_selected_printer_name()
        if not name:
            self._messagebox.showwarning("No Selection", "Please select a printer for test print.")
            return

        printers = self._manager.list_printers()
        printer = next((p for p in printers if p["name"] == name), None)
        if not printer:
            return

        self._test_warning = None
        try:
            import requests
            resp = requests.post(
                f"{self._manager.odoo_url}/receipt_printer/test_print",
                headers={"Authorization": f"Bearer {printer['api_key']}"},
                timeout=10,
            )
            if resp.status_code == 200:
                self._record_log("INFO", f"Test print job sent to '{name}'.")
                self._messagebox.showinfo("Test Print", f"Test print job sent to '{name}'.")
            else:
                self._test_warning = classify_test_print_error(
                    printer,
                    status_code=resp.status_code,
                    error_text=resp.text,
                    odoo_url=self._manager.odoo_url,
                )
                self._record_log(
                    "ERROR",
                    f"Test print for '{name}' returned HTTP {resp.status_code}: "
                    f"{resp.text[:500]}",
                )
                self._messagebox.showerror("Test Print Failed", f"HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            self._test_warning = classify_test_print_error(
                printer, error_text=str(e), odoo_url=self._manager.odoo_url
            )
            self._record_log("ERROR", f"Test print failed for '{name}': {e}")
            self._messagebox.showerror("Test Print Failed", str(e))

    def _on_save(self) -> None:
        try:
            self._manager.odoo_url = self._url_var.get()
            self._manager.save()
            self._record_log("INFO", "Configuration saved.")
            self._messagebox.showinfo(
                "Saved",
                "Configuration saved. The running service will reload it automatically."
            )
        except ConfigManagerError as e:
            self._record_log("ERROR", f"Save failed: {e}")
            self._messagebox.showerror("Save Error", str(e))

    def _open_printer_form(self, existing: dict | None = None) -> None:
        """Open a dialog for adding or editing a printer."""
        tk, ttk, messagebox = self._tk, self._ttk, self._messagebox

        dialog = tk.Toplevel(self._root)
        dialog.title("Edit Printer" if existing else "Add Printer")
        dialog.geometry("400x350")
        dialog.transient(self._root)
        dialog.grab_set()

        is_edit = existing is not None

        # Name
        row = 0
        ttk.Label(dialog, text="Name:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        name_var = tk.StringVar(value=existing.get("name", "") if existing else "")
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=30)
        name_entry.grid(row=row, column=1, sticky=tk.EW, padx=5, pady=2)
        if is_edit:
            name_entry.configure(state="disabled")

        # Connection type
        row += 1
        ttk.Label(dialog, text="Connection Type:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        type_var = tk.StringVar(value=existing.get("connection_type", "network") if existing else "network")
        type_combo = ttk.Combobox(dialog, textvariable=type_var, values=["network", "usb", "ipp"], state="readonly")
        type_combo.grid(row=row, column=1, sticky=tk.EW, padx=5, pady=2)
        if is_edit:
            type_combo.configure(state="disabled")

        # Dynamic fields frame
        row += 1
        fields_frame = ttk.Frame(dialog)
        fields_frame.grid(row=row, column=0, columnspan=2, sticky=tk.NSEW, padx=5, pady=5)
        dialog.columnconfigure(1, weight=1)

        field_vars: dict[str, tk.StringVar] = {}

        def rebuild_fields(*args) -> None:
            for widget in fields_frame.winfo_children():
                widget.destroy()
            field_vars.clear()

            conn_type = type_var.get()
            fields = FIELDS_BY_TYPE.get(conn_type, [])

            for i, fdef in enumerate(fields):
                ttk.Label(fields_frame, text=f"{fdef.label}:").grid(
                    row=i, column=0, sticky=tk.W, padx=5, pady=2
                )
                var = tk.StringVar()
                if existing:
                    val = existing.get(fdef.name, "")
                    if fdef.field_type == "hex" and isinstance(val, int):
                        var.set(hex(val))
                    else:
                        var.set(str(val) if val is not None else "")
                entry = ttk.Entry(fields_frame, textvariable=var, width=30)
                entry.grid(row=i, column=1, sticky=tk.EW, padx=5, pady=2)
                field_vars[fdef.name] = var

        type_var.trace_add("write", rebuild_fields)
        rebuild_fields()

        # Buttons
        btn_row = row + 1
        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=btn_row, column=0, columnspan=2, pady=10)

        def on_ok() -> None:
            form_data = {
                "name": name_var.get().strip(),
                "connection_type": type_var.get(),
            }
            for fname, var in field_vars.items():
                val = var.get().strip()
                if val:
                    form_data[fname] = val

            try:
                data = extract_printer_data(form_data)
                if is_edit:
                    self._manager.update_printer(data["name"], data)
                else:
                    self._manager.add_printer(data)
                self._record_log("INFO", f"Saved printer '{data['name']}'.")
                self._refresh_printer_list()
                dialog.destroy()
            except ConfigManagerError as e:
                self._record_log("ERROR", f"Printer form error: {e}")
                messagebox.showerror("Validation Error", str(e), parent=dialog)

        ttk.Button(btn_frame, text="OK", command=on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def run(self) -> None:
        """Start the GUI event loop."""
        self._root.mainloop()


def main(argv: list[str] | None = None) -> int:
    """Entry point for the config GUI."""
    import argparse
    parser = argparse.ArgumentParser(description="Print Agent Configuration GUI")
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="Path to YAML config file (default: config.yaml)",
    )
    args = parser.parse_args(argv)

    gui = ConfigGUI(args.config)
    gui.run()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
