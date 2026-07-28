# Manual Verification Checklist — Print Agent Packaging

## Prerequisites: Setting Up a Test Environment

### Option A: Windows VM (recommended)

1. **Create a Windows VM** — Hyper-V, VirtualBox, or VMware. Windows 10/11
   evaluation ISOs work fine. Allocate at least 2 CPU cores, 4 GB RAM, 40 GB disk.
2. **Do NOT install** Python, Git, NSSM, or any dev tools. The whole point is
   to verify the installer works from a clean state.
3. **Take a snapshot** after initial setup so you can revert between test runs.
4. **Enable PowerShell** — open PowerShell as Administrator (right-click Start →
   "Windows PowerShell (Admin)") for the commands below.

### Option B: Physical Windows machine

Same as above, but you'll need to manually uninstall Python/Git/NSSM first if
they're present, and you won't be able to snapshot/revert easily.

---

## Phase 2: Windows Service (manual verification)

### Prerequisites

The service uses `winservicetools` (pip install winservicetools). Install it
into your Python environment before testing. No PyInstaller exe is needed
for the service — winservicetools handles registration using `pythonw.exe`
directly.

```powershell
pip install winservicetools
```

### Step-by-step

#### 2.1 Install the service

```powershell
# From an elevated (Admin) PowerShell:
cd "C:\path\to\print_agent_packaging"
winservicetools.exe install --script "C:\path\to\print_agent_packaging\service.py"
```

**Expected:** Output says the service was installed. No error messages.

**Verify:**
```powershell
Get-Service PrintAgent
```
**Expected:** Status shows `Stopped`, Name is `PrintAgent`.

- [X] Service registered successfully

#### 2.2 Start the service

```powershell
sc.exe start PrintAgent
```

**Expected:** Output or no error. Check status:
```powershell
Get-Service PrintAgent
```
**Expected:** Status shows `Running`.

Also check `services.msc`:
1. Press `Win+R`, type `services.msc`, press Enter.
2. Find "Print Agent" in the list.
3. Status should be "Running", Startup Type should be "Automatic".

- [X] Service shows "Running" in services.msc

#### 2.3 Check service log file

The service logs to `print_agent_service.log` in the same directory as
`service.py`. Check it for startup messages:

```powershell
Get-Content "C:\path\to\print_agent_packaging\print_agent_service.log"
```

**Expected:** Shows "starting with N printer(s)" or a config error if
`config.yaml` is missing/invalid.

- [X] Service log file shows startup messages

#### 2.4 Stop the service

```powershell
sc.exe stop PrintAgent
```

**Expected:** Status changes to `Stopped`.

```powershell
Get-Service PrintAgent
```

Also verify no orphan processes:
```powershell
Get-Process -Name "pythonw" -ErrorAction SilentlyContinue
```
**Expected:** No results (process fully terminated).

- [X] Service stops cleanly, no orphan processes

#### 2.5 Remove the service

```powershell
sc.exe delete PrintAgent
```

**Expected:** Service is removed.

```powershell
Get-Service PrintAgent -ErrorAction SilentlyContinue
```
**Expected:** "Cannot find any service with service name 'PrintAgent'".

- [X] Service removed from Windows

#### 2.6 Run in foreground (development/debug)

```powershell
python service.py
```

**Expected:** Runs in foreground, prints log output to the console. Press
`Ctrl+C` to stop. Useful for development troubleshooting.

- [ ] Foreground mode runs with console output

#### 2.7 Auto-restart on crash (optional advanced test)

Windows services can be configured to auto-restart. To verify:

1. Install and start the service (steps 2.1–2.2).
2. Find the service PID:
   ```powershell
   (Get-Service PrintAgent).Id
   ```
3. Kill it forcefully:
   ```powershell
   Stop-Process -Id <PID> -Force
   ```
4. Wait 30 seconds, then check:
   ```powershell
   Get-Service PrintAgent
   ```
   **Expected:** Status returns to `Running` (Windows restarted it).

- [ ] Service auto-restarts after forced crash

---

## Phase 3: Config GUI (manual verification)

### Prerequisites

You need either the built `print_agent_config.exe` (Phase 4) or Python with
tkinter available. The exe is preferred for testing the real user experience.

### Step-by-step

#### 3.1 Launch the GUI

**From the installer (after Phase 5):**
- Click Start → "Configure Print Agent"

**From the exe directly:**
```powershell
cd "C:\path\to\print_agent_packaging\dist"
.\print_agent_config.exe
```

**From Python (dev only):**
```powershell
cd "C:\path\to\print_agent_packaging"
python config_gui.py
```

