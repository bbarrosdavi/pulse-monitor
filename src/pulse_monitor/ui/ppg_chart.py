"""Gráfico de onda PPG em tempo real usando PyQtGraph com preenchimento em gradiente."""

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
    """Card inferior 'Sinal PPG' idêntico ao protótipo com plotagem PyQtGraph."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PpgChartCard")
        self.setStyleSheet(
            """
            #PpgChartCard {
                background-color: #FFFFFF;
                border: 1px solid #F1E6E9;
                border-radius: 16px;
            }
            """
        )
        apply_card_shadow(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 14)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(12)
        self.badge = _PpgBadge(self)
        self.title_label = QLabel("Sinal PPG", self)
        self.title_label.setStyleSheet(
            "color: #6E5960; font-size: 14.5px; font-weight: 500; background: transparent; border: none;"
        )
        self.status_pill = StatusPill(self)

        header.addWidget(self.badge)
        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(self.status_pill)
        root.addLayout(header)

        # Configuração PyQtGraph
        pg.setConfigOptions(antialias=True)
        self.plot_widget = pg.PlotWidget(self)
        self.plot_widget.setBackground("#FFFFFF")
        self.plot_widget.setMenuEnabled(False)
        self.plot_widget.setMouseEnabled(x=False, y=False)
        self.plot_widget.hideButtons()

        plot_item = self.plot_widget.getPlotItem()
        plot_item.setContentsMargins(10, 6, 16, 4)
        plot_item.setYRange(-1.05, 1.05, padding=0.0)
        plot_item.setXRange(-0.12, 4.12, padding=0.0)

        tick_font = QFont("Sans Serif", 9)
        tick_color = QColor("#9C8B91")

        left_axis = plot_item.getAxis("left")
        left_axis.setPen(pg.mkPen(None))
        left_axis.setTextPen(tick_color)
        left_axis.setTickFont(tick_font)
        left_axis.setStyle(tickLength=0, tickTextOffset=8)
        left_axis.setTicks(
            [[(-1.0, "-1.0"), (-0.5, "-0.5"), (0.0, "0.0"), (0.5, "0.5"), (1.0, "1.0")]]
        )

        bottom_axis = plot_item.getAxis("bottom")
        bottom_axis.setPen(pg.mkPen(color="#EDE3E6", width=1))
        bottom_axis.setTextPen(tick_color)
        bottom_axis.setTickFont(tick_font)
        bottom_axis.setStyle(tickLength=5, tickTextOffset=8)
        bottom_axis.setTicks(
            [[(0.0, "0.0s"), (1.0, "1.0s"), (2.0, "2.0s"), (3.0, "3.0s"), (4.0, "4.0s")]]
        )

        # Linhas horizontais sutis de grade
        for y_val in (-1.0, -0.5, 0.0, 0.5, 1.0):
            line = pg.InfiniteLine(
                pos=y_val,
                angle=0,
                pen=pg.mkPen(color="#F4ECEE", width=1, style=Qt.PenStyle.DotLine),
            )
            plot_item.addItem(line)

        # Gradiente rosa sob a onda PPG
        grad = QLinearGradient(0.0, 0.55, 0.0, -0.85)
        grad.setColorAt(0.0, QColor(227, 134, 158, 95))
        grad.setColorAt(0.65, QColor(235, 165, 184, 35))
        grad.setColorAt(1.0, QColor(245, 210, 220, 0))

        self.curve = plot_item.plot(
            pen=pg.mkPen(color="#BC647B", width=2.2),
            fillLevel=-0.85,
            brush=QBrush(grad),
        )

        root.addWidget(self.plot_widget, 1)

    def update_waveform(self, time_axis: np.ndarray, ppg_values: np.ndarray) -> None:
        self.curve.setData(time_axis, ppg_values)
