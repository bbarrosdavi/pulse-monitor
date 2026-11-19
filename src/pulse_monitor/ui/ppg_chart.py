"""Gráfico clínico em formato ECG (P-QRS-T) em tempo real com PyQtGraph."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from pulse_monitor.ui.cards import StatusPill, apply_card_shadow
from pulse_monitor.ui.icons import draw_ppg_badge


class _PpgBadge(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(36, 36)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        draw_ppg_badge(p, QRectF(0, 0, self.width(), self.height()))
        p.end()


class PpgChartCard(QFrame):
    """Card inferior do traçado cardíaco em estilo monitor hospitalar ECG."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PpgChartCard")
        self.setStyleSheet(
            """
            #PpgChartCard {
                background-color: #131D28;
                border: 1px solid #1F2E3E;
                border-radius: 12px;
            }
            """
        )
        apply_card_shadow(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(12)
        self.badge = _PpgBadge(self)
        self.title_label = QLabel("Sinal PPG", self)
        self.title_label.setStyleSheet(
            "color: #E6EDF3; font-size: 14.5px; font-weight: 600; background: transparent; border: none;"
        )
        lead_lbl = QLabel("DERIVAÇÃO II  •  25 mm/s  •  200 Hz", self)
        lead_lbl.setStyleSheet(
            "color: #00E676; font-size: 11px; font-weight: 700; letter-spacing: 0.6px; "
            "background: #0D2019; border: 1px solid #184330; border-radius: 6px; padding: 3px 8px;"
        )
        self.status_pill = StatusPill(self)

        header.addWidget(self.badge)
        header.addWidget(self.title_label)
        header.addWidget(lead_lbl)
        header.addStretch(1)
        header.addWidget(self.status_pill)
        root.addLayout(header)

        # Osciloscópio clínico PyQtGraph
        pg.setConfigOptions(antialias=True)
        self.plot_widget = pg.PlotWidget(self)
        self.plot_widget.setBackground("#091017")
        self.plot_widget.setStyleSheet("border: 1px solid #1A2A3A; border-radius: 8px;")
        self.plot_widget.setMenuEnabled(False)
        self.plot_widget.setMouseEnabled(x=False, y=False)
        self.plot_widget.hideButtons()

        plot_item = self.plot_widget.getPlotItem()
        plot_item.setContentsMargins(8, 8, 14, 6)
        plot_item.setYRange(-1.05, 1.05, padding=0.0)
        plot_item.setXRange(-0.10, 4.10, padding=0.0)

        tick_font = QFont("Monospace", 8)
        tick_color = QColor("#678099")

        left_axis = plot_item.getAxis("left")
        left_axis.setPen(pg.mkPen(color="#1C2E40", width=1))
        left_axis.setTextPen(tick_color)
        left_axis.setTickFont(tick_font)
        left_axis.setStyle(tickLength=4, tickTextOffset=8)
        left_axis.setTicks(
            [[(-1.0, "-1.0"), (-0.5, "-0.5"), (0.0, "0.0"), (0.5, "0.5"), (1.0, "1.0")]]
        )

        bottom_axis = plot_item.getAxis("bottom")
        bottom_axis.setPen(pg.mkPen(color="#1C2E40", width=1))
        bottom_axis.setTextPen(tick_color)
        bottom_axis.setTickFont(tick_font)
        bottom_axis.setStyle(tickLength=5, tickTextOffset=8)
        bottom_axis.setTicks(
            [[(0.0, "0.0s"), (1.0, "1.0s"), (2.0, "2.0s"), (3.0, "3.0s"), (4.0, "4.0s")]]
        )

        # Grade milimetrada estilo papel/osciloscópio de ECG
        for x_minor in np.arange(0.0, 4.01, 0.2):
            is_major = abs(x_minor - round(x_minor)) < 1e-6
            col = "#182A3B" if is_major else "#101C27"
            plot_item.addItem(pg.InfiniteLine(pos=float(x_minor), angle=90, pen=pg.mkPen(color=col, width=1)))

        for y_minor in np.arange(-1.0, 1.01, 0.25):
            is_major = abs((y_minor * 2.0) - round(y_minor * 2.0)) < 1e-6
            col = "#182A3B" if is_major else "#101C27"
            plot_item.addItem(pg.InfiniteLine(pos=float(y_minor), angle=0, pen=pg.mkPen(color=col, width=1)))

        # Traço principal estilo osciloscópio ECG hospitalar (varredura contínua com lacuna)
        self.curve = plot_item.plot(
            pen=pg.mkPen(color="#00E676", width=2.4),
            connect="finite",
        )
        # Ponto luminoso na ponta do feixe de varredura
        self.cursor_dot = pg.ScatterPlotItem(
            size=9,
            brush=pg.mkBrush("#B9F6CA"),
            pen=pg.mkPen("#00E676", width=2),
        )
        plot_item.addItem(self.cursor_dot)

        root.addWidget(self.plot_widget, 1)

    def update_waveform(
        self,
        time_axis: np.ndarray,
        ppg_values: np.ndarray,
        cursor_idx: int | None = None,
    ) -> None:
        self.curve.setData(time_axis, ppg_values, connect="finite")
        if cursor_idx is not None and 0 <= cursor_idx < len(time_axis):
            val = ppg_values[cursor_idx]
            if np.isfinite(val):
                self.cursor_dot.setData([time_axis[cursor_idx]], [val])
                return
        self.cursor_dot.setData([], [])
