"""Ícones vetoriais clínicos desenhados com QPainter."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap


def draw_heart_pulse_icon(painter: QPainter, rect: QRectF, color: QColor) -> None:
    """Desenha ícone clínico de coração com traço ECG."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(color, 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
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
    pulse.moveTo(x + 0.20 * w, y + 0.50 * h)
    pulse.lineTo(x + 0.36 * w, y + 0.50 * h)
    pulse.lineTo(x + 0.44 * w, y + 0.33 * h)
    pulse.lineTo(x + 0.54 * w, y + 0.65 * h)
    pulse.lineTo(x + 0.62 * w, y + 0.46 * h)
    pulse.lineTo(x + 0.80 * w, y + 0.46 * h)
    painter.drawPath(pulse)
    painter.restore()


def make_title_icon(size: int = 20) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    draw_heart_pulse_icon(p, QRectF(1, 1, size - 2, size - 2), QColor("#00E676"))
    p.end()
    return pm


def draw_sidebar_icon(painter: QPainter, kind: str, rect: QRectF, color: QColor) -> None:
    """Desenha ícones minimalistas da barra lateral clínica."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(color, 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()

    if kind == "home":
        # Monitor multiparamétrico
        screen = QRectF(x + 0.14 * w, y + 0.18 * h, 0.72 * w, 0.52 * h)
        painter.drawRoundedRect(screen, 2.5, 2.5)
        wave = QPainterPath()
        wave.moveTo(x + 0.22 * w, y + 0.46 * h)
        wave.lineTo(x + 0.36 * w, y + 0.46 * h)
        wave.lineTo(x + 0.44 * w, y + 0.28 * h)
        wave.lineTo(x + 0.53 * w, y + 0.60 * h)
        wave.lineTo(x + 0.61 * w, y + 0.42 * h)
        wave.lineTo(x + 0.78 * w, y + 0.42 * h)
        painter.drawPath(wave)
        painter.drawLine(QPointF(x + 0.36 * w, y + 0.82 * h), QPointF(x + 0.64 * w, y + 0.82 * h))
        painter.drawLine(QPointF(x + 0.50 * w, y + 0.70 * h), QPointF(x + 0.50 * w, y + 0.82 * h))

    elif kind == "wave":
        path = QPainterPath()
        path.moveTo(x + 0.12 * w, y + 0.55 * h)
        path.lineTo(x + 0.30 * w, y + 0.55 * h)
        path.lineTo(x + 0.42 * w, y + 0.20 * h)
        path.lineTo(x + 0.56 * w, y + 0.80 * h)
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
    """Badge clínico verde ECG para Frequência Cardíaca."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#1B4D36"), 1.0))
    painter.setBrush(QColor("#0F2D21"))
    painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 10, 10)
    draw_heart_pulse_icon(painter, rect.adjusted(7, 7, -7, -7), QColor("#00E676"))
    painter.restore()


def draw_o2_badge(painter: QPainter, rect: QRectF) -> None:
    """Badge clínico ciano para SpO2."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#1A455E"), 1.0))
    painter.setBrush(QColor("#0E2636"))
    painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 10, 10)

    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    drop = QPainterPath()
    drop.moveTo(x + 0.50 * w, y + 0.22 * h)
    drop.cubicTo(x + 0.67 * w, y + 0.44 * h, x + 0.72 * w, y + 0.58 * h, x + 0.68 * w, y + 0.68 * h)
    drop.cubicTo(x + 0.63 * w, y + 0.78 * h, x + 0.37 * w, y + 0.78 * h, x + 0.32 * w, y + 0.68 * h)
    drop.cubicTo(x + 0.28 * w, y + 0.58 * h, x + 0.33 * w, y + 0.44 * h, x + 0.50 * w, y + 0.22 * h)

    painter.setPen(QPen(QColor("#29B6F6"), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(QColor(41, 182, 246, 28))
    painter.drawPath(drop)

    painter.setPen(QColor("#7FD8FF"))
    font = QFont("Sans Serif", 8, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(QRectF(x + 0.28 * w, y + 0.47 * h, 0.44 * w, 0.28 * h), Qt.AlignmentFlag.AlignCenter, "O₂")
    painter.restore()


def draw_ppg_badge(painter: QPainter, rect: QRectF) -> None:
    """Badge clínico de derivação ECG/PPG."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#1B4D36"), 1.0))
    painter.setBrush(QColor("#0F2D21"))
    painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 8, 8)

    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    pen = QPen(QColor("#00E676"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    path = QPainterPath()
    path.moveTo(x + 0.16 * w, y + 0.56 * h)
    path.lineTo(x + 0.33 * w, y + 0.56 * h)
    path.lineTo(x + 0.42 * w, y + 0.24 * h)
    path.lineTo(x + 0.53 * w, y + 0.76 * h)
    path.lineTo(x + 0.62 * w, y + 0.44 * h)
    path.lineTo(x + 0.70 * w, y + 0.56 * h)
    path.lineTo(x + 0.84 * w, y + 0.56 * h)
    painter.drawPath(path)
    painter.restore()
