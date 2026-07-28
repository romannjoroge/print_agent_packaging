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

from dataclasses import dataclass
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
        self._root = tk.Tk()
        self._root.title("Print Agent Configuration")
        self._root.geometry("700x500")
        self._root.minsize(600, 400)

        self._build_ui()
        self._refresh_printer_list()

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
                self._refresh_printer_list()
            except ConfigManagerError as e:
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

        try:
            import requests
            resp = requests.post(
                f"{self._manager.odoo_url}/receipt_printer/test_print",
                headers={"Authorization": f"Bearer {printer['api_key']}"},
                timeout=10,
            )
            if resp.status_code == 200:
                self._messagebox.showinfo("Test Print", f"Test print job sent to '{name}'.")
            else:
                self._messagebox.showerror("Test Print Failed", f"HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            self._messagebox.showerror("Test Print Failed", str(e))

    def _on_save(self) -> None:
        self._manager.odoo_url = self._url_var.get()
        try:
            self._manager.save()
            self._messagebox.showinfo(
                "Saved",
                "Configuration saved. The running service will reload it automatically."
            )
        except ConfigManagerError as e:
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
                self._refresh_printer_list()
                dialog.destroy()
            except ConfigManagerError as e:
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
