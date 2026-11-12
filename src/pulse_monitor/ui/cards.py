"""Componentes de cards, barra lateral, pílula de status e painel ilustrativo."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
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
    """Aplica sombra suave rosada fiel ao protótipo."""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(22)
    shadow.setOffset(0, 4)
    shadow.setColor(QColor(135, 85, 100, 18))
    widget.setGraphicsEffect(shadow)


class SidebarButton(QPushButton):
    """Botão de ícone minimalista da barra lateral esquerda."""

    def __init__(self, kind: str, tooltip: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self._active = False
        self.setToolTip(tooltip)
        self.setFixedSize(38, 38)
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
            p.setBrush(QColor("#F9E9ED"))
            p.drawRoundedRect(rect, 10, 10)
            icon_color = QColor("#6B4C56")
        elif self.underMouse():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#FBF1F3"))
            p.drawRoundedRect(rect, 10, 10)
            icon_color = QColor("#7B616A")
        else:
            icon_color = QColor("#907B82")

        icon_rect = QRectF(8, 8, rect.width() - 16, rect.height() - 16)
        draw_sidebar_icon(p, self.kind, icon_rect, icon_color)
        p.end()


class _BadgeWidget(QWidget):
    """Widget auxiliar para desenhar badge circular vetorial."""

    def __init__(self, kind: str, size: int = 44, parent: QWidget | None = None) -> None:
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
    """Barra de progresso horizontal fina com cantos arredondados."""

    def __init__(self, fill_color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fill_color = QColor(fill_color)
        self._ratio = 0.5
        self.setFixedHeight(7)

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
        p.setBrush(QColor("#F1EAEB"))
        p.drawRoundedRect(QRectF(0, 0, w, h), radius, radius)

        fill_w = max(h, w * self._ratio)
        p.setBrush(self._fill_color)
        p.drawRoundedRect(QRectF(0, 0, fill_w, h), radius, radius)
        p.end()


class MetricCard(QFrame):
    """Card de métrica vital (Frequência Cardíaca ou Saturação de Oxigênio)."""

    def __init__(
        self,
        *,
        title: str,
        unit: str,
        badge_kind: str,
        bar_color: str,
        initial_value: str,
        initial_ratio: float,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setStyleSheet(
            """
            #MetricCard {
                background-color: #FFFFFF;
                border: 1px solid #F1E6E9;
                border-radius: 16px;
            }
            """
        )
        apply_card_shadow(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 20)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(14)
        self.badge = _BadgeWidget(badge_kind, 44, self)
        self.title_label = QLabel(title, self)
        self.title_label.setStyleSheet(
            "color: #6E5960; font-size: 14.5px; font-weight: 500; background: transparent; border: none;"
        )
        header.addWidget(self.badge)
        header.addWidget(self.title_label, 1)
        root.addLayout(header)

        root.addStretch(1)

        value_row = QHBoxLayout()
        value_row.setContentsMargins(58, 0, 0, 0)
        value_row.setSpacing(8)
        self.value_label = QLabel(initial_value, self)
        self.value_label.setStyleSheet(
            "color: #5D3E48; font-size: 46px; font-weight: 600; background: transparent; border: none;"
        )
        self.unit_label = QLabel(unit, self)
        self.unit_label.setStyleSheet(
            "color: #8F7A81; font-size: 16px; font-weight: 400; padding-bottom: 7px; background: transparent; border: none;"
        )
        value_row.addWidget(self.value_label, 0, Qt.AlignmentFlag.AlignBottom)
        value_row.addWidget(self.unit_label, 0, Qt.AlignmentFlag.AlignBottom)
        value_row.addStretch(1)
        root.addLayout(value_row)

        bar_row = QHBoxLayout()
        bar_row.setContentsMargins(58, 4, 34, 0)
        self.progress_bar = _ProgressBar(bar_color, self)
        self.progress_bar.set_ratio(initial_ratio)
        bar_row.addWidget(self.progress_bar)
        root.addLayout(bar_row)

    def set_value(self, text: str, ratio: float) -> None:
        self.value_label.setText(text)
        self.progress_bar.set_ratio(ratio)


class HeartQuoteCard(QFrame):
    """Card ilustrativo 'Seu coração em boas mãos' idêntico ao protótipo."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(165)

    def sizeHint(self) -> QSize:
        return QSize(300, 175)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        card_path = QPainterPath()
        card_path.addRoundedRect(rect, 16, 16)

        # Fundo com gradiente suave rosa pastel
        bg_grad = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
        bg_grad.setColorAt(0.0, QColor("#FDF7F8"))
        bg_grad.setColorAt(0.55, QColor("#FDF1F4"))
        bg_grad.setColorAt(1.0, QColor("#FCE6EC"))
        p.fillPath(card_path, bg_grad)

        p.setClipPath(card_path)

        # Brilho sutil radial atrás do coração
        w, h = rect.width(), rect.height()
        radial = QRadialGradient(QPointF(0.76 * w, 0.54 * h), 0.28 * w)
        radial.setColorAt(0.0, QColor(246, 198, 211, 80))
        radial.setColorAt(1.0, QColor(246, 198, 211, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(radial)
        p.drawEllipse(QPointF(0.76 * w, 0.54 * h), 0.28 * w, 0.36 * h)

        # Traço contínuo artístico formando o coração à direita
        ribbon = QPainterPath()
        ribbon.moveTo(0.04 * w, 0.95 * h)
        ribbon.cubicTo(0.32 * w, 0.92 * h, 0.58 * w, 0.78 * h, 0.76 * w, 0.56 * h)
        ribbon.cubicTo(0.86 * w, 0.42 * h, 0.86 * w, 0.24 * h, 0.75 * w, 0.23 * h)
        ribbon.cubicTo(0.68 * w, 0.22 * h, 0.65 * w, 0.30 * h, 0.66 * w, 0.37 * h)
        ribbon.cubicTo(0.64 * w, 0.25 * h, 0.54 * w, 0.22 * h, 0.51 * w, 0.35 * h)
        ribbon.cubicTo(0.49 * w, 0.50 * h, 0.62 * w, 0.66 * h, 0.75 * w, 0.72 * h)
        ribbon.cubicTo(0.85 * w, 0.76 * h, 0.94 * w, 0.68 * h, 1.01 * w, 0.58 * h)

        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor("#DDA1AF"), 1.65, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawPath(ribbon)

        # Estrela de brilho (4 pontas) no canto superior direito
        sx, sy = 0.89 * w, 0.24 * h
        r_out, r_in = 8.0, 2.2
        star = QPainterPath()
        star.moveTo(sx, sy - r_out)
        star.quadTo(sx + r_in * 0.4, sy - r_in * 0.4, sx + r_out, sy)
        star.quadTo(sx + r_in * 0.4, sy + r_in * 0.4, sx, sy + r_out)
        star.quadTo(sx - r_in * 0.4, sy + r_in * 0.4, sx - r_out, sy)
        star.quadTo(sx - r_in * 0.4, sy - r_in * 0.4, sx, sy - r_out)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#E3A3B3"))
        p.drawPath(star)

        # Texto itálico delicado à esquerda
        p.setPen(QColor("#7B6169"))
        font = QFont("Sans Serif", 12, QFont.Weight.Normal, True)
        p.setFont(font)
        text_rect = QRectF(24, 0.36 * h, 0.56 * w, 0.42 * h)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Seu coração\nem boas mãos")

        # Borda externa do card
        p.setClipping(False)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor("#F2E4E8"), 1.0))
        p.drawPath(card_path)
        p.end()


class StatusPill(QFrame):
    """Pílula de status 'Tempo real' com ponto indicador verde/âmbar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusPill")
        self.setStyleSheet(
            """
            #StatusPill {
                background-color: #F8F4F5;
                border: 1px solid #EDE3E6;
                border-radius: 13px;
            }
            """
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(11, 4, 12, 4)
        layout.setSpacing(6)

        self._dot = QLabel(self)
        self._dot.setFixedSize(7, 7)
        self._dot.setStyleSheet("background-color: #58B970; border-radius: 3px; border: none;")

        self._label = QLabel("Tempo real", self)
        self._label.setStyleSheet(
            "color: #6D5960; font-size: 12px; font-weight: 500; background: transparent; border: none;"
        )

        layout.addWidget(self._dot)
        layout.addWidget(self._label)

    def set_connected(self, connected: bool, tooltip: str = "") -> None:
        dot_color = "#58B970" if connected else "#E09A48"
        self._dot.setStyleSheet(f"background-color: {dot_color}; border-radius: 3px; border: none;")
        self._label.setText("Tempo real" if connected else "Aguardando")
        if tooltip:
            self.setToolTip(tooltip)
