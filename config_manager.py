"""CRUD operations wrapping print_agent.config for GUI and CLI use."""

from __future__ import annotations

import copy
import os
import tempfile
from pathlib import Path

import yaml

from print_agent.config import Config, ConfigError, _parse_printer


class ConfigManagerError(Exception):
    """Raised when a config manager operation fails."""


class ConfigManager:
    """CRUD-style config manager wrapping print_agent's config loader.

    Stores config as a plain dict internally for easy manipulation,
    validates through print_agent.config._parse_printer on add/update,
    and writes atomically on save.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._data: dict = {}
        self.load()

    def load(self) -> None:
        """Load (or reload) config from disk, validating the result."""
        if not self._path.exists():
            raise ConfigManagerError(f"Config file not found: {self._path}")

        try:
            raw = yaml.safe_load(self._path.read_text())
        except yaml.YAMLError as e:
            raise ConfigManagerError(f"Invalid YAML in {self._path}: {e}") from e

        if not isinstance(raw, dict):
            raise ConfigManagerError(
                f"Config must be a YAML mapping, got {type(raw).__name__}"
            )

        if "odoo_url" not in raw or not raw["odoo_url"]:
            raise ConfigManagerError("Missing required field: 'odoo_url'")

        if "printers" not in raw:
            raise ConfigManagerError("Missing required field: 'printers'")

        if not isinstance(raw["printers"], list):
            raise ConfigManagerError("'printers' must be a list")

        # Validate each printer through core validation
        for i, p in enumerate(raw["printers"]):
            try:
                _parse_printer(p, index=i)
            except ConfigError as e:
                raise ConfigManagerError(str(e)) from e

        self._data = copy.deepcopy(raw)

    @property
    def odoo_url(self) -> str:
        return self._data.get("odoo_url", "")

    @odoo_url.setter
    def odoo_url(self, value: str) -> None:
        if not value:
            raise ConfigManagerError("odoo_url cannot be empty")
        self._data["odoo_url"] = value

    def list_printers(self) -> list[dict]:
        """Return a copy of all printer configs as dicts."""
        return copy.deepcopy(self._data.get("printers", []))

    def add_printer(self, printer: dict) -> None:
        """Add a printer after validating it through core config validation."""
        printers = self._data.setdefault("printers", [])

        name = printer.get("name")
        if not name:
            raise ConfigManagerError("Printer must have a 'name'")

        if any(p["name"] == name for p in printers):
            raise ConfigManagerError(f"Printer '{name}' already exists")

        if not printer.get("api_key"):
            raise ConfigManagerError(f"Printer '{name}' must have an 'api_key'")

        # Validate through core parser
        try:
            _parse_printer(printer, index=len(printers))
        except ConfigError as e:
            raise ConfigManagerError(str(e)) from e

        printers.append(copy.deepcopy(printer))

    def update_printer(self, name: str, updates: dict) -> None:
        """Update fields on an existing printer by name, re-validating."""
        printers = self._data.get("printers", [])
        idx = None
        for i, p in enumerate(printers):
            if p["name"] == name:
                idx = i
                break

        if idx is None:
            raise ConfigManagerError(f"Printer '{name}' not found")

        merged = {**printers[idx], **updates}

        # Validate merged result through core parser
        try:
            _parse_printer(merged, index=idx)
        except ConfigError as e:
            raise ConfigManagerError(str(e)) from e

        printers[idx] = merged

    def remove_printer(self, name: str) -> None:
        """Remove a printer by name."""
        printers = self._data.get("printers", [])
        for i, p in enumerate(printers):
            if p["name"] == name:
                printers.pop(i)
                return
        raise ConfigManagerError(f"Printer '{name}' not found")

    def save(self, path: str | Path | None = None) -> None:
        """Save config atomically: write to temp file, then replace.

        If path is None, saves to the original file path.
        """
        target = Path(path) if path else self._path
        target.parent.mkdir(parents=True, exist_ok=True)

        content = yaml.dump(
            self._data, default_flow_style=False, sort_keys=False
        )

        # Atomic write: write to temp file in same directory, then replace
        fd, tmp_path = tempfile.mkstemp(
            dir=target.parent, suffix=".tmp", prefix=".config_"
        )
        try:
            with os.fdopen(fd, "w") as f:
                f.write(content)
            os.replace(tmp_path, target)
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
