"""Emulador completo do Arduino Pro Micro conectado via porta serial virtual (PTY)."""

from __future__ import annotations

import os
import pty
import select
import termios
import threading
import time

from pulse_monitor.protocol import SAMPLE_RATE_HZ, encode_sample
from pulse_monitor.simulator.ppg_model import Max30102SimConfig, Max30102Simulator


class VirtualArduinoSimulator:
    """Emula um Arduino Pro Micro + MAX30102 escrevendo em uma porta PTY POSIX."""

    def __init__(
        self,
        config: Max30102SimConfig | None = None,
        sample_rate_hz: int = SAMPLE_RATE_HZ,
    ) -> None:
        self.config = config or Max30102SimConfig()
        self.sample_rate_hz = sample_rate_hz
        self.sensor = Max30102Simulator(self.config)

        self._master_fd: int | None = None
        self._slave_fd: int | None = None
        self.port_name: str | None = None

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._rx_buffer = ""

    def start(self) -> str:
        """Cria o par PTY e inicia a transmissão a 200 Hz. Retorna o caminho da porta."""
        if self._thread and self._thread.is_alive():
            assert self.port_name is not None
            return self.port_name

        master_fd, slave_fd = pty.openpty()
        # Modo raw no PTY para evitar eco e tradução de quebras de linha
        attrs = termios.tcgetattr(slave_fd)
        attrs[3] &= ~(termios.ECHO | termios.ICANON)
        termios.tcsetattr(slave_fd, termios.TCSANOW, attrs)

        self._master_fd = master_fd
        self._slave_fd = slave_fd
        self.port_name = os.ttyname(slave_fd)

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="VirtualArduinoPTY", daemon=True)
        self._thread.start()
        return self.port_name

    def stop(self) -> None:
        """Encerra a simulação e fecha os descritores da porta PTY."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        for fd_attr in ("_master_fd", "_slave_fd"):
            fd = getattr(self, fd_attr)
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
                setattr(self, fd_attr, None)
        self.port_name = None

    def update_config(
        self,
        *,
        bpm: float | None = None,
        spo2: float | None = None,
        noise_60hz: bool | None = None,
        motion_drift: bool | None = None,
    ) -> None:
        """Atualiza parâmetros fisiológicos e de ruído em tempo real."""
        with self._lock:
            if bpm is not None:
                self.config.bpm = max(30.0, min(200.0, float(bpm)))
            if spo2 is not None:
                self.config.spo2 = max(70.0, min(100.0, float(spo2)))
            if noise_60hz is not None:
                self.config.noise_60hz = bool(noise_60hz)
            if motion_drift is not None:
                self.config.motion_drift = bool(motion_drift)

    def _handle_command(self, cmd: str) -> None:
        if cmd == "PING":
            self._write_master(f"PONG,PULSE_MONITOR_V1,{self.config.mode}\n")
        elif cmd.startswith("SET_BPM:"):
            try:
                self.update_config(bpm=float(cmd.split(":", 1)[1]))
            except ValueError:
                pass
        elif cmd.startswith("SET_SPO2:"):
            try:
                self.update_config(spo2=float(cmd.split(":", 1)[1]))
            except ValueError:
                pass
        elif cmd.startswith("SET_NOISE60:"):
            self.update_config(noise_60hz=cmd.split(":", 1)[1].strip() != "0")
        elif cmd.startswith("SET_MOTION:"):
            self.update_config(motion_drift=cmd.split(":", 1)[1].strip() != "0")

    def _poll_commands(self) -> None:
        if self._master_fd is None:
            return
        readable, _, _ = select.select([self._master_fd], [], [], 0)
        if not readable:
            return
        try:
            chunk = os.read(self._master_fd, 256).decode("ascii", errors="ignore")
        except OSError:
            return
        self._rx_buffer += chunk
        while "\n" in self._rx_buffer:
            line, self._rx_buffer = self._rx_buffer.split("\n", 1)
            cmd = line.strip()
            if cmd:
                self._handle_command(cmd)

    def _write_master(self, text: str) -> None:
        if self._master_fd is None:
            return
        try:
            os.write(self._master_fd, text.encode("ascii"))
        except OSError:
            pass

    def _run_loop(self) -> None:
        dt_s = 1.0 / self.sample_rate_hz
        next_tick = time.perf_counter()

        while not self._stop_event.is_set():
            self._poll_commands()

            with self._lock:
                sample = self.sensor.step(dt_s)

            self._write_master(encode_sample(sample))

            next_tick += dt_s
            sleep_s = next_tick - time.perf_counter()
            if sleep_s > 0:
                time.sleep(sleep_s)
            elif sleep_s < -0.1:
                next_tick = time.perf_counter()
