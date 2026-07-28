"""Windows service wrapper for print_agent using winservicetools.

winservicetools handles all the pywin32/SCM plumbing (no pythonservice.exe,
no --pipe= detection, no ctypes hacks).  Install with:

    winservicetools.exe install --script C:\\path\\to\\service.py

Or run in foreground for development:

    python service.py
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading

logger = logging.getLogger("print_agent.service")


def _get_log_path() -> str:
    """Return a log file path next to the script/exe."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "print_agent_service.log")


def service_main(service_event: threading.Event) -> None:
    """Target function for the Windows service.

    Runs the orchestrator poll loop, checking service_event between cycles.
    When the service receives a stop request, winservicetools clears the
    event and this function exits cleanly.
    """
    from print_agent.config import Config, ConfigError
    from print_agent.orchestrator import Orchestrator

    config_path = "config.yaml"
    job_delay = 2.0

    # Set up file logging (no console when running as a service)
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        filename=_get_log_path(),
    )

    try:
        config = Config.from_file(config_path)
    except ConfigError as e:
        logger.error("Configuration error: %s", e)
        return

    logger.info("Print agent service starting with %d printer(s)", len(config.printers))
    orch = Orchestrator(config, job_delay=job_delay)

    while service_event.is_set():
        orch._poll_once()
        # Wait between cycles, but wake up immediately if stopped
        service_event.wait(timeout=job_delay)

    logger.info("Print agent service stopping")


def parse_service_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse foreground-mode CLI arguments (config path, verbose, job-delay)."""
    parser = argparse.ArgumentParser(description="Print Agent Service")
    parser.add_argument("-c", "--config", default="config.yaml")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--job-delay", type=float, default=2.0)
    return parser.parse_args(argv)


# --- Service class (only available when winservicetools is installed) ---

PrintAgentService = None

try:
    import winservicetools

    PrintAgentService = winservicetools.WindowsSvc.new_service(
        target=service_main,
        svc_name="PrintAgent",
        svc_display_name="Print Agent",
        svc_description="Polls Odoo for pending receipt print jobs and prints them.",
        svc_start="auto",
    )
except ImportError:
    pass


def main() -> int:
    """Entry point — start the service or run in foreground mode."""
    if sys.platform == "win32" and not sys.argv[1:] and PrintAgentService is not None:
        # No args: start as a Windows service (SCM mode)
        PrintAgentService.start()
        return 0

    # Foreground mode (development / non-Windows)
    args = parse_service_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    stop_event = threading.Event()

    def _handle_signal(signum, frame):
        logger.info("Received signal %d, shutting down", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    from print_agent.config import Config, ConfigError
    from print_agent.orchestrator import Orchestrator

    try:
        config = Config.from_file(args.config)
    except ConfigError as e:
        logger.error("Configuration error: %s", e)
        return 1

    logger.info("Print agent starting with %d printer(s)", len(config.printers))
    orch = Orchestrator(config, job_delay=args.job_delay)

    stop_event.set()  # starts in "running" state
    while stop_event.is_set():
        orch._poll_once()
        stop_event.wait(timeout=args.job_delay)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
