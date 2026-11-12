"""Ícones vetoriais e ilustrações desenhadas com QPainter."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap


def draw_heart_pulse_icon(painter: QPainter, rect: QRectF, color: QColor) -> None:
    """Desenha um ícone de coração contorno com linha de pulso (título)."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(color, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    w, h = rect.width(), rect.height()
    x, y = rect.x(), rect.y()
    heart = QPainterPath()
    heart.moveTo(x + 0.50 * w, y + 0.84 * h)
    heart.cubicTo(x + 0.14 * w, y + 0.62 * h, x + 0.08 * w, y + 0.34 * h, x + 0.24 * w, y + 0.20 * h)
    heart.cubicTo(x + 0.36 * w, y + 0.11 * h, x + 0.48 * w, y + 0.19 * h, x + 0.50 * w, y + 0.29 * h)
    heart.cubicTo(x + 0.52 * w, y + 0.19 * h, x + 0.64 * w, y + 0.11 * h, x + 0.76 * w, y + 0.20 * h)
    heart.cubicTo(x + 0.92 * w, y + 0.34 * h, x + 0.86 * w, y + 0.62 * h, x + 0.50 * w, y + 0.84 * h)
    painter.drawPath(heart)

    pulse = QPainterPath()
    pulse.moveTo(x + 0.23 * w, y + 0.50 * h)
    pulse.lineTo(x + 0.37 * w, y + 0.50 * h)
    pulse.lineTo(x + 0.44 * w, y + 0.36 * h)
    pulse.lineTo(x + 0.54 * w, y + 0.62 * h)
    pulse.lineTo(x + 0.61 * w, y + 0.46 * h)
    pulse.lineTo(x + 0.77 * w, y + 0.46 * h)
    painter.drawPath(pulse)
    painter.restore()


def make_title_icon(size: int = 20) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    draw_heart_pulse_icon(p, QRectF(1, 1, size - 2, size - 2), QColor("#7D5F68"))
    p.end()
    return pm


