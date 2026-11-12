"""Filtragem digital (Notch 60 Hz + Passa-Faixa) e extração de BPM e SpO2."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np
from scipy import signal

from pulse_monitor.protocol import PpgSample, SAMPLE_RATE_HZ


@dataclass
class DspConfig:
    """Configurações da cadeia de filtragem digital."""

    sample_rate_hz: float = float(SAMPLE_RATE_HZ)
    window_seconds: float = 8.0
    display_seconds: float = 4.0
    enable_notch_60hz: bool = True
    enable_bandpass: bool = True
    lowcut_hz: float = 0.5
    highcut_hz: float = 4.5


@dataclass(frozen=True, slots=True)
class DspMetrics:
    """Resultado do processamento sobre a janela atual de amostras."""

    time_axis: np.ndarray
    ppg_filtered: np.ndarray
    ppg_raw_ac: np.ndarray
    bpm: float
    spo2: float
    r_ratio: float
    perfusion_index_pct: float
    sample_count: int


class PpgSignalProcessor:
    """Aplica filtros digitais em tempo real e calcula BPM e SpO2."""

    def __init__(self, config: DspConfig | None = None) -> None:
        self.config = config or DspConfig()
        max_samples = int(self.config.sample_rate_hz * self.config.window_seconds)
        self._ir_buf: deque[float] = deque(maxlen=max_samples)
        self._red_buf: deque[float] = deque(maxlen=max_samples)
        self._total_samples = 0

        self._bpm_ema: float | None = None
        self._spo2_ema: float | None = None

        fs = self.config.sample_rate_hz
        self._b_notch, self._a_notch = signal.iirnotch(60.0, Q=30.0, fs=fs)
        self._b_bp, self._a_bp = signal.butter(
            3,
            [self.config.lowcut_hz, self.config.highcut_hz],
            btype="bandpass",
            fs=fs,
        )

    def reset(self) -> None:
        """Limpa os buffers internos e médias móveis."""
        self._ir_buf.clear()
        self._red_buf.clear()
        self._total_samples = 0
        self._bpm_ema = None
        self._spo2_ema = None

    def push_samples(self, samples: list[PpgSample]) -> None:
        """Adiciona novas amostras recebidas da porta serial."""
        for s in samples:
            self._ir_buf.append(float(s.ir_raw))
            self._red_buf.append(float(s.red_raw))
            self._total_samples += 1

    def _apply_filters(self, ac_signal: np.ndarray) -> np.ndarray:
        out = ac_signal
        if len(out) < 32:
            return out
        padlen = min(len(out) - 1, int(self.config.sample_rate_hz))
        if self.config.enable_notch_60hz:
            out = signal.filtfilt(self._b_notch, self._a_notch, out, padlen=padlen)
        if self.config.enable_bandpass:
            out = signal.filtfilt(self._b_bp, self._a_bp, out, padlen=padlen)
        return out

    def process(self) -> DspMetrics:
        """Executa filtragem digital e estima BPM e SpO2 na janela atual."""
        fs = self.config.sample_rate_hz
        display_len = int(fs * self.config.display_seconds)
        time_axis = np.linspace(0.0, self.config.display_seconds, display_len, endpoint=True)

        if len(self._ir_buf) < int(fs * 1.2):
            zeros = np.zeros(display_len, dtype=np.float64)
            return DspMetrics(
                time_axis=time_axis,
                ppg_filtered=zeros,
                ppg_raw_ac=zeros,
                bpm=self._bpm_ema or 0.0,
                spo2=self._spo2_ema or 0.0,
                r_ratio=0.0,
                perfusion_index_pct=0.0,
                sample_count=self._total_samples,
            )

        ir_raw = np.asarray(self._ir_buf, dtype=np.float64)
        red_raw = np.asarray(self._red_buf, dtype=np.float64)

        dc_ir = float(np.mean(ir_raw))
        dc_red = float(np.mean(red_raw))

        # Inverte polaridade óptica para exibir sístole positiva
        ir_ac_raw = -(ir_raw - dc_ir)
        red_ac_raw = -(red_raw - dc_red)

        ir_filt = self._apply_filters(ir_ac_raw)
        red_filt = self._apply_filters(red_ac_raw)

        # Descarta bordas de transitório do filtfilt quando janela está cheia
        valid_slice = slice(int(0.5 * fs), None) if len(ir_filt) > int(2.5 * fs) else slice(None)
        ir_valid = ir_filt[valid_slice]
        red_valid = red_filt[valid_slice]

        # Normaliza janela de 4s para faixa visual [-0.6, +0.45] dentro de [-1.0, 1.0]
        ir_tail = ir_filt[-display_len:]
        raw_tail = ir_ac_raw[-display_len:]

        p_low, p_high = np.percentile(ir_valid, [2.0, 98.0])
        span = max(float(p_high - p_low), 1e-6)
        # Escala mantendo forma fisiológica suave centrada em [-0.55, +0.40]
        scale = 0.88 / span if span > 10.0 else 0.0
        ppg_disp = np.clip((ir_tail - np.mean(ir_valid)) * scale - 0.08, -0.95, 0.95)
        raw_disp = np.clip((raw_tail - np.mean(raw_tail)) * scale - 0.08, -0.98, 0.98)

        if len(ppg_disp) < display_len:
            pad = display_len - len(ppg_disp)
            ppg_disp = np.pad(ppg_disp, (pad, 0), mode="constant")
            raw_disp = np.pad(raw_disp, (pad, 0), mode="constant")

        # Detecção de picos sistólicos para BPM
        prominence = max(0.35 * float(np.std(ir_valid)), 1e-3)
        peaks, _ = signal.find_peaks(
            ir_valid,
            distance=int(0.28 * fs),
            prominence=prominence,
        )
        bpm_inst = self._bpm_ema or 0.0
        if len(peaks) >= 2:
            ibis = np.diff(peaks) / fs
            valid_ibis = ibis[(ibis >= 0.30) & (ibis <= 2.00)]
            if len(valid_ibis) > 0:
                bpm_inst = 60.0 / float(np.median(valid_ibis))
                self._bpm_ema = bpm_inst if self._bpm_ema is None else (0.25 * bpm_inst + 0.75 * self._bpm_ema)

        # Razão de absorção Beer-Lambert R = (AC_red / DC_red) / (AC_ir / DC_ir)
        ac_ir_rms = float(np.std(ir_valid))
        ac_red_rms = float(np.std(red_valid))
        r_ratio = 0.0
        if dc_ir > 1.0 and dc_red > 1.0 and ac_ir_rms > 1.0:
            r_ratio = (ac_red_rms / dc_red) / (ac_ir_rms / dc_ir)
            spo2_inst = float(np.clip(110.0 - 25.0 * r_ratio, 70.0, 100.0))
            self._spo2_ema = spo2_inst if self._spo2_ema is None else (0.20 * spo2_inst + 0.80 * self._spo2_ema)

        pi_pct = (float(p_high - p_low) / dc_ir * 100.0) if dc_ir > 1.0 else 0.0

        return DspMetrics(
            time_axis=time_axis,
            ppg_filtered=ppg_disp,
            ppg_raw_ac=raw_disp,
            bpm=self._bpm_ema or 0.0,
            spo2=self._spo2_ema or 0.0,
            r_ratio=r_ratio,
            perfusion_index_pct=pi_pct,
            sample_count=self._total_samples,
        )
