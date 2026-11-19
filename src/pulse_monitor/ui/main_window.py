"""Janela principal do Pulse Monitor em estilo monitor clínico multiparamétrico."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pulse_monitor.acquisition.serial_worker import SerialAcquisitionManager, find_arduino_port
from pulse_monitor.dsp.processor import PpgSignalProcessor
from pulse_monitor.protocol import SourceMode
from pulse_monitor.simulator.ppg_model import Max30102Simulator
from pulse_monitor.ui.cards import HeartQuoteCard, MetricCard, SidebarButton
from pulse_monitor.ui.icons import make_title_icon
from pulse_monitor.ui.ppg_chart import PpgChartCard
from pulse_monitor.ui.views import AnalysisView, RecordsView, SettingsView


class _WindowControl(QPushButton):
    def __init__(self, symbol: str, tooltip: str, hover_bg: str, parent: QWidget | None = None) -> None:
        super().__init__(symbol, parent)
        self.setFixedSize(28, 24)
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                color: #8BA3BA;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
                color: #FFFFFF;
            }}
            """
        )


class _TitleBar(QFrame):
    """Barra superior clínica com identificação do instrumento, relógio e controles."""

    def __init__(self, window: QMainWindow) -> None:
        super().__init__(window)
        self._window = window
        self._drag_pos: QPoint | None = None
        self.setFixedHeight(44)
        self.setObjectName("TitleBar")
        self.setStyleSheet(
            """
            #TitleBar {
                background-color: #101923;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
                border-bottom: 1px solid #1E2E3E;
            }
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 12, 0)
        layout.setSpacing(10)

        icon_lbl = QLabel(self)
        icon_lbl.setPixmap(make_title_icon(20))
        icon_lbl.setStyleSheet("background: transparent;")

        title_lbl = QLabel("Pulse Monitor", self)
        title_lbl.setStyleSheet(
            "color: #E8F0F7; font-size: 14px; font-weight: 700; letter-spacing: 0.4px; background: transparent;"
        )
        sub_lbl = QLabel("MONITOR MULTIPARAMÉTRICO  •  PPG / SpO₂", self)
        sub_lbl.setStyleSheet(
            "color: #5E7A94; font-size: 11px; font-weight: 600; letter-spacing: 0.7px; background: transparent;"
        )

        self.clock_lbl = QLabel(datetime.now().strftime("%H:%M:%S"), self)
        self.clock_lbl.setStyleSheet(
            "color: #8FA7BF; font-size: 12px; font-weight: 600; background: #0B1219; "
            "border: 1px solid #1C2B3A; border-radius: 6px; padding: 3px 9px;"
        )

        self.btn_min = _WindowControl("–", "Minimizar", "#1E3042", self)
        self.btn_max = _WindowControl("□", "Maximizar", "#1E3042", self)
        self.btn_close = _WindowControl("×", "Fechar", "#D32F2F", self)
        self.btn_min.clicked.connect(window.showMinimized)
        self.btn_max.clicked.connect(self._toggle_maximize)
        self.btn_close.clicked.connect(window.close)

        layout.addWidget(icon_lbl)
        layout.addWidget(title_lbl)
        layout.addWidget(sub_lbl)
        layout.addStretch(1)
        layout.addWidget(self.clock_lbl)
        layout.addSpacing(8)
        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_close)

    def update_clock(self) -> None:
        self.clock_lbl.setText(datetime.now().strftime("%H:%M:%S"))

    def _toggle_maximize(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._window.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_pos = None


class MainWindow(QMainWindow):
    """IHM clínica principal do Instrumento Virtual Pulse Monitor."""

    def __init__(self, *, start_acquisition: bool = True) -> None:
        super().__init__()
        self.setWindowTitle("Pulse Monitor — Monitor Cardíaco")
        self.resize(1120, 640)
        self.setMinimumSize(920, 540)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.processor = PpgSignalProcessor()
        self.acquisition = SerialAcquisitionManager(self)
        self._current_source_label = SourceMode.label(SourceMode.VIRTUAL_ARDUINO)
        self._connected = False
        self._record_tick = 0

        self._build_ui()
        self._connect_signals()

        self._update_timer = QTimer(self)
        self._update_timer.setInterval(33)  # ~30 FPS suaves
        self._update_timer.timeout.connect(self._on_tick)

        if start_acquisition:
            arduino_port = find_arduino_port()
            if arduino_port:
                self.settings_view.select_usb_port(arduino_port)
                self.acquisition.start_physical_serial(arduino_port)
            else:
                prewarm = self.acquisition.start_virtual_arduino(prewarm_seconds=5.0)
                self.processor.push_samples(prewarm)
                self._apply_metrics_to_ui(self.processor.process())
            self._update_timer.start()
        else:
            self._prewarm_processor()

    def _build_ui(self) -> None:
        outer = QWidget(self)
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(6, 6, 6, 6)

        self.window_frame = QFrame(outer)
        self.window_frame.setObjectName("WindowFrame")
        self.window_frame.setStyleSheet(
            """
            #WindowFrame {
                background-color: #0B1118;
                border: 1px solid #1E2E3F;
                border-radius: 12px;
            }
            """
        )
        frame_layout = QVBoxLayout(self.window_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        self.title_bar = _TitleBar(self)
        frame_layout.addWidget(self.title_bar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Barra lateral esquerda clínica
        sidebar = QFrame(self.window_frame)
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(58)
        sidebar.setStyleSheet(
            """
            #Sidebar {
                background-color: #0F1720;
                border-bottom-left-radius: 12px;
                border-right: 1px solid #1D2C3C;
            }
            """
        )
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(9, 18, 9, 18)
        sb_layout.setSpacing(12)

        self.nav_buttons = [
            SidebarButton("home", "Monitor Multiparamétrico", sidebar),
            SidebarButton("wave", "Análise DSP e Filtros", sidebar),
            SidebarButton("records", "Prontuário da Sessão", sidebar),
            SidebarButton("settings", "Hardware / Simulador", sidebar),
        ]
        for idx, btn in enumerate(self.nav_buttons):
            btn.clicked.connect(lambda _checked=False, i=idx: self._switch_page(i))
            sb_layout.addWidget(btn)
        sb_layout.addStretch(1)
        self.nav_buttons[0].set_active(True)
        body.addWidget(sidebar)

        # Área principal
        content_wrap = QWidget(self.window_frame)
        content_wrap.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content_wrap)
        content_layout.setContentsMargins(18, 16, 18, 16)

        self.stack = QStackedWidget(content_wrap)
        self.home_page = self._build_home_page()
        self.analysis_view = AnalysisView(self.stack)
        self.records_view = RecordsView(self.stack)
        self.settings_view = SettingsView(self.stack)

        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.analysis_view)
        self.stack.addWidget(self.records_view)
        self.stack.addWidget(self.settings_view)

        content_layout.addWidget(self.stack)
        body.addWidget(content_wrap, 1)
        frame_layout.addLayout(body, 1)

        outer_layout.addWidget(self.window_frame)
        self.setCentralWidget(outer)

    def _build_home_page(self) -> QWidget:
        page = QWidget(self)
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        top_row = QHBoxLayout()
        top_row.setSpacing(14)

        self.bpm_card = MetricCard(
            title="Frequência Cardíaca",
            unit="bpm",
            badge_kind="heart",
            bar_color="#00E676",
            initial_value="62",
            initial_ratio=0.42,
            limits_text="60–100",
            parent=page,
        )
        self.spo2_card = MetricCard(
            title="Saturação de Oxigênio",
            unit="%",
            badge_kind="o2",
            bar_color="#29B6F6",
            initial_value="98",
            initial_ratio=0.65,
            limits_text="95–100%",
            parent=page,
        )
        self.quote_card = HeartQuoteCard(page)

        top_row.addWidget(self.bpm_card, 1)
        top_row.addWidget(self.spo2_card, 1)
        top_row.addWidget(self.quote_card, 1)
        layout.addLayout(top_row, 35)

        self.ppg_card = PpgChartCard(page)
        layout.addWidget(self.ppg_card, 65)

        return page

    def _connect_signals(self) -> None:
        self.acquisition.status_changed.connect(self._on_status_changed)
        self.acquisition.error_occurred.connect(self._on_error)
        self.settings_view.source_mode_changed.connect(self._on_source_changed)
        self.settings_view.sim_params_changed.connect(self._on_sim_params_changed)
        self.settings_view.dsp_filters_changed.connect(self._on_dsp_filters_changed)

    def _prewarm_processor(self) -> None:
        pre_sim = Max30102Simulator(seed=42)
        dt = 1.0 / self.processor.config.sample_rate_hz
        samples = [pre_sim.step(dt) for _ in range(int(self.processor.config.sample_rate_hz * 5.0))]
        self.processor.push_samples(samples)
        metrics = self.processor.process()
        self._apply_metrics_to_ui(metrics)

    def _switch_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.set_active(i == index)

    def _on_status_changed(self, connected: bool, label: str, _mode: int) -> None:
        self._connected = connected
        self._current_source_label = label
        port = self.acquisition.current_port or ""
        tooltip = f"{label} ({port})" if port else label
        self.ppg_card.status_pill.set_connected(connected, tooltip=tooltip)
        self.settings_view.set_status_text(f"Status: {tooltip}")

    def _on_error(self, message: str) -> None:
        self.settings_view.set_status_text(f"Erro: {message}")

    def _on_source_changed(self, use_virtual: bool, port: str) -> None:
        self.processor.reset()
        if use_virtual:
            prewarm = self.acquisition.start_virtual_arduino(prewarm_seconds=5.0)
            self.processor.push_samples(prewarm)
            self._apply_metrics_to_ui(self.processor.process())
        elif port:
            self.acquisition.start_physical_serial(port)
        else:
            self.settings_view.set_status_text("Selecione uma porta USB válida para o Arduino Pro Micro.")

    def _on_sim_params_changed(self, bpm: float, spo2: float, noise60: bool, motion: bool) -> None:
        self.acquisition.update_simulation_params(
            bpm=bpm,
            spo2=spo2,
            noise_60hz=noise60,
            motion_drift=motion,
        )

    def _on_dsp_filters_changed(self, notch_60hz: bool, bandpass: bool) -> None:
        self.processor.config.enable_notch_60hz = notch_60hz
        self.processor.config.enable_bandpass = bandpass

    def _on_tick(self) -> None:
        self._record_tick += 1
        if self._record_tick % 15 == 0:
            self.title_bar.update_clock()

        samples = self.acquisition.drain_samples()
        if not samples:
            return
        self.processor.push_samples(samples)
        metrics = self.processor.process()
        self._apply_metrics_to_ui(metrics)

        if self._record_tick % 30 == 0 and metrics.finger_detected:
            self.records_view.add_record(
                metrics.bpm,
                metrics.spo2,
                metrics.r_ratio,
                self._current_source_label,
            )

    def _apply_metrics_to_ui(self, metrics) -> None:
        if not metrics.finger_detected:
            self.bpm_card.set_value("--", 0.05)
            self.spo2_card.set_value("--", 0.05)
            if self._connected:
                port = self.acquisition.current_port or ""
                tooltip = f"{self._current_source_label} ({port}) — Posicione o dedo no sensor"
                self.ppg_card.status_pill.set_connected(True, tooltip=tooltip, label="Posicione o dedo")
        else:
            if self._connected:
                port = self.acquisition.current_port or ""
                tooltip = f"{self._current_source_label} ({port})" if port else self._current_source_label
                self.ppg_card.status_pill.set_connected(True, tooltip=tooltip, label="Tempo real")
            if metrics.bpm > 0:
                bpm_ratio = (metrics.bpm - 20.0) / 100.0
                self.bpm_card.set_value(f"{round(metrics.bpm)}", bpm_ratio)
            if metrics.spo2 > 0:
                spo2_ratio = (metrics.spo2 - 75.0) / 35.0
                self.spo2_card.set_value(f"{round(metrics.spo2)}", spo2_ratio)

        self.quote_card.update_telemetry(
            bpm=metrics.bpm,
            pi_pct=metrics.perfusion_index_pct,
            r_ratio=metrics.r_ratio,
            finger_detected=metrics.finger_detected,
        )
        wave = metrics.ecg_display if metrics.ecg_display is not None else metrics.ppg_filtered
        self.ppg_card.update_waveform(metrics.time_axis, wave, cursor_idx=metrics.sweep_cursor)
        self.analysis_view.update_metrics(metrics)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._update_timer.stop()
        self.acquisition.stop()
        super().closeEvent(event)
