"""Teste de fumaça da IHM em modo offscreen."""

from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

from pulse_monitor.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    yield app


def test_main_window_initializes_with_prototype_defaults(qapp) -> None:
    win = MainWindow(start_acquisition=False)
    try:
        assert win.bpm_card.value_label.text() == "62"
        assert win.spo2_card.value_label.text() == "98"
        assert win.ppg_card.title_label.text() == "Sinal PPG"
        assert win.stack.count() == 4
    finally:
        win.close()
