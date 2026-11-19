"""Leitor serial em thread dedicada compatível com Arduino Pro Micro USB e PTY simulado."""

from __future__ import annotations

import threading
import time
from collections import deque

import serial
from PySide6.QtCore import QObject, Signal
from serial.tools import list_ports

from pulse_monitor.protocol import BAUD_RATE, PpgSample, SourceMode, decode_sample
from pulse_monitor.simulator.arduino_sim import VirtualArduinoSimulator
from pulse_monitor.simulator.ppg_model import Max30102SimConfig


def list_serial_ports() -> list[tuple[str, str]]:
    """Retorna lista de portas seriais disponíveis como `(device, description)`."""
    ports: list[tuple[str, str]] = []
    for p in list_ports.comports():
        ports.append((p.device, p.description or p.device))
    return ports


def find_arduino_port() -> str | None:
    """Detecta automaticamente uma porta USB de Arduino Pro Micro / Leonardo conectada."""
    candidates = list(list_ports.comports())
    for p in candidates:
        desc = f"{p.description or ''} {p.manufacturer or ''}".lower()
        if p.vid == 0x2341 or "arduino" in desc or "leonardo" in desc or "sparkfun" in desc:
            return p.device
    for p in candidates:
        if p.device.startswith("/dev/ttyACM"):
            return p.device
    return None


class SerialAcquisitionManager(QObject):
    """Gerencia conexão serial com Arduino físico ou simulador Arduino+MAX30102."""

    status_changed = Signal(bool, str, int)  # connected, status_text, mode
    error_occurred = Signal(str)
    diagnostic_received = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._queue: deque[PpgSample] = deque(maxlen=4000)
        self._queue_lock = threading.Lock()

        self._stop_event = threading.Event()
        self._reader_thread: threading.Thread | None = None
        self._serial: serial.Serial | None = None

        self._simulator: VirtualArduinoSimulator | None = None
        self._use_virtual_arduino = True
        self._port_path: str | None = None
        self._last_mode = SourceMode.VIRTUAL_ARDUINO
        self._sim_config = Max30102SimConfig()

    @property
    def is_virtual_arduino(self) -> bool:
        return self._use_virtual_arduino

    @property
    def current_port(self) -> str | None:
        return self._port_path

    def start_virtual_arduino(self, prewarm_seconds: float = 0.0) -> list[PpgSample]:
        """Inicia o emulador de Arduino Pro Micro + MAX30102 e conecta via PTY serial."""
        self.stop()
        self._use_virtual_arduino = True
        self._simulator = VirtualArduinoSimulator(config=self._sim_config)
        prewarm: list[PpgSample] = []
        if prewarm_seconds > 0.0:
            dt = 1.0 / self._simulator.sample_rate_hz
            count = int(self._simulator.sample_rate_hz * prewarm_seconds)
            prewarm = [self._simulator.sensor.step(dt) for _ in range(count)]
        port = self._simulator.start()
        self._open_serial(port, SourceMode.VIRTUAL_ARDUINO, "Simulador Arduino + MAX30102")
        return prewarm

    def start_physical_serial(self, port: str, baudrate: int = BAUD_RATE) -> None:
        """Conecta a um Arduino Pro Micro físico pela porta USB serial."""
        self.stop()
        self._use_virtual_arduino = False
        self._open_serial(port, SourceMode.ARDUINO_SIM_SENSOR, f"Arduino USB ({port})", baudrate=baudrate)

    def stop(self) -> None:
        """Para a thread de leitura serial e o simulador se ativo."""
        self._stop_event.set()
        if self._serial is not None:
            try:
                self._serial.close()
            except OSError:
                pass
            self._serial = None
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=1.5)
        self._reader_thread = None

        if self._simulator is not None:
            self._simulator.stop()
            self._simulator = None

        self._port_path = None
        self.status_changed.emit(False, "Desconectado", self._last_mode)

    def drain_samples(self) -> list[PpgSample]:
        """Retira todas as amostras pendentes da fila de forma thread-safe."""
        with self._queue_lock:
            if not self._queue:
                return []
            items = list(self._queue)
            self._queue.clear()
            return items

    def update_simulation_params(
        self,
        *,
        bpm: float | None = None,
        spo2: float | None = None,
        noise_60hz: bool | None = None,
        motion_drift: bool | None = None,
    ) -> None:
        """Envia novos parâmetros para o simulador (ou via comandos seriais ao Arduino)."""
        if bpm is not None:
            self._sim_config.bpm = bpm
            self.send_command(f"SET_BPM:{bpm:.1f}")
        if spo2 is not None:
            self._sim_config.spo2 = spo2
            self.send_command(f"SET_SPO2:{spo2:.1f}")
        if noise_60hz is not None:
            self._sim_config.noise_60hz = noise_60hz
            self.send_command(f"SET_NOISE60:{1 if noise_60hz else 0}")
        if motion_drift is not None:
            self._sim_config.motion_drift = motion_drift
            self.send_command(f"SET_MOTION:{1 if motion_drift else 0}")

        if self._simulator is not None:
            self._simulator.update_config(
                bpm=bpm,
                spo2=spo2,
                noise_60hz=noise_60hz,
                motion_drift=motion_drift,
            )

    def send_command(self, cmd: str) -> None:
        """Envia um comando ASCII terminado por newline para o Arduino conectado."""
        if self._serial is not None and self._serial.is_open:
            try:
                self._serial.write((cmd.strip() + "\n").encode("ascii"))
            except (serial.SerialException, OSError):
                pass

    def _open_serial(self, port: str, default_mode: int, label: str, baudrate: int = BAUD_RATE) -> None:
        try:
            ser = serial.Serial(port=port, baudrate=baudrate, timeout=0.2)
            try:
                ser.dtr = True
            except (serial.SerialException, OSError):
                pass
        except (serial.SerialException, OSError) as exc:
            self.error_occurred.emit(f"Falha ao abrir {port}: {exc}")
            self.status_changed.emit(False, f"Erro em {port}", default_mode)
            return

        self._serial = ser
        self._port_path = port
        self._last_mode = default_mode
        self._stop_event.clear()
        self._reader_thread = threading.Thread(
            target=self._read_loop,
            args=(ser, default_mode),
            name="SerialReader",
            daemon=True,
        )
        self._reader_thread.start()
        self.status_changed.emit(True, label, default_mode)
        if not self._use_virtual_arduino:
            self.send_command("STATUS")
            self.send_command("PING")

    def _read_loop(self, ser: serial.Serial, default_mode: int) -> None:
        last_mode = default_mode
        while not self._stop_event.is_set():
            try:
                raw_line = ser.readline()
            except (serial.SerialException, OSError, TypeError) as exc:
                if not self._stop_event.is_set():
                    self.error_occurred.emit(f"Conexão serial interrompida: {exc}")
                    self.status_changed.emit(False, "Desconectado", last_mode)
                break

            if not raw_line:
                continue

            line = raw_line.decode("ascii", errors="ignore")
            sample = decode_sample(line)
            if sample is None:
                stripped = line.strip()
                if stripped.startswith(("STATUS,", "DIAG,", "ERR_REAL,", "PONG,")):
                    self.diagnostic_received.emit(stripped)
                continue

            if sample.mode != last_mode:
                last_mode = sample.mode
                self._last_mode = last_mode
                self.status_changed.emit(True, SourceMode.label(last_mode), last_mode)

            with self._queue_lock:
                self._queue.append(sample)

        time.sleep(0.01)
