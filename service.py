"""Windows service wrapper for print_agent using winservicetools.

Development:  winservicetools.exe install --script service.py
Frozen exe:   print_agent_service.exe install
Start/stop:   sc.exe start/stop/delete PrintAgent
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading

try:
    import winservicetools
except ImportError:
    winservicetools = None

logger = logging.getLogger("print_agent.service")

if getattr(sys, "frozen", False):
    _here = os.path.dirname(sys.executable)
else:
    _here = os.path.dirname(os.path.abspath(__file__))

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    filename=os.path.join(_here, "print_agent_service.log"),
    filemode="a",
)


def service_main(service_event: threading.Event) -> None:
    """Runs the orchestrator poll loop. Exits when service_event is cleared.

    Checks the config file's mtime each cycle — if it changed (e.g. the GUI
    saved new settings), reloads the config and recreates the orchestrator.
    """
    from print_agent.config import Config, ConfigError
    from print_agent.orchestrator import Orchestrator

    config_path = os.path.join(_here, "config.yaml")
    job_delay = 2.0

    def _load_orchestrator() -> Orchestrator:
        config = Config.from_file(config_path)
        logger.info("Loaded config with %d printer(s)", len(config.printers))
        return Orchestrator(config, job_delay=job_delay)

    try:
        orch = _load_orchestrator()
    except ConfigError as e:
        logger.error("Configuration error: %s", e)
        return

    last_mtime = os.path.getmtime(config_path)

    while service_event.is_set():
        # Check if config file changed
        try:
            current_mtime = os.path.getmtime(config_path)
            if current_mtime != last_mtime:
                logger.info("Config file changed, reloading...")
                try:
                    orch = _load_orchestrator()
                    last_mtime = current_mtime
                    logger.info("Config reloaded successfully")
                except ConfigError as e:
                    logger.error("Failed to reload config: %s", e)
                    # Keep running with the old config
        except OSError:
            pass  # File temporarily unavailable during save

        orch._poll_once()
        service_event.wait(timeout=job_delay)

    logger.info("Print agent service stopping")


# --- Service class via winservicetools ---

PrintAgentService = None

if winservicetools is not None:
    PrintAgentService = winservicetools.WindowsSvc.new_service(
        target=service_main,
        svc_name="PrintAgent",
        svc_display_name="Print Agent",
        svc_description="Polls Odoo for pending receipt print jobs and prints them.",
        svc_start="auto",
    )


# --- Install/remove for frozen exe (Win32 API, no sc.exe quoting issues) ---

def _frozen_install():
    """Register the frozen exe as the service binary via Win32 API."""
    import ctypes

    HANDLE = ctypes.c_void_p
    SC_MANAGER_ALL_ACCESS = 0xF003F
    SERVICE_ALL_ACCESS = 0xF01FF
    SERVICE_WIN32_OWN_PROCESS = 0x10
    SERVICE_AUTO_START = 0x2
    SERVICE_ERROR_NORMAL = 0x1

    binary_path = f'"{sys.executable}"'

    advapi32 = ctypes.windll.advapi32
    advapi32.OpenSCManagerW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    advapi32.OpenSCManagerW.restype = HANDLE
    advapi32.CreateServiceW.argtypes = [
        HANDLE, ctypes.c_wchar_p, ctypes.c_wchar_p,
        ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32,
        ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p,
        ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
    ]
    advapi32.CreateServiceW.restype = HANDLE
    advapi32.CloseServiceHandle.argtypes = [HANDLE]
    advapi32.CloseServiceHandle.restype = ctypes.c_int
    advapi32.ChangeServiceConfig2W.argtypes = [HANDLE, ctypes.c_uint32, ctypes.c_void_p]
    advapi32.ChangeServiceConfig2W.restype = ctypes.c_int

    scm = advapi32.OpenSCManagerW(None, None, SC_MANAGER_ALL_ACCESS)
    if not scm:
        raise OSError(f"OpenSCManager failed: {ctypes.GetLastError()}")

    try:
        svc = advapi32.CreateServiceW(
            scm, "PrintAgent", "Print Agent",
            SERVICE_ALL_ACCESS, SERVICE_WIN32_OWN_PROCESS,
            SERVICE_AUTO_START, SERVICE_ERROR_NORMAL,
            binary_path, None, None, None, None, None,
        )
        if not svc:
            raise OSError(f"CreateService failed: {ctypes.GetLastError()}")
        try:
            class SERVICE_DESCRIPTION(ctypes.Structure):
                _fields_ = [("lpDescription", ctypes.c_wchar_p)]
            desc = SERVICE_DESCRIPTION()
            desc.lpDescription = "Polls Odoo for pending receipt print jobs and prints them."
            advapi32.ChangeServiceConfig2W(svc, 1, ctypes.byref(desc))
        finally:
            advapi32.CloseServiceHandle(svc)
    finally:
        advapi32.CloseServiceHandle(scm)

    print(f"Service installed. Binary path: {binary_path}")


def _frozen_remove():
    """Remove the service via sc.exe delete."""
    subprocess.run(["sc.exe", "stop", "PrintAgent"], capture_output=True)
    subprocess.run(["sc.exe", "delete", "PrintAgent"], capture_output=True)
    print("Service removed.")


# --- Entry point ---

if __name__ == "__main__":
    args = sys.argv[1:]

    if "install" in args:
        if getattr(sys, "frozen", False):
            _frozen_install()
        elif PrintAgentService is not None:
            PrintAgentService.install(scriptpath=os.path.abspath(__file__))
        else:
            print("winservicetools not installed.")
            sys.exit(1)

    elif "remove" in args:
        if getattr(sys, "frozen", False):
            _frozen_remove()
        elif PrintAgentService is not None:
            PrintAgentService.delete()
        else:
            print("winservicetools not installed.")
            sys.exit(1)

    else:
        # SCM mode — enter the service dispatcher
        if PrintAgentService is not None:
            PrintAgentService.start()
        else:
            print("winservicetools not installed.")
            sys.exit(1)