**Expected:** A window opens titled "Print Agent Configuration" showing:
- An "Odoo Connection" section with a URL field
- A "Printers" section with a table (may be empty)
- Buttons: Add, Edit, Delete, Test Print, Save

- [ ] GUI launches without errors

#### 3.2 Verify existing printers load

If `config.yaml` exists next to the exe (or in the working directory), the
printers defined in it should appear in the table.

**Expected:** Each printer shows Name, Type, and Host/Device columns.

- [ ] Existing printers listed correctly

#### 3.3 Add a network printer

1. Click **Add**.
2. A dialog opens titled "Add Printer".
3. Fill in:
   - **Name:** `test_printer`
   - **Connection Type:** `Network (ESC/POS)` (should be selected by default)
   - **Host:** `192.168.1.200`
   - **Port:** `9100`
   - **API Key:** `test-api-key-123`
4. Click **OK**.

**Expected:** The dialog closes. `test_printer` appears in the printer list
table with type "network" and host "192.168.1.200".

- [ ] Network printer added successfully

#### 3.4 Add a USB printer

1. Click **Add**.
2. Change **Connection Type** to `USB`.
3. **Observe:** The form fields should change — Host/Port disappear, and
   Vendor ID, Product ID, Device Path, and API Key appear.
4. Fill in:
   - **Name:** `usb_receipt`
   - **Vendor ID:** `0x0456`
   - **Product ID:** `0x0808`
   - **API Key:** `usb-key-456`
5. Click **OK**.

**Expected:** `usb_receipt` appears in the list with type "usb".

- [ ] USB printer added, form fields change by connection type

#### 3.5 Add an IPP printer

1. Click **Add**.
2. Change **Connection Type** to `IPP`.
3. **Observe:** Fields change to Host, Port, Printer URI, API Key.
4. Fill in:
   - **Name:** `hp_office`
   - **Host:** `192.168.1.50`
   - **Port:** `631`
   - **API Key:** `ipp-key-789`
5. Click **OK**.

**Expected:** `hp_office` appears in the list with type "ipp".

- [ ] IPP printer added successfully

#### 3.6 Edit an existing printer

1. Click on `test_printer` in the list to select it.
2. Click **Edit**.
3. A dialog opens pre-filled with `test_printer`'s current values.
4. **Observe:** Name and Connection Type fields are disabled (read-only).
5. Change the Host to `10.0.0.50`.
6. Click **OK**.

**Expected:** The list updates to show the new host `10.0.0.50`.

- [ ] Edit dialog pre-fills correctly, changes applied

#### 3.7 Validation errors

1. Click **Add**.
2. Leave Name empty, fill in other fields, click **OK**.
3. **Expected:** An error dialog appears saying the printer must have a name.
4. Try adding a printer with a name that already exists (e.g., `test_printer`).
5. **Expected:** Error saying the printer already exists.
6. Try adding a network printer with no host.
7. **Expected:** Error about missing host.

- [ ] Validation shows clear error messages

#### 3.8 Delete a printer

1. Select `hp_office` in the list.
2. Click **Delete**.
3. **Expected:** A confirmation dialog asks "Delete printer 'hp_office'?"
4. Click **No** — printer should remain.
5. Click **Delete** again, then **Yes**.
6. **Expected:** `hp_office` disappears from the list.

- [ ] Delete prompts for confirmation, removes printer on Yes

#### 3.9 Save configuration

1. Click **Save**.
2. **Expected:** A success dialog says "Configuration saved. The running
   service will reload it automatically."
3. Open `config.yaml` in a text editor (Notepad is fine).
4. **Verify:** The file contains all the printers you added/edited, with
   correct values and valid YAML format.

- [ ] Save writes valid config to disk

#### 3.10 Service picks up changes (config reload via mtime)

1. Make sure the service is running:
   ```powershell
   Get-Service PrintAgent
   ```
2. In the GUI, add or edit a printer and click **Save**.
3. Wait 5–10 seconds (the orchestrator polls on an interval).
4. Check `print_agent_service.log` for new entries mentioning the printer.

**Expected:** The service picks up the config change without needing a
manual restart.

- [ ] Service reloads config automatically after GUI save

#### 3.11 Test Print

1. Select a printer in the list that has a valid Odoo URL and API key
   configured.
2. Click **Test Print**.
3. **Expected (if Odoo is reachable):** A dialog says "Test print job sent
   to '<name>'." The printer should print a test receipt.
4. **Expected (if Odoo is NOT reachable):** An error dialog with connection
   details — this is fine for testing the GUI wiring.

- [ ] Test Print sends job (or shows appropriate error)

---

## Phase 4: PyInstaller Builds (manual verification)

### Prerequisites

You need a machine with Python 3.10+ and PyInstaller installed:
```powershell
pip install pyinstaller
```

