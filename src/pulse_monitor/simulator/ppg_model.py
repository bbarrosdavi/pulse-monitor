"""Modelo fisiológico de PPG e simulação óptica do sensor MAX30102."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from pulse_monitor.protocol import PpgSample, SourceMode


@dataclass
class Max30102SimConfig:
    """Parâmetros configuráveis do sensor óptico MAX30102 simulado."""

    bpm: float = 62.0
    spo2: float = 98.0
    noise_60hz: bool = True
    motion_drift: bool = True
    shot_noise_std: float = 12.0
    hrv_enabled: bool = True
    mode: int = SourceMode.VIRTUAL_ARDUINO


def _gaussian(phase: float, center: float, width: float) -> float:
    d = (phase - center) / width
    return math.exp(-0.5 * d * d)


class Max30102Simulator:
    """Gera amostras brutas de 18 bits (IR e Red) fiéis ao MAX30102."""

    DC_IR = 100_000.0
    DC_RED = 85_000.0
    AC_IR = 1_250.0

    def __init__(self, config: Max30102SimConfig | None = None, seed: int | None = 42) -> None:
        self.config = config or Max30102SimConfig()
        self._rng = random.Random(seed)
        self._phase = 0.0
        self._elapsed_s = 0.0
        self._beat_amp_scale = 1.0

    def step(self, dt_s: float) -> PpgSample:
        """Avança o modelo em `dt_s` segundos e retorna uma amostra bruta."""
        self._elapsed_s += dt_s

        # Variabilidade fisiológica sutil da frequência cardíaca (~±1.5% respiratória)
        hrv_mod = 1.0 + 0.015 * math.sin(2.0 * math.pi * 0.20 * self._elapsed_s) if self.config.hrv_enabled else 1.0
        freq_hz = (self.config.bpm * hrv_mod) / 60.0

        prev_phase = self._phase
        self._phase = (self._phase + freq_hz * dt_s) % 1.0
        if self._phase < prev_phase:
            self._beat_amp_scale = self._rng.uniform(0.95, 1.06) if self.config.hrv_enabled else 1.0

        # Morfologia PPG suave: pico sistólico + onda dicrótica + base diastólica
        systolic = 1.00 * _gaussian(self._phase, 0.25, 0.085)
        dicrotic = 0.34 * _gaussian(self._phase, 0.48, 0.115)
        diastolic = 0.10 * _gaussian(self._phase, 0.72, 0.100)
        pulse = self._beat_amp_scale * ((systolic + dicrotic + diastolic) - 0.34)

        # Relação Beer-Lambert calibrada: SpO2 = 110 - 25 * R
        r_ratio = max(0.08, (110.0 - self.config.spo2) / 25.0)
        ac_red = r_ratio * (self.AC_IR / self.DC_IR) * self.DC_RED

        noise_60 = (
            180.0 * math.sin(2.0 * math.pi * 60.0 * self._elapsed_s)
            if self.config.noise_60hz
            else 0.0
        )
        motion = (
            320.0 * math.sin(2.0 * math.pi * 0.22 * self._elapsed_s)
            + 90.0 * math.sin(2.0 * math.pi * 0.37 * self._elapsed_s)
            if self.config.motion_drift
            else 0.0
        )

        shot_ir = self._rng.gauss(0.0, self.config.shot_noise_std) if self.config.shot_noise_std > 0 else 0.0
        shot_red = self._rng.gauss(0.0, self.config.shot_noise_std * 0.9) if self.config.shot_noise_std > 0 else 0.0

        # Absorção óptica inversa: maior volume arterial reduz luz transmitida/refletida
        ir_val = self.DC_IR - self.AC_IR * pulse + noise_60 + motion + shot_ir
        red_val = self.DC_RED - ac_red * pulse + 0.85 * noise_60 + 0.85 * motion + shot_red

        ir_raw = max(0, min(262_143, int(round(ir_val))))
        red_raw = max(0, min(262_143, int(round(red_val))))
        timestamp_ms = int(round(self._elapsed_s * 1000.0))

        return PpgSample(
            timestamp_ms=timestamp_ms,
            ir_raw=ir_raw,
            red_raw=red_raw,
            mode=self.config.mode,
        )
