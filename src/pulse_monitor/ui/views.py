"""Vistas secundárias acessíveis pela barra lateral (Análise DSP, Registros e Configurações)."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pulse_monitor.acquisition.serial_worker import list_serial_ports
from pulse_monitor.dsp.processor import DspMetrics
from pulse_monitor.ui.cards import apply_card_shadow


def _card_style() -> str:
    return """
    QFrame#SectionCard {
        background-color: #FFFFFF;
        border: 1px solid #F1E6E9;
        border-radius: 16px;
    }
    """


class AnalysisView(QWidget):
    """Comparação Sinal Bruto vs Sinal Filtrado (Notch 60Hz + Passa-Faixa) e métricas DSP."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        card = QFrame(self)
        card.setObjectName("SectionCard")
        card.setStyleSheet(_card_style())
        apply_card_shadow(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Análise de Filtragem Digital (Sinal Bruto vs. Filtrado)", card)
        title.setStyleSheet("color: #5D3E48; font-size: 15px; font-weight: 600; border: none;")
        self.metrics_label = QLabel("Razão R: -- | IP: --% | Amostras: 0", card)
        self.metrics_label.setStyleSheet("color: #8A747C; font-size: 12.5px; border: none;")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.metrics_label)
        layout.addLayout(header)

        self.plot = pg.PlotWidget(card)
        self.plot.setBackground("#FFFFFF")
        self.plot.setMenuEnabled(False)
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.hideButtons()

        pi = self.plot.getPlotItem()
        pi.setYRange(-1.05, 1.05, padding=0.0)
        pi.setXRange(0.0, 4.0, padding=0.01)
        pi.addLegend(offset=(12, 8))
        pi.getAxis("left").setTextPen(QColor("#9C8B91"))
        pi.getAxis("bottom").setTextPen(QColor("#9C8B91"))
        pi.showGrid(x=False, y=True, alpha=0.25)

        self.raw_curve = pi.plot(
            pen=pg.mkPen(color="#C9B7BE", width=1.2),
            name="Bruto AC (60 Hz + deriva)",
        )
        self.filt_curve = pi.plot(
            pen=pg.mkPen(color="#BC647B", width=2.2),
            name="Filtrado (Notch 60 Hz + 0.5–4.5 Hz)",
        )
        layout.addWidget(self.plot, 1)
        root.addWidget(card, 1)

    def update_metrics(self, metrics: DspMetrics) -> None:
        self.raw_curve.setData(metrics.time_axis, metrics.ppg_raw_ac)
        self.filt_curve.setData(metrics.time_axis, metrics.ppg_filtered)
        self.metrics_label.setText(
            f"Razão R: {metrics.r_ratio:.3f}  |  Índice de Perfusão: {metrics.perfusion_index_pct:.2f}%  |  Amostras: {metrics.sample_count}"
        )


@dataclass(slots=True)
class TelemetryRecord:
    timestamp: str
    bpm: float
    spo2: float
    r_ratio: float
    source: str


