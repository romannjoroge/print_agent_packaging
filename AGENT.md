# AGENT.md — Print Agent Packaging (Windows Service + Config GUI + Installer)

## Project Summary

Turn the existing `print_agent` Python project into a distributable Windows
`.exe` installer that a non-technical user can double-click to install. This
removes the current requirement for end users to install Git, Python, NSSM,
and manually edit a YAML file.

The finished product must:
1. Install as a self-contained package (no separate Python/pip install needed
   by the end user).
2. Register and run itself as a native Windows service (no NSSM dependency
   for end users — NSSM remains fine for your own dev/debug environment).
3. Provide a desktop GUI for configuring printers (replacing manual
   `config.yaml` editing).
4. Ship as a single installer `.exe` via a Start Menu shortcut.

This builds on top of the existing `print_agent` core (config loading,
connections, rendering, odoo_client, orchestrator — see that project's
AGENT.md/README). Do not re-implement that logic here; import and reuse it.

## Development Method: Test-Driven Development

Same hard requirement as the rest of this project: write a failing test
first, confirm it fails for the right reason, write the minimum code to pass
it, run the full suite, refactor, commit, then move on. Never write
implementation before its test.

**Testing constraint specific to this phase:** several pieces of this project
are inherently hard or impossible to unit test in the normal sense —
Windows service registration, the installer itself, and GUI rendering/click
behavior. Handle each category explicitly rather than skipping tests
silently:

- **Business logic behind the GUI/service (config read/write, validation,
  printer CRUD operations, service install/start/stop command construction)
  must be fully unit tested**, with the GUI framework and `pywin32`/Windows
  APIs mocked out. Structure code so this logic lives in plain functions/
  classes the GUI and service wrapper call into, not embedded inside GUI
  event handlers or `ServiceFramework` methods directly.
- **Windows service registration/lifecycle** (actually installing, starting,
  stopping a Windows service) cannot be meaningfully unit tested — mark these
  as manual verification steps (a checklist, not automated tests) and note
  them explicitly in your phase summary.
- **GUI interaction** (does clicking Save actually work): unit test the
  underlying save/validate functions; for the GUI wiring itself, a short
  manual test checklist is acceptable rather than automated UI testing,
  unless you choose a framework with good testing support (e.g. `pytest-qt`
  for PySide/PyQt) — if you do, use it and write real tests.
- **The installer** (Inno Setup output) cannot be unit tested at all — verify
  manually via a documented checklist (see Phase 5) and note results in your
  summary rather than skipping silently.

## Scope

### 1. Config manager module (`config_manager.py`)
- Wraps the existing `print_agent.config` loader with CRUD-style operations
  usable by both the GUI and any future CLI: `list_printers()`,
  `add_printer(printer)`, `update_printer(name, updates)`,
  `remove_printer(name)`, `save()`, `load()`.
- Validates input the same way the core config loader already does (reuse
  its validation, don't duplicate/diverge from it) — reject invalid
  connection-type-specific fields with clear error messages the GUI can
  display to the user.
- Test coverage: each CRUD operation, validation errors for both USB and
  network printer configs, round-trip save/load preserves data exactly,
  concurrent-edit safety is out of scope (single local user assumption) but
  overwriting an externally-modified file should at minimum not silently
  corrupt it — test that save() writes atomically (e.g. write to a temp file
  then replace) so a crash mid-save can't leave a half-written config.

### 2. Windows service wrapper (`service.py`)
- Uses `pywin32`'s `win32serviceutil.ServiceFramework` to wrap the existing
  `print_agent.orchestrator` poll loop as a proper Windows service (no NSSM).
- Must support the standard `install`, `remove`, `start`, `stop`, `debug`
  verbs via command line, matching `pywin32`'s conventional pattern (e.g.
  `print_agent_service.exe install`).
- On `SvcStop`, must signal the orchestrator loop to exit cleanly (not kill
  it abruptly) so in-flight jobs aren't left in an inconsistent ack state.
- Test coverage: the orchestrator's stop signal handling (already covered
  partly in the core project, extend if needed) is unit tested without
  `pywin32` involved. The actual service class itself is thin — cover
  argument parsing/dispatch logic if any exists beyond what `pywin32`
  provides; the install/start/stop lifecycle itself goes in the manual
  checklist (Phase 5), not automated tests.

### 3. Config GUI (`config_gui.py`)
- Choose one approach and document the choice + reasoning in your phase
  summary: `tkinter` (zero extra dependency, simpler, less polished) or
  `PySide6`/`pywebview` (nicer UI, bigger dependency, better testability
  with `pytest-qt` if using PySide6).