def draw_sidebar_icon(painter: QPainter, kind: str, rect: QRectF, color: QColor) -> None:
    """Desenha ícones minimalistas da barra lateral (home, wave, doc, settings)."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(color, 1.65, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()

    if kind == "home":
        roof = QPainterPath()
        roof.moveTo(x + 0.16 * w, y + 0.48 * h)
        roof.lineTo(x + 0.50 * w, y + 0.18 * h)
        roof.lineTo(x + 0.84 * w, y + 0.48 * h)
        painter.drawPath(roof)

        body = QPainterPath()
        body.moveTo(x + 0.24 * w, y + 0.42 * h)
        body.lineTo(x + 0.24 * w, y + 0.82 * h)
        body.lineTo(x + 0.76 * w, y + 0.82 * h)
        body.lineTo(x + 0.76 * w, y + 0.42 * h)
        painter.drawPath(body)

        door = QPainterPath()
        door.moveTo(x + 0.42 * w, y + 0.82 * h)
        door.lineTo(x + 0.42 * w, y + 0.58 * h)
        door.lineTo(x + 0.58 * w, y + 0.58 * h)
        door.lineTo(x + 0.58 * w, y + 0.82 * h)
        painter.drawPath(door)

    elif kind == "wave":
        path = QPainterPath()
        path.moveTo(x + 0.12 * w, y + 0.55 * h)
        path.lineTo(x + 0.30 * w, y + 0.55 * h)
        path.lineTo(x + 0.42 * w, y + 0.22 * h)
        path.lineTo(x + 0.56 * w, y + 0.78 * h)
        path.lineTo(x + 0.68 * w, y + 0.45 * h)
        path.lineTo(x + 0.76 * w, y + 0.55 * h)
        path.lineTo(x + 0.88 * w, y + 0.55 * h)
        painter.drawPath(path)

    elif kind == "records":
        doc = QRectF(x + 0.24 * w, y + 0.18 * h, 0.52 * w, 0.66 * h)
        painter.drawRoundedRect(doc, 2.5, 2.5)
        painter.drawLine(QPointF(x + 0.36 * w, y + 0.38 * h), QPointF(x + 0.64 * w, y + 0.38 * h))
        painter.drawLine(QPointF(x + 0.36 * w, y + 0.52 * h), QPointF(x + 0.64 * w, y + 0.52 * h))
        painter.drawLine(QPointF(x + 0.36 * w, y + 0.66 * h), QPointF(x + 0.54 * w, y + 0.66 * h))

    elif kind == "settings":
        import math

        cx, cy = x + 0.5 * w, y + 0.5 * h
        r_inner = 0.16 * w
        painter.drawEllipse(QPointF(cx, cy), r_inner, r_inner)
        gear = QPainterPath()
        teeth = 8
        for i in range(teeth * 2):
            ang = (i * math.pi) / teeth
            r = 0.34 * w if i % 2 == 0 else 0.26 * w
            px = cx + r * math.cos(ang)
            py = cy + r * math.sin(ang)
            if i == 0:
                gear.moveTo(px, py)
            else:
                gear.lineTo(px, py)
        gear.closeSubpath()
        painter.drawPath(gear)

    painter.restore()


def draw_heart_badge(painter: QPainter, rect: QRectF) -> None:
    """Badge circular rosa com coração preenchido e pulso branco."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#FCE8ED"))
    painter.drawEllipse(rect)

    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    heart = QPainterPath()
    heart.moveTo(x + 0.50 * w, y + 0.74 * h)
    heart.cubicTo(x + 0.24 * w, y + 0.58 * h, x + 0.20 * w, y + 0.36 * h, x + 0.32 * w, y + 0.27 * h)
    heart.cubicTo(x + 0.41 * w, y + 0.21 * h, x + 0.48 * w, y + 0.27 * h, x + 0.50 * w, y + 0.34 * h)
    heart.cubicTo(x + 0.52 * w, y + 0.27 * h, x + 0.59 * w, y + 0.21 * h, x + 0.68 * w, y + 0.27 * h)
    heart.cubicTo(x + 0.80 * w, y + 0.36 * h, x + 0.76 * w, y + 0.58 * h, x + 0.50 * w, y + 0.74 * h)

    grad = QLinearGradient(x, y + 0.2 * h, x, y + 0.75 * h)
    grad.setColorAt(0.0, QColor("#F07A96"))
    grad.setColorAt(1.0, QColor("#E25E7D"))
    painter.setBrush(grad)
    painter.drawPath(heart)

    pen = QPen(QColor("#FFF8FA"), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    pulse = QPainterPath()
    pulse.moveTo(x + 0.28 * w, y + 0.49 * h)
    pulse.lineTo(x + 0.39 * w, y + 0.49 * h)
    pulse.lineTo(x + 0.45 * w, y + 0.39 * h)
    pulse.lineTo(x + 0.52 * w, y + 0.58 * h)
    pulse.lineTo(x + 0.58 * w, y + 0.45 * h)
    pulse.lineTo(x + 0.64 * w, y + 0.49 * h)
    pulse.lineTo(x + 0.73 * w, y + 0.49 * h)
    painter.drawPath(pulse)
    painter.restore()


def draw_o2_badge(painter: QPainter, rect: QRectF) -> None:
    """Badge circular lilás com gota de oxigênio O2."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#EFEBF8"))
    painter.drawEllipse(rect)

    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    drop = QPainterPath()
    drop.moveTo(x + 0.50 * w, y + 0.23 * h)
    drop.cubicTo(x + 0.66 * w, y + 0.44 * h, x + 0.71 * w, y + 0.58 * h, x + 0.67 * w, y + 0.67 * h)
    drop.cubicTo(x + 0.63 * w, y + 0.76 * h, x + 0.37 * w, y + 0.76 * h, x + 0.33 * w, y + 0.67 * h)
    drop.cubicTo(x + 0.29 * w, y + 0.58 * h, x + 0.34 * w, y + 0.44 * h, x + 0.50 * w, y + 0.23 * h)

    painter.setPen(QPen(QColor("#78639A"), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(QColor("#F7F4FC"))
    painter.drawPath(drop)

    painter.setPen(QColor("#6E598F"))
    font = QFont("Sans Serif", 8, QFont.Weight.DemiBold)
    painter.setFont(font)
    painter.drawText(QRectF(x + 0.28 * w, y + 0.46 * h, 0.44 * w, 0.28 * h), Qt.AlignmentFlag.AlignCenter, "O₂")
    painter.restore()


def draw_ppg_badge(painter: QPainter, rect: QRectF) -> None:
    """Badge circular rosa suave com ícone de onda PPG."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#FCE8ED"))
    painter.drawEllipse(rect)

    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    pen = QPen(QColor("#C7677F"), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    path = QPainterPath()
    path.moveTo(x + 0.22 * w, y + 0.54 * h)
    path.lineTo(x + 0.34 * w, y + 0.54 * h)
    path.lineTo(x + 0.42 * w, y + 0.30 * h)
    path.lineTo(x + 0.52 * w, y + 0.72 * h)
    path.lineTo(x + 0.61 * w, y + 0.42 * h)
    path.lineTo(x + 0.67 * w, y + 0.54 * h)
    path.lineTo(x + 0.78 * w, y + 0.54 * h)
    painter.drawPath(path)
    painter.restore()
