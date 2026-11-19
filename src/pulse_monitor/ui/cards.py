"""Componentes clínicos profissionais: cards multiparamétricos, telemetria e barra lateral."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pulse_monitor.ui.icons import (
    draw_heart_badge,
    draw_o2_badge,
    draw_sidebar_icon,
)


def apply_card_shadow(widget: QWidget) -> None:
    """Sombra discreta para profundidade em interface médica dark."""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(18)
    shadow.setOffset(0, 3)
    shadow.setColor(QColor(0, 0, 0, 90))
    widget.setGraphicsEffect(shadow)


class SidebarButton(QPushButton):
    """Botão de navegação lateral em estilo estação clínica."""

    def __init__(self, kind: str, tooltip: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self._active = False
        self.setToolTip(tooltip)
        self.setFixedSize(40, 40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)

    def set_active(self, active: bool) -> None:
        self._active = active
        self.setChecked(active)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())

        if self._active:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 230, 118, 30))
            p.drawRoundedRect(rect, 9, 9)
            # Indicador lateral esquerdo ativo
            p.setBrush(QColor("#00E676"))
            p.drawRoundedRect(QRectF(0, 8, 3, rect.height() - 16), 1.5, 1.5)
            icon_color = QColor("#00E676")
        elif self.underMouse():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#1A2634"))
            p.drawRoundedRect(rect, 9, 9)
            icon_color = QColor("#C6D7E6")
        else:
            icon_color = QColor("#6B8299")

        icon_rect = QRectF(9, 9, rect.width() - 18, rect.height() - 18)
        draw_sidebar_icon(p, self.kind, icon_rect, icon_color)
        p.end()


class _BadgeWidget(QWidget):
    def __init__(self, kind: str, size: int = 40, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._kind = kind
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        rect = QRectF(0, 0, self.width(), self.height())
        if self._kind == "heart":
            draw_heart_badge(p, rect)
        elif self._kind == "o2":
            draw_o2_badge(p, rect)
        p.end()


class _ProgressBar(QWidget):
    """Barra horizontal de nível fisiológico de alta visibilidade."""

    def __init__(self, fill_color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fill_color = QColor(fill_color)
        self._ratio = 0.5
        self.setFixedHeight(6)

    def set_ratio(self, ratio: float) -> None:
        self._ratio = max(0.05, min(1.0, float(ratio)))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = float(self.width())
        h = float(self.height())
        radius = h / 2.0

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#1C2B3A"))
        p.drawRoundedRect(QRectF(0, 0, w, h), radius, radius)

        fill_w = max(h, w * self._ratio)
        p.setBrush(self._fill_color)
        p.drawRoundedRect(QRectF(0, 0, fill_w, h), radius, radius)
        p.end()


class MetricCard(QFrame):
    """Card multiparamétrico de monitor hospitalar (FC ou SpO₂)."""

    def __init__(
        self,
        *,
        title: str,
        unit: str,
        badge_kind: str,
        bar_color: str,
        initial_value: str,
        initial_ratio: float,
        limits_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setStyleSheet(
            """
            #MetricCard {
                background-color: #131D28;
                border: 1px solid #1F2E3E;
                border-radius: 12px;
            }
            """
        )
        apply_card_shadow(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 18)
        root.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(12)
        self.badge = _BadgeWidget(badge_kind, 40, self)
        self.title_label = QLabel(title, self)
        self.title_label.setStyleSheet(
            "color: #9BB0C5; font-size: 13.5px; font-weight: 600; letter-spacing: 0.3px; background: transparent; border: none;"
        )
        header.addWidget(self.badge)
        header.addWidget(self.title_label, 1)

        if limits_text:
            limits_lbl = QLabel(limits_text, self)
            limits_lbl.setStyleSheet(
                "color: #5E778E; font-size: 11px; font-weight: 600; background: #0E1620; "
                "border: 1px solid #1E2E3D; border-radius: 6px; padding: 2px 7px;"
            )
            header.addWidget(limits_lbl)
        root.addLayout(header)

        root.addStretch(1)

        value_row = QHBoxLayout()
        value_row.setContentsMargins(6, 0, 0, 0)
        value_row.setSpacing(10)
        self.value_label = QLabel(initial_value, self)
        self.value_label.setStyleSheet(
            f"color: {bar_color}; font-size: 52px; font-weight: 700; background: transparent; border: none;"
        )
        self.unit_label = QLabel(unit, self)
        self.unit_label.setStyleSheet(
            "color: #6F88A0; font-size: 16px; font-weight: 600; padding-bottom: 9px; background: transparent; border: none;"
        )
        value_row.addWidget(self.value_label, 0, Qt.AlignmentFlag.AlignBottom)
        value_row.addWidget(self.unit_label, 0, Qt.AlignmentFlag.AlignBottom)
        value_row.addStretch(1)
        root.addLayout(value_row)

        bar_row = QHBoxLayout()
        bar_row.setContentsMargins(6, 4, 6, 0)
        self.progress_bar = _ProgressBar(bar_color, self)
        self.progress_bar.set_ratio(initial_ratio)
        bar_row.addWidget(self.progress_bar)
        root.addLayout(bar_row)

    def set_value(self, text: str, ratio: float) -> None:
        self.value_label.setText(text)
        self.progress_bar.set_ratio(ratio)


class HeartQuoteCard(QFrame):
    """Painel clínico de Telemetria, Ritmo e Qualidade de Perfusão."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TelemetryCard")
        self.setStyleSheet(
            """
            #TelemetryCard {
                background-color: #131D28;
                border: 1px solid #1F2E3E;
                border-radius: 12px;
            }
            """
        )
        apply_card_shadow(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("TELEMETRIA CLÍNICA", self)
        title.setStyleSheet(
            "color: #9BB0C5; font-size: 12px; font-weight: 700; letter-spacing: 0.8px; background: transparent; border: none;"
        )
        self.rhythm_badge = QLabel("SINUSAL", self)
        self.rhythm_badge.setStyleSheet(
            "color: #00E676; background-color: rgba(0, 230, 118, 0.14); border: 1px solid rgba(0, 230, 118, 0.35); "
            "border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 700;"
        )
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.rhythm_badge)
        root.addLayout(header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)

        self.pi_value = self._add_metric_cell(grid, 0, 0, "ÍNDICE DE PERFUSÃO", "-- %", "#29B6F6")
        self.r_value = self._add_metric_cell(grid, 0, 1, "RAZÃO ÓPTICA (R)", "--", "#E6EDF3")
        self.filter_value = self._add_metric_cell(grid, 1, 0, "FILTRAGEM DSP", "Notch 60Hz • BP", "#00E676")
        self.sensor_value = self._add_metric_cell(grid, 1, 1, "AQUISIÇÃO", "MAX30102 • 200Hz", "#C6D7E6")

        root.addLayout(grid, 1)

    def _add_metric_cell(
        self,
        grid: QGridLayout,
        row: int,
        col: int,
        label_text: str,
        initial: str,
        value_color: str,
    ) -> QLabel:
        box = QFrame(self)
        box.setStyleSheet(
            "background-color: #0E1620; border: 1px solid #1C2A38; border-radius: 8px;"
        )
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 7, 10, 7)
        lay.setSpacing(2)

        lbl = QLabel(label_text, box)
        lbl.setStyleSheet("color: #627B93; font-size: 10px; font-weight: 700; border: none; background: transparent;")
        val = QLabel(initial, box)
        val.setStyleSheet(f"color: {value_color}; font-size: 13px; font-weight: 600; border: none; background: transparent;")
        lay.addWidget(lbl)
        lay.addWidget(val)
        grid.addWidget(box, row, col)
        return val

    def update_telemetry(self, *, bpm: float, pi_pct: float, r_ratio: float, finger_detected: bool) -> None:
        if not finger_detected or bpm <= 0:
            self.rhythm_badge.setText("AGUARDANDO")
            self.rhythm_badge.setStyleSheet(
                "color: #FFB300; background-color: rgba(255, 179, 0, 0.14); border: 1px solid rgba(255, 179, 0, 0.35); "
                "border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 700;"
            )
            self.pi_value.setText("-- %")
            self.r_value.setText("--")
            return

        if bpm < 55:
            txt, col = "BRADICARDIA", "#FFB300"
        elif bpm > 105:
            txt, col = "TAQUICARDIA", "#FF5252"
        else:
            txt, col = "RITMO SINUSAL", "#00E676"

        self.rhythm_badge.setText(txt)
        self.rhythm_badge.setStyleSheet(
            f"color: {col}; background-color: #0E1A24; border: 1px solid {col}; "
            "border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 700;"
        )
        self.pi_value.setText(f"{pi_pct:.2f} %")
        self.r_value.setText(f"{r_ratio:.3f}")