class RecordsView(QWidget):
    """Histórico da sessão e exportação CSV dos sinais vitais."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._records: list[TelemetryRecord] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        card = QFrame(self)
        card.setObjectName("SectionCard")
        card.setStyleSheet(_card_style())
        apply_card_shadow(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Registros da Sessão", card)
        title.setStyleSheet("color: #5D3E48; font-size: 15px; font-weight: 600; border: none;")

        self.export_btn = QPushButton("Exportar CSV", card)
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #F9E9ED;
                color: #6B4C56;
                border: 1px solid #EBD4DA;
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 12.5px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #F4DCE2; }
            """
        )
        self.export_btn.clicked.connect(self._export_csv)

        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.export_btn)
        layout.addLayout(header)

        self.table = QTableWidget(0, 5, card)
        self.table.setHorizontalHeaderLabels(["Horário", "BPM", "SpO₂ (%)", "Razão R", "Origem"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setStyleSheet(
            """
            QTableWidget {
                border: 1px solid #F1E6E9;
                border-radius: 10px;
                background-color: #FFFFFF;
                color: #5D3E48;
                gridline-color: #F6EEF0;
            }
            QHeaderView::section {
                background-color: #FDF7F8;
                color: #7D636B;
                border: none;
                border-bottom: 1px solid #F1E6E9;
                padding: 6px;
                font-weight: 600;
            }
            """
        )
        layout.addWidget(self.table, 1)
        root.addWidget(card, 1)

    def add_record(self, bpm: float, spo2: float, r_ratio: float, source: str) -> None:
        if bpm <= 0.0:
            return
        now = datetime.now().strftime("%H:%M:%S")
        rec = TelemetryRecord(now, bpm, spo2, r_ratio, source)
        self._records.append(rec)
        if len(self._records) > 200:
            self._records.pop(0)
            self.table.removeRow(self.table.rowCount() - 1)

        self.table.insertRow(0)
        values = [now, f"{bpm:.0f}", f"{spo2:.1f}", f"{r_ratio:.3f}", source]
        for col, text in enumerate(values):
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if col < 4 else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(0, col, item)

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Exportar Registros", "pulse_monitor_sessao.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["horario", "bpm", "spo2_pct", "r_ratio", "origem"])
            for r in self._records:
                writer.writerow([r.timestamp, f"{r.bpm:.1f}", f"{r.spo2:.1f}", f"{r.r_ratio:.4f}", r.source])


class SettingsView(QWidget):
    """Configuração de fonte (Simulador Arduino vs USB Serial), simulação e filtros DSP."""

    source_mode_changed = Signal(bool, str)  # use_virtual, serial_port
    sim_params_changed = Signal(float, float, bool, bool)  # bpm, spo2, noise60, motion
    dsp_filters_changed = Signal(bool, bool)  # notch_60hz, bandpass

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        # Card 1: Fonte de Dados (Arduino Simulado vs Físico)
        hw_card = QFrame(self)
        hw_card.setObjectName("SectionCard")
        hw_card.setStyleSheet(_card_style())
        apply_card_shadow(hw_card)
        hw_layout = QVBoxLayout(hw_card)
        hw_layout.setContentsMargins(20, 16, 20, 16)
        hw_layout.setSpacing(10)

        hw_title = QLabel("Hardware e Comunicação Serial (Arduino Pro Micro + MAX30102)", hw_card)
        hw_title.setStyleSheet("color: #5D3E48; font-size: 14.5px; font-weight: 600; border: none;")
        hw_layout.addWidget(hw_title)

        row_src = QHBoxLayout()
        self.mode_combo = QComboBox(hw_card)
        self.mode_combo.addItem("Simulador Arduino Pro Micro + MAX30102 (Virtual PTY)", "virtual")
        self.mode_combo.addItem("Arduino Pro Micro Físico (USB Serial 115200 bps)", "usb")

        self.port_combo = QComboBox(hw_card)
        self.refresh_btn = QPushButton("Atualizar Portas", hw_card)
        self.apply_src_btn = QPushButton("Conectar", hw_card)
        for btn in (self.refresh_btn, self.apply_src_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #F9E9ED;
                    color: #6B4C56;
                    border: 1px solid #EBD4DA;
                    border-radius: 8px;
                    padding: 5px 12px;
                    font-weight: 500;
                }
                QPushButton:hover { background-color: #F4DCE2; }
                """
            )

        row_src.addWidget(self.mode_combo, 2)
        row_src.addWidget(self.port_combo, 1)
        row_src.addWidget(self.refresh_btn)
        row_src.addWidget(self.apply_src_btn)
        hw_layout.addLayout(row_src)

        self.port_status = QLabel("Conectado ao Simulador Virtual Arduino + MAX30102", hw_card)
        self.port_status.setStyleSheet("color: #8A747C; font-size: 12px; border: none;")
        hw_layout.addWidget(self.port_status)

        # Card 2: Parâmetros do Módulo Simulado & Filtros
        sim_card = QFrame(self)
        sim_card.setObjectName("SectionCard")
        sim_card.setStyleSheet(_card_style())
        apply_card_shadow(sim_card)
        sim_layout = QVBoxLayout(sim_card)
        sim_layout.setContentsMargins(20, 16, 20, 16)
        sim_layout.setSpacing(12)

        sim_title = QLabel("Parâmetros do Módulo Simulado e Filtros Digitais", sim_card)
        sim_title.setStyleSheet("color: #5D3E48; font-size: 14.5px; font-weight: 600; border: none;")
        sim_layout.addWidget(sim_title)

        # Slider BPM
        bpm_row = QHBoxLayout()
        self.bpm_val_lbl = QLabel("Frequência Alvo: 62 bpm", sim_card)
        self.bpm_val_lbl.setMinimumWidth(175)
        self.bpm_val_lbl.setStyleSheet("color: #6E5960; border: none;")
        self.bpm_slider = QSlider(Qt.Orientation.Horizontal, sim_card)
        self.bpm_slider.setRange(40, 160)
        self.bpm_slider.setValue(62)
        bpm_row.addWidget(self.bpm_val_lbl)
        bpm_row.addWidget(self.bpm_slider, 1)
        sim_layout.addLayout(bpm_row)

        # Slider SpO2
        spo2_row = QHBoxLayout()
        self.spo2_val_lbl = QLabel("SpO₂ Alvo: 98 %", sim_card)
        self.spo2_val_lbl.setMinimumWidth(175)
        self.spo2_val_lbl.setStyleSheet("color: #6E5960; border: none;")
        self.spo2_slider = QSlider(Qt.Orientation.Horizontal, sim_card)
        self.spo2_slider.setRange(80, 100)
        self.spo2_slider.setValue(98)
        spo2_row.addWidget(self.spo2_val_lbl)
        spo2_row.addWidget(self.spo2_slider, 1)
        sim_layout.addLayout(spo2_row)

        # Checkboxes de ruído e filtros
        checks_row = QHBoxLayout()
        self.chk_noise60 = QCheckBox("Injetar ruído de rede 60 Hz", sim_card)
        self.chk_noise60.setChecked(True)
        self.chk_motion = QCheckBox("Injetar deriva de movimento", sim_card)
        self.chk_motion.setChecked(True)
        self.chk_notch = QCheckBox("Filtro Notch 60 Hz (IHM)", sim_card)
        self.chk_notch.setChecked(True)
        self.chk_bandpass = QCheckBox("Filtro Passa-Faixa 0.5–4.5 Hz (IHM)", sim_card)
        self.chk_bandpass.setChecked(True)
        for chk in (self.chk_noise60, self.chk_motion, self.chk_notch, self.chk_bandpass):
            chk.setStyleSheet("color: #6E5960; border: none;")
            checks_row.addWidget(chk)
        sim_layout.addLayout(checks_row)

        root.addWidget(hw_card)
        root.addWidget(sim_card)
        root.addStretch(1)

        self.refresh_ports()
        self.mode_combo.currentIndexChanged.connect(self._sync_port_enabled)
        self.refresh_btn.clicked.connect(self.refresh_ports)
        self.apply_src_btn.clicked.connect(self._emit_source)
        self.bpm_slider.valueChanged.connect(self._emit_sim)
        self.spo2_slider.valueChanged.connect(self._emit_sim)
        self.chk_noise60.toggled.connect(self._emit_sim)
        self.chk_motion.toggled.connect(self._emit_sim)
        self.chk_notch.toggled.connect(self._emit_dsp)
        self.chk_bandpass.toggled.connect(self._emit_dsp)
        self._sync_port_enabled()

    def refresh_ports(self) -> None:
        self.port_combo.clear()
        ports = list_serial_ports()
        if not ports:
            self.port_combo.addItem("Nenhuma porta USB detectada", "")
        else:
            for dev, desc in ports:
                self.port_combo.addItem(f"{dev} ({desc})", dev)

    def _sync_port_enabled(self) -> None:
        is_usb = self.mode_combo.currentData() == "usb"
        self.port_combo.setEnabled(is_usb)
        self.refresh_btn.setEnabled(is_usb)

    def _emit_source(self) -> None:
        use_virtual = self.mode_combo.currentData() == "virtual"
        port = str(self.port_combo.currentData() or "")
        self.source_mode_changed.emit(use_virtual, port)

    def _emit_sim(self) -> None:
        bpm = float(self.bpm_slider.value())
        spo2 = float(self.spo2_slider.value())
        self.bpm_val_lbl.setText(f"Frequência Alvo: {int(bpm)} bpm")
        self.spo2_val_lbl.setText(f"SpO₂ Alvo: {int(spo2)} %")
        self.sim_params_changed.emit(bpm, spo2, self.chk_noise60.isChecked(), self.chk_motion.isChecked())

    def _emit_dsp(self) -> None:
        self.dsp_filters_changed.emit(self.chk_notch.isChecked(), self.chk_bandpass.isChecked())

    def set_status_text(self, text: str) -> None:
        self.port_status.setText(text)