Also install the print_agent dependencies:
```powershell
cd C:\path\to\print_agent
pip install -r requirements.txt
```

### Step-by-step

#### 4.1 Build the config GUI exe

```powershell
cd C:\path\to\print_agent_packaging
pyinstaller build/config_gui.spec
```

**Expected:** Build completes without errors. Output is in `dist/`:
- `dist/print_agent_config.exe`

Note: With winservicetools, no service exe is needed. The service runs as
`pythonw.exe service.py` directly.

- [X] Config GUI exe built successfully

#### 4.2 Test on a clean machine

Copy the config GUI exe to a Windows machine that does **NOT** have Python
installed (use your test VM).

```powershell
# On the clean VM:
mkdir C:\TestPrintAgent
# Copy print_agent_config.exe there
# Also copy a config.yaml
```

#### 4.3 Test the config GUI exe

```powershell
cd C:\TestPrintAgent
.\print_agent_config.exe
```

**Expected:** The GUI window opens without errors. You should see the
"Print Agent Configuration" window with Odoo URL field and printer list.

Close the window when done.

- [X] Config GUI exe runs on clean machine without Python

#### 4.4 Check exe size

Right-click the exe → Properties. It should be roughly 10–30 MB
(PyInstaller bundles the Python interpreter and all dependencies).

If it's under 1 MB, something went wrong with the build.

- [X] Exe size is reasonable (10–30 MB)

---

## Phase 5: Inno Setup Installer (full end-to-end checklist)

### Prerequisites

1. **Install Inno Setup 6+** on your dev machine: https://jrsoftware.org/isinfo.php
2. **Build the config GUI exe** (Phase 4).
3. **Copy `config.example.yaml`** to the `print_agent_packaging` root if not
   already there.
4. **Take a VM snapshot** before testing so you can revert and re-test.

### Step-by-step

#### 5.1 Build the installer

```powershell
cd C:\path\to\print_agent_packaging
# Open the .iss file in Inno Setup and click Build → Compile
# Or from command line:
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\print_agent_installer.iss
```

**Expected:** Output is `installer_output/PrintAgentSetup.exe`.

- [X] Installer built successfully

#### 5.2 Run the installer on a fresh VM

1. Revert your VM to the clean snapshot (no Python, no dev tools).
2. Copy `PrintAgentSetup.exe` to the VM.
3. Right-click → **Run as administrator**.
4. Click through the installer wizard.
5. **Expected:** Installer completes without errors.

- [X] Installer completed without errors

#### 5.3 Verify service is running

Open PowerShell as Admin:
```powershell
Get-Service PrintAgent
```

**Expected:** Status is `Running`.

- [ ] Service is running after install

#### 5.4 Verify Start Menu shortcut

1. Open the Start Menu.
2. Look for a "Print Agent" folder.
3. Inside, you should see "Configure Print Agent".
4. Click it.

**Expected:** The config GUI opens.

- [ ] Start Menu shortcut works, GUI opens

#### 5.5 Add a printer via the GUI

1. In the GUI, click **Add**.
2. Fill in a test printer and click **Save**.

- [ ] Can add and save a printer via GUI

#### 5.6 Reboot and verify auto-start

1. Restart the VM.
2. After boot, check:
   ```powershell
   Get-Service PrintAgent
   ```
3. **Expected:** Status is `Running`.

- [ ] Service auto-starts after reboot

#### 5.7 Run the uninstaller

1. Open Settings → Apps → Apps & features.
2. Find "Print Agent" and click **Uninstall**.

- [ ] Uninstaller runs without errors

#### 5.8 Verify clean uninstall

```powershell
Get-Service PrintAgent -ErrorAction SilentlyContinue
# Expected: service doesn't exist

Test-Path "C:\Program Files\PrintAgent"
# Expected: False (directory removed)
```

- [ ] Service removed, files cleaned up
- [ ] Config file preserved (if modified)

---

## Recording Results

After completing each phase, fill in the results:

```
**Results:**
- Date: YYYY-MM-DD
- Tester: <name>
- Environment: <VM snapshot name or machine description>
- Status: PASS / PARTIAL / FAIL
- Notes: <any issues encountered>
```

## Troubleshooting

### Service fails to start
- Check `print_agent_service.log` in the same directory as `service.py`.
- Try running `python service.py` in foreground mode to see errors directly.

### GUI doesn't show printers
- Verify `config.yaml` exists and contains valid YAML.
- Try running the GUI from a terminal to see error output.

### SmartScreen warning
- Click "More info" → "Run anyway". Expected without code signing.

### Service doesn't pick up config changes
- The orchestrator checks config file mtime on each poll cycle.
- Wait at least one full poll cycle (default: a few seconds).