class StatusPill(QFrame):
    """Indicador de estado em tempo real do monitor clínico."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusPill")
        self.setStyleSheet(
            """
            #StatusPill {
                background-color: #0E1822;
                border: 1px solid #1E3244;
                border-radius: 12px;
            }
            """
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(11, 4, 12, 4)
        layout.setSpacing(7)

        self._dot = QLabel(self)
        self._dot.setFixedSize(8, 8)
        self._dot.setStyleSheet("background-color: #00E676; border-radius: 4px; border: none;")

        self._label = QLabel("Tempo real", self)
        self._label.setStyleSheet(
            "color: #D5E3F0; font-size: 12px; font-weight: 600; background: transparent; border: none;"
        )

        layout.addWidget(self._dot)
        layout.addWidget(self._label)

    def set_connected(self, connected: bool, tooltip: str = "", label: str | None = None) -> None:
        if not connected:
            dot_color = "#FF5252"
        elif label and "dedo" in label.lower():
            dot_color = "#FFB300"
        else:
            dot_color = "#00E676"
        self._dot.setStyleSheet(f"background-color: {dot_color}; border-radius: 4px; border: none;")
        if label is not None:
            self._label.setText(label)
        else:
            self._label.setText("Tempo real" if connected else "Desconectado")
        if tooltip:
            self.setToolTip(tooltip)
