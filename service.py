"""Windows service wrapper for print_agent using pywin32.

Provides ServiceStopEvent for clean shutdown signaling and
parse_service_args for service-specific CLI arguments.

The actual Windows service class (PrintAgentService) is only importable
on Windows with pywin32 installed — it's defined conditionally at the
bottom of this module.
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading


class ServiceStopEvent:
    """Thread-safe stop signal for the orchestrator.

    The Windows service's SvcStop handler calls signal(), and the
    orchestrator poll loop checks is_stopped or calls wait() between cycles.
    """

    def __init__(self) -> None:
        self._event = threading.Event()

    @property
    def is_stopped(self) -> bool:
        return self._event.is_set()

    def signal(self) -> None:
        self._event.set()

    def wait(self, timeout: float | None = None) -> None:
        self._event.wait(timeout=timeout)


def parse_service_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse service-specific CLI arguments (config path, verbose, job-delay)."""
    parser = argparse.ArgumentParser(
        description="Print Agent Windows Service"
    )
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="Path to YAML config file (default: config.yaml)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--job-delay",
        type=float,
        default=2.0,
        help="Seconds to wait between print jobs (default: 2.0)",
    )
    return parser.parse_args(argv)


def _run_orchestrator(config_path: str, job_delay: float, stop_event: ServiceStopEvent) -> None:
    """Run the orchestrator poll loop, checking stop_event between cycles."""
    from print_agent.config import Config, ConfigError
    from print_agent.orchestrator import Orchestrator

    logger = logging.getLogger("print_agent.service")

    try:
        config = Config.from_file(config_path)
    except ConfigError as e:
        logger.error("Configuration error: %s", e)
        return

    logger.info("Print agent service starting with %d printer(s)", len(config.printers))
    orch = Orchestrator(config, job_delay=job_delay)

    while not stop_event.is_stopped:
        orch._poll_once()
        # Wait between cycles, but wake up immediately if stopped
        stop_event.wait(timeout=job_delay)


# --- Windows-only service class ---
# Only import pywin32 on Windows to allow tests to run on any platform.

if sys.platform == "win32":
    try:
        import win32serviceutil
        import win32service
        import win32event
        import servicemanager

        class PrintAgentService(win32serviceutil.ServiceFramework):
            """Windows service wrapping the print_agent orchestrator."""

            _svc_name_ = "PrintAgent"
            _svc_display_name_ = "Print Agent"
            _svc_description_ = "Polls Odoo for pending receipt print jobs and prints them."

            def __init__(self, args) -> None:
                super().__init__(args)
                self._stop_event = ServiceStopEvent()
                self._stop_event_win = win32event.CreateEvent(None, 0, 0, None)

            def SvcStop(self) -> None:
                self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
                self._stop_event.signal()
                win32event.SetEvent(self._stop_event_win)

            def SvcDoRun(self) -> None:
                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_INFORMATION_TYPE,
                    servicemanager.PYS_SERVICE_STARTED,
                    (self._svc_name_, ""),
                )
                self._main()

            def _main(self) -> None:
                args = parse_service_args()
                _run_orchestrator(args.config, args.job_delay, self._stop_event)

    except ImportError:
        pass  # pywin32 not installed — service class unavailable


def main(argv: list[str] | None = None) -> int:
    """Entry point for the service executable.

    On Windows with pywin32: dispatches to win32serviceutil for
    install/remove/start/stop/debug verbs.

    On any platform: if no service verbs given, runs the orchestrator
    directly (useful for development/testing).
    """
    logger = logging.getLogger("print_agent.service")
    level = logging.DEBUG
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=level, format=fmt, stream=sys.stdout)

    if sys.platform == "win32":
        try:
            import win32serviceutil
            # If a service verb (install, remove, start, stop, debug) is
            # in the args, let pywin32 handle it.
            service_verbs = {"install", "remove", "start", "stop", "debug", "update"}
            cmd_args = argv if argv is not None else sys.argv[1:]
            if any(v in service_verbs for v in cmd_args):
                win32serviceutil.HandleCommandLine(PrintAgentService, argv=argv)
                return 0
        except ImportError:
            logger.warning("pywin32 not installed; running in foreground mode")

    # Foreground mode (development or non-Windows)
    args = parse_service_args(argv)
    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.INFO)

    stop_event = ServiceStopEvent()

    import signal

    def _handle_signal(signum, frame):
        logger.info("Received signal %d, shutting down", signum)
        stop_event.signal()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    _run_orchestrator(args.config, args.job_delay, stop_event)
    return 0


if __name__ == "__main__":
    sys.exit(main())
