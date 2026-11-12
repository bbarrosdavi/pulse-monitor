"""CLI standalone para simular o Arduino Pro Micro + MAX30102 em porta serial virtual."""

from __future__ import annotations

import argparse
import signal
import sys
import time

from pulse_monitor.simulator.arduino_sim import VirtualArduinoSimulator
from pulse_monitor.simulator.ppg_model import Max30102SimConfig


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Simulador de Arduino Pro Micro + MAX30102 via porta serial virtual (PTY)."
    )
    parser.add_argument("--bpm", type=float, default=62.0, help="Frequência cardíaca alvo (BPM)")
    parser.add_argument("--spo2", type=float, default=98.0, help="Saturação de oxigênio alvo (%%)")
    parser.add_argument("--no-60hz", action="store_true", help="Desativa ruído de rede elétrica 60 Hz")
    parser.add_argument("--no-motion", action="store_true", help="Desativa deriva de movimento")
    args = parser.parse_args()

    cfg = Max30102SimConfig(
        bpm=args.bpm,
        spo2=args.spo2,
        noise_60hz=not args.no_60hz,
        motion_drift=not args.no_motion,
    )
    sim = VirtualArduinoSimulator(config=cfg)
    port = sim.start()
    print(f"Arduino Pro Micro (Simulado) ativo na porta serial virtual: {port}", flush=True)
    print("Pressione Ctrl+C para encerrar.", flush=True)

    running = True

    def _stop(_sig: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    try:
        while running:
            time.sleep(0.2)
    finally:
        sim.stop()
        print("\nSimulador encerrado.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
