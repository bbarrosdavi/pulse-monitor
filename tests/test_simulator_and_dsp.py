"""Testes do simulador Arduino Pro Micro + MAX30102 e cadeia DSP."""

from __future__ import annotations

import time

import numpy as np
import serial

from pulse_monitor.dsp.processor import PpgSignalProcessor
from pulse_monitor.protocol import SAMPLE_RATE_HZ, decode_sample
from pulse_monitor.simulator.arduino_sim import VirtualArduinoSimulator
from pulse_monitor.simulator.ppg_model import Max30102SimConfig, Max30102Simulator


def test_dsp_recovers_bpm_and_spo2_under_60hz_and_motion_noise() -> None:
    cfg = Max30102SimConfig(bpm=72.0, spo2=97.0, noise_60hz=True, motion_drift=True, hrv_enabled=False)
    sim = Max30102Simulator(cfg, seed=123)
    proc = PpgSignalProcessor()

    dt = 1.0 / SAMPLE_RATE_HZ
    samples = [sim.step(dt) for _ in range(SAMPLE_RATE_HZ * 8)]
    proc.push_samples(samples)
    metrics = proc.process()

    assert abs(metrics.bpm - 72.0) <= 2.0
    assert abs(metrics.spo2 - 97.0) <= 1.5
    assert metrics.ppg_filtered.shape == (SAMPLE_RATE_HZ * 4,)
    assert np.max(np.abs(metrics.ppg_filtered)) <= 1.0


def test_dsp_notch_filter_attenuates_60hz() -> None:
    cfg = Max30102SimConfig(bpm=62.0, spo2=98.0, noise_60hz=True, motion_drift=False, shot_noise_std=0.0, hrv_enabled=False)
    sim = Max30102Simulator(cfg, seed=1)
    dt = 1.0 / SAMPLE_RATE_HZ
    samples = [sim.step(dt) for _ in range(SAMPLE_RATE_HZ * 6)]

    proc_filtered = PpgSignalProcessor()
    proc_filtered.push_samples(samples)
    m_filt = proc_filtered.process()

    # Verifica que componente em 60 Hz na saída filtrada foi fortemente atenuada
    freqs = np.fft.rfftfreq(len(m_filt.ppg_filtered), d=dt)
    spec_filt = np.abs(np.fft.rfft(m_filt.ppg_filtered))
    spec_raw = np.abs(np.fft.rfft(m_filt.ppg_raw_ac))

    idx_60 = int(np.argmin(np.abs(freqs - 60.0)))
    assert spec_filt[idx_60] < 0.05 * spec_raw[idx_60]


def test_virtual_arduino_pty_streams_valid_serial_frames() -> None:
    sim = VirtualArduinoSimulator(Max30102SimConfig(bpm=65.0, spo2=99.0))
    port = sim.start()
    try:
        with serial.Serial(port, baudrate=115200, timeout=1.0) as ser:
            ser.write(b"PING\n")
            received = []
            pong_seen = False
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline and (len(received) < 20 or not pong_seen):
                line = ser.readline().decode("ascii", errors="ignore")
                if line.startswith("PONG,"):
                    pong_seen = True
                sample = decode_sample(line)
                if sample is not None:
                    received.append(sample)

        assert pong_seen
        assert len(received) >= 20
        assert all(s.ir_raw > 0 and s.red_raw > 0 for s in received)
    finally:
        sim.stop()
