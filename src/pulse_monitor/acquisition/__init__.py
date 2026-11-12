"""Aquisição de dados via porta serial USB ou simulador PTY."""

from pulse_monitor.acquisition.serial_worker import SerialAcquisitionManager, list_serial_ports

__all__ = ["SerialAcquisitionManager", "list_serial_ports"]
