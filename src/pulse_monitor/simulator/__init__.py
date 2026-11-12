"""Simulador de Arduino Pro Micro e módulo MAX30102."""

from pulse_monitor.simulator.arduino_sim import VirtualArduinoSimulator
from pulse_monitor.simulator.ppg_model import Max30102SimConfig, Max30102Simulator

__all__ = ["Max30102SimConfig", "Max30102Simulator", "VirtualArduinoSimulator"]
