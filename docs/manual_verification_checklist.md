# Manual Verification Checklist — Print Agent Packaging

## Phase 2: Windows Service (manual verification)

- [ ] `print_agent_service.exe install` registers the service in Windows Services
- [ ] `print_agent_service.exe start` starts the service (shows "Running" in services.msc)
- [ ] `print_agent_service.exe stop` stops the service cleanly (no orphan processes)
- [ ] `print_agent_service.exe remove` removes the service registration
- [ ] `print_agent_service.exe debug` runs in foreground with console output
- [ ] Service logs to Windows Event Log when running as a service
- [ ] Service auto-restarts after a crash (Windows recovery settings)

**Results:** _[To be filled after testing on Windows VM]_

---

## Phase 3: Config GUI (manual verification)

- [ ] GUI launches without errors from Start Menu shortcut
- [ ] Existing printers are listed correctly on startup
- [ ] "Add" button opens form with correct fields for each connection type
- [ ] "Edit" button populates form with existing printer data
- [ ] Form validation shows clear errors for missing required fields
- [ ] "Delete" button prompts for confirmation before removing
- [ ] "Save" writes config to disk and shows success message
- [ ] Running service picks up config changes without restart (via mtime polling)
- [ ] "Test Print" sends a job to the selected printer

**Results:** _[To be filled after testing on Windows VM]_

---

## Phase 4: PyInstaller Builds (manual verification)

- [ ] `print_agent_service.exe` runs on a clean Windows machine without Python installed
- [ ] `print_agent_config.exe` runs on a clean Windows machine without Python installed
- [ ] No missing dependency errors (DLL, module, etc.)
- [ ] Both exes are self-contained (no external Python packages needed)

**Results:** _[To be filled after testing on Windows VM]_

---

## Phase 5: Inno Setup Installer (full checklist)

Test on a **fresh Windows VM** with no Python, Git, or NSSM installed.

1. [ ] **Run the installer** — completes without error
2. [ ] **Service is running** — check via `services.msc` or `Get-Service PrintAgent` without manually starting it
3. [ ] **Config GUI from Start Menu** — open "Configure Print Agent" shortcut, add a printer, save
4. [ ] **Service picks up changes** — confirm via log output or Test Print without manual restart
5. [ ] **Reboot the VM** — confirm the service auto-starts and is running again without any user action
6. [ ] **Run the uninstaller** — confirm the service is stopped/removed and files are cleaned up
7. [ ] **No leftover files** — check that `Program Files\PrintAgent` is removed
8. [ ] **No leftover services** — confirm `PrintAgent` service is gone from services.msc

**Results:** _[To be filled after testing on Windows VM]_

---

## Notes

- Code signing is not implemented. Windows SmartScreen may show a warning
  on first run. This is expected and not a blocker for testing.
- The installer requires admin privileges (for service registration).
- The config file is preserved during uninstall (marked as `uninsneveruninstall`).
