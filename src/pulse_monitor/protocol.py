"""Protocolo de comunicação serial entre Arduino Pro Micro e a IHM."""

from __future__ import annotations

from dataclasses import dataclass

SAMPLE_RATE_HZ = 200
BAUD_RATE = 115200


class SourceMode:
    """Identificadores de origem das amostras recebidas pela IHM."""

    REAL_SENSOR = 0
    ARDUINO_SIM_SENSOR = 1
    VIRTUAL_ARDUINO = 2

    @classmethod
    def label(cls, mode: int) -> str:
        return {
            cls.REAL_SENSOR: "Arduino Pro Micro + MAX30102",
            cls.ARDUINO_SIM_SENSOR: "Arduino Pro Micro (MAX30102 Simulado)",
            cls.VIRTUAL_ARDUINO: "Simulador Arduino + MAX30102",
        }.get(mode, "Desconhecido")


@dataclass(frozen=True, slots=True)
class PpgSample:
    """Amostra bruta de fotopletismografia (IR e Vermelho)."""

    timestamp_ms: int
    ir_raw: int
    red_raw: int
    mode: int = SourceMode.VIRTUAL_ARDUINO


def encode_sample(sample: PpgSample) -> str:
    """Serializa uma amostra para o formato ASCII da porta serial."""
    return f"PPG,{sample.timestamp_ms},{sample.ir_raw},{sample.red_raw},{sample.mode}\n"


def decode_sample(line: str) -> PpgSample | None:
    """Decodifica uma linha serial `PPG,<ms>,<ir>,<red>,<mode>`."""
    stripped = line.strip()
    if not stripped.startswith("PPG,"):
        return None
    parts = stripped.split(",")
    if len(parts) not in (4, 5):
        return None
    try:
        timestamp_ms = int(parts[1])
        ir_raw = int(parts[2])
        red_raw = int(parts[3])
        mode = int(parts[4]) if len(parts) == 5 else SourceMode.ARDUINO_SIM_SENSOR
    except ValueError:
        return None
    return PpgSample(
        timestamp_ms=timestamp_ms,
        ir_raw=ir_raw,
        red_raw=red_raw,
        mode=mode,
    )
