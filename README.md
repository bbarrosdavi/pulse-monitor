# Pulse Monitor — Instrumento Virtual para Monitoramento Cardíaco (PPG / SpO₂)

Instrumento Virtual (VI) desenvolvido para aquisição, processamento digital de sinais e visualização em tempo real de **Frequência Cardíaca (BPM)**, **Saturação de Oxigênio (SpO₂)** e **Onda Fotopletismográfica (PPG)**.

Baseado na proposta de projeto final (UTFPR — Engenharia de Controle e Automação, 2026):
- **Microcontrolador**: Arduino Pro Micro (ATmega32U4) via USB Serial (`115200` baud)
- **Sensor Óptico**: Módulo MAX30102 via I2C (SDA Pino 2, SCL Pino 3, 3.3V/5V, GND)
- **Simulação Integrada**:
  - **Firmware Arduino (`firmware/`)**: autodetecta o MAX30102 via I2C (`0x57`) e ativa automaticamente o **simulador embarcado do MAX30102** quando o módulo físico não está disponível.
  - **Simulador Arduino + MAX30102 (`src/pulse_monitor/simulator/`)**: emula o Arduino Pro Micro e o sensor MAX30102 via porta serial virtual (PTY POSIX) ou stream integrado, utilizando exatamente o mesmo protocolo serial do hardware real.
- **IHM & DSP (`src/pulse_monitor/`)**: Interface em **PySide6** + **PyQtGraph** com filtragem digital em tempo real (**Notch IIR 60 Hz** + **Passa-Faixa Butterworth 0.5–5.0 Hz**), detecção adaptativa de picos para BPM e cálculo de SpO₂ pela razão de absorção Red/IR ($R = \frac{AC_{red}/DC_{red}}{AC_{ir}/DC_{ir}}$).

## Estrutura do Repositório

```
pulse-monitor/
├── firmware/
│   └── arduino_pro_micro_max30102/
│       └── arduino_pro_micro_max30102.ino   # Firmware C++ (MAX30102 real ou simulado)
├── src/
│   └── pulse_monitor/
│       ├── app.py                           # Ponto de entrada da aplicação
│       ├── protocol.py                      # Protocolo serial (PPG,<ms>,<ir>,<red>,<sim>)
│       ├── dsp/
│       │   └── processor.py                 # Filtros digitais (60Hz notch, bandpass), BPM e SpO2
│       ├── simulator/
│       │   ├── ppg_model.py                 # Modelo fisiológico PPG + Beer-Lambert + ruídos
│       │   ├── arduino_sim.py               # Emulador de Arduino Pro Micro + PTY virtual serial
│       │   └── cli.py                       # CLI standalone do simulador serial
│       ├── acquisition/
│       │   └── serial_worker.py             # Leitor serial (Arduino físico ou PTY simulado)
│       └── ui/
│           ├── main_window.py               # Janela principal (layout idêntico ao protótipo)
│           ├── cards.py                     # Cards de BPM, SpO2 e card ilustrativo
│           ├── ppg_chart.py                 # Gráfico contínuo PyQtGraph com gradiente
│           ├── views.py                     # Vistas secundárias (Análise DSP, Registros, Config.)
│           └── icons.py                     # Ícones vetoriais QPainter
└── tests/                                   # Testes unitários e de integração (pytest)
```

## Como Executar

```bash
# Instalar dependências com uv
uv sync --extra dev

# Executar a IHM (inicia automaticamente com Arduino + MAX30102 simulados)
uv run pulse-monitor

# Opcional: executar apenas o simulador em uma porta serial virtual (PTY)
uv run pulse-monitor-sim

# Executar testes
uv run pytest
```