- Screens needed: list of configured printers (name, type, status), add/edit
  form (fields conditional on connection type — USB vs network), delete with
  confirmation, and a "Test Print" action that creates a test job the same
  way the Odoo module's Test Print button does (reuse/mirror that payload
  shape).
- On save, must trigger the running service to reload config — simplest
  approach: have the orchestrator poll-check the config file's mtime each
  cycle and reload if changed (extend the core project if this isn't already
  supported), rather than building new IPC. Document whichever approach you
  take.
- Test coverage: all form validation and save/delete logic goes through
  `config_manager.py` (already tested there) — GUI test coverage should
  focus on wiring (does the form call the right config_manager method with
  the right data), using `pytest-qt` if PySide6, or a manual checklist if
  tkinter.

### 4. PyInstaller packaging
- Two build targets from the same codebase:
  - `print_agent_service.exe` — runs `service.py`'s entrypoint.
  - `print_agent_config.exe` — runs `config_gui.py`'s entrypoint.
- `.spec` files checked into the repo (not just ad-hoc CLI flags) so builds
  are reproducible.
- Test coverage: not unit-testable in the traditional sense. Add this to the
  Phase 5 manual checklist — build both exes, run each standalone (outside
  the installer) on a clean Windows VM/machine without Python installed, and
  confirm they run without missing-dependency errors.

### 5. Inno Setup installer + manual verification checklist
- Inno Setup script that:
  - Installs both exes to `Program Files\PrintAgent\`.
  - Runs `print_agent_service.exe install` and `start` silently post-install.
  - Adds a Start Menu shortcut for `print_agent_config.exe` ("Configure
    Print Agent").
  - Ships a default/example `config.yaml` if none exists yet, so the GUI has
    something to load on first run.
  - Includes a clean uninstaller that stops and removes the service before
    deleting files.
- Not unit-testable. Document and execute this manual checklist before
  considering the phase done, and record results (pass/fail + notes) in your
  final summary:
  1. Fresh Windows VM, no Python/Git/NSSM installed.
  2. Run the installer — completes without error.
  3. Confirm service is running (`services.msc` or `Get-Service`) without
     manually starting it.
  4. Open the config GUI from the Start Menu shortcut, add a printer, save.
  5. Confirm the running service picks up the new printer (via log output or
     a Test Print) without manual restart, per whatever reload mechanism was
     built in Phase 3.
  6. Reboot the VM — confirm the service auto-starts and is running again
     without any user action.
  7. Run the uninstaller — confirm the service is stopped/removed and files
     are cleaned up.

## Project Structure (expected)

```
print_agent_packaging/
    config_manager.py
    service.py
    config_gui.py
    build/
        service.spec
        config_gui.spec
    installer/
        print_agent_installer.iss
    tests/
        test_config_manager.py
        test_service_logic.py       # non-pywin32-dependent logic only
        test_config_gui_wiring.py   # if using pytest-qt; else omit and
                                      # rely on manual checklist
    docs/
        manual_verification_checklist.md   # Phase 5 checklist, filled in
                                             # with results after each run
```

## Build Order

Work in this order; do not start a phase until the previous phase's automated
tests (where applicable) pass and any manual steps for that phase are
recorded:

1. `config_manager.py` — full TDD, this is the most testable and everything
   else depends on it.
2. `service.py` — TDD the non-pywin32 logic; manually verify install/start/
   stop/remove on a real Windows machine and record results.
3. `config_gui.py` — TDD wiring logic where the framework supports it;
   manual checklist otherwise.
4. PyInstaller packaging for both exes — manual verification on a clean VM.
5. Inno Setup installer — full manual checklist from section 5, executed on
   a clean VM with no dev tools installed.

## Constraints & Conventions

- Python 3.10+, consistent with the core `print_agent` project.
- Reuse the core project's config schema and orchestrator rather than
  forking/duplicating logic — this packaging layer wraps and ships the
  existing agent, it doesn't reimplement it.
- Keep GUI code free of business logic — every validation/save/delete
  operation should be callable and testable without the GUI framework
  imported.
- After each phase, summarize: what was built, what was automatically
  tested, what was manually verified (with results), and any deviations from
  this spec with reasoning.

## Out of Scope (do not build)

- macOS/Linux packaging (Windows only, for now).
- Auto-update mechanism for the installed agent.
- Code signing / certificate handling for the .exe (note if this becomes a
  blocker due to Windows SmartScreen warnings, but don't attempt to solve it
  without discussion first).
- Multi-language/localization support for the GUI.