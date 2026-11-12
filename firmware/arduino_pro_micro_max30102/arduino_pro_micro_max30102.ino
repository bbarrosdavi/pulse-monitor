/*
 * Pulse Monitor — Firmware Embarcado para Arduino Pro Micro (ATmega32U4)
 * Sensor Óptico: MAX30102 via I2C (SDA = Pino 2, SCL = Pino 3, VIN = 3.3V/5V, GND)
 * Comunicação: USB Serial @ 115200 bps | Taxa de amostragem: 200 Hz (5 ms)
 *
 * Funcionalidades:
 *  - Autodetecção do módulo MAX30102 no barramento I2C (endereço 0x57).
 *  - Quando o módulo físico MAX30102 não está conectado, ativa automaticamente
 *    o simulador embarcado do sensor óptico (sinal PPG IR/RED + ruído 60 Hz + deriva).
 *  - Aceita comandos pela serial USB:
 *      SET_BPM:<valor>      (30..200)
 *      SET_SPO2:<valor>     (70..100)
 *      SET_NOISE60:<0|1>
 *      SET_MOTION:<0|1>
 *      MODE:<AUTO|SIM|REAL>
 *      PING
 */

#include <Wire.h>
#include <math.h>

#define MAX30102_I2C_ADDR 0x57
#define SAMPLE_INTERVAL_US 5000UL  // 200 Hz -> Nyquist = 100 Hz (permite filtro notch 60 Hz)

// Registradores essenciais do MAX30102 (leitura I2C direta sem dependência externa obrigatória)
#define REG_INTR_ENABLE_1 0x02
#define REG_FIFO_WR_PTR   0x04
#define REG_OVF_COUNTER   0x05
#define REG_FIFO_RD_PTR   0x06
#define REG_FIFO_DATA     0x07
#define REG_FIFO_CONFIG   0x08
#define REG_MODE_CONFIG   0x09
#define REG_SPO2_CONFIG   0x0A
#define REG_LED1_PA       0x0C
#define REG_LED2_PA       0x0D
#define REG_PART_ID       0xFF

enum OperatingMode {
  MODE_AUTO = 0,
  MODE_SIM  = 1,
  MODE_REAL = 2
};

OperatingMode requestedMode = MODE_AUTO;
bool max30102Present = false;

// Parâmetros do simulador MAX30102 embarcado
float simBpm = 62.0f;
float simSpo2 = 98.0f;
bool simNoise60Hz = true;
bool simMotionDrift = true;
float simPhase = 0.0f;

unsigned long lastSampleUs = 0;
String cmdBuffer = "";

void writeRegister(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(MAX30102_I2C_ADDR);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}

bool readRegister(uint8_t reg, uint8_t &value) {
  Wire.beginTransmission(MAX30102_I2C_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) {
    return false;
  }
  Wire.requestFrom((uint8_t)MAX30102_I2C_ADDR, (uint8_t)1);
  if (!Wire.available()) {
    return false;
  }
  value = Wire.read();
  return true;
}

bool initMAX30102() {
  uint8_t partId = 0;
  if (!readRegister(REG_PART_ID, partId) || partId != 0x15) {
    return false;
  }
  // Reset e configuração padrão SpO2 (LED Vermelho + IR, 200 Hz, 18-bit ADC)
  writeRegister(REG_MODE_CONFIG, 0x40);
  delay(20);
  writeRegister(REG_FIFO_WR_PTR, 0x00);
  writeRegister(REG_OVF_COUNTER, 0x00);
  writeRegister(REG_FIFO_RD_PTR, 0x00);
  writeRegister(REG_FIFO_CONFIG, 0x0F);  // sem média FIFO, rollover habilitado
  writeRegister(REG_MODE_CONFIG, 0x03);  // modo SpO2 (Red + IR)
  writeRegister(REG_SPO2_CONFIG, 0x2B);  // ADC 4096 nA, 200 Hz, 411 us (18 bits)
  writeRegister(REG_LED1_PA, 0x24);      // Red LED ~7.2 mA
  writeRegister(REG_LED2_PA, 0x24);      // IR LED  ~7.2 mA
  return true;
}

bool readMAX30102Sample(uint32_t &redRaw, uint32_t &irRaw) {
  Wire.beginTransmission(MAX30102_I2C_ADDR);
  Wire.write(REG_FIFO_DATA);
  if (Wire.endTransmission(false) != 0) {
    return false;
  }
  Wire.requestFrom((uint8_t)MAX30102_I2C_ADDR, (uint8_t)6);
  if (Wire.available() < 6) {
    return false;
  }
  uint32_t b0 = Wire.read();
  uint32_t b1 = Wire.read();
  uint32_t b2 = Wire.read();
  uint32_t b3 = Wire.read();
  uint32_t b4 = Wire.read();
  uint32_t b5 = Wire.read();

  redRaw = ((b0 << 16) | (b1 << 8) | b2) & 0x03FFFFUL;
  irRaw  = ((b3 << 16) | (b4 << 8) | b5) & 0x03FFFFUL;
  return true;
}

float gaussianPulse(float phase, float center, float width) {
  float d = (phase - center) / width;
  return expf(-0.5f * d * d);
}

void generateSimulatedMAX30102(float dtSec, float tSec, uint32_t &redRaw, uint32_t &irRaw) {
  float freqHz = simBpm / 60.0f;
  simPhase += freqHz * dtSec;
  if (simPhase >= 1.0f) {
    simPhase -= 1.0f;
  }

  // Morfologia fisiológica PPG (pico sistólico + nó dicrótico + onda diastólica)
  float systolic  = 1.00f * gaussianPulse(simPhase, 0.25f, 0.085f);
  float dicrotic  = 0.34f * gaussianPulse(simPhase, 0.48f, 0.115f);
  float diastolic = 0.10f * gaussianPulse(simPhase, 0.72f, 0.100f);
  float pulse = (systolic + dicrotic + diastolic) - 0.34f;

  // Razão de absorção Beer-Lambert: SpO2 = 110 - 25 * R
  float rRatio = (110.0f - simSpo2) / 25.0f;
  if (rRatio < 0.1f) rRatio = 0.1f;

  const float dcIr  = 100000.0f;
  const float dcRed = 85000.0f;
  const float acIr  = 1200.0f;
  const float acRed = rRatio * (acIr / dcIr) * dcRed;

  float noise60 = simNoise60Hz ? (180.0f * sinf(2.0f * PI * 60.0f * tSec)) : 0.0f;
  float motion  = simMotionDrift ? (320.0f * sinf(2.0f * PI * 0.22f * tSec)) : 0.0f;

  // No fotodetector real do MAX30102, maior volume sanguíneo absorve mais luz
  float irVal  = dcIr  - acIr  * pulse + noise60 + motion;
  float redVal = dcRed - acRed * pulse + 0.85f * noise60 + 0.85f * motion;

  irRaw  = (uint32_t)constrain((long)irVal, 0L, 262143L);
  redRaw = (uint32_t)constrain((long)redVal, 0L, 262143L);
}

void processSerialCommand(const String &cmd) {
  if (cmd == "PING") {
    int modeFlag = (requestedMode == MODE_REAL && max30102Present) ? 0 : 1;
    Serial.print("PONG,PULSE_MONITOR_V1,");
    Serial.println(modeFlag);
  } else if (cmd.startsWith("SET_BPM:")) {
    float val = cmd.substring(8).toFloat();
    if (val >= 30.0f && val <= 200.0f) simBpm = val;
  } else if (cmd.startsWith("SET_SPO2:")) {
    float val = cmd.substring(9).toFloat();
    if (val >= 70.0f && val <= 100.0f) simSpo2 = val;
  } else if (cmd.startsWith("SET_NOISE60:")) {
    simNoise60Hz = (cmd.substring(12).toInt() != 0);
  } else if (cmd.startsWith("SET_MOTION:")) {
    simMotionDrift = (cmd.substring(11).toInt() != 0);
  } else if (cmd == "MODE:AUTO") {
    requestedMode = MODE_AUTO;
  } else if (cmd == "MODE:SIM") {
    requestedMode = MODE_SIM;
  } else if (cmd == "MODE:REAL") {
    requestedMode = MODE_REAL;
  }
}

void pollSerialCommands() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      cmdBuffer.trim();
      if (cmdBuffer.length() > 0) {
        processSerialCommand(cmdBuffer);
      }
      cmdBuffer = "";
    } else if (cmdBuffer.length() < 64) {
      cmdBuffer += c;
    }
  }
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  Wire.setClock(400000UL);

  max30102Present = initMAX30102();
  lastSampleUs = micros();
}

void loop() {
  pollSerialCommands();

  unsigned long nowUs = micros();
  if ((unsigned long)(nowUs - lastSampleUs) >= SAMPLE_INTERVAL_US) {
    lastSampleUs += SAMPLE_INTERVAL_US;

    bool useReal = false;
    if (requestedMode == MODE_REAL && max30102Present) {
      useReal = true;
    } else if (requestedMode == MODE_AUTO && max30102Present) {
      useReal = true;
    }

    uint32_t redRaw = 0;
    uint32_t irRaw = 0;
    int simFlag = 1;

    if (useReal && readMAX30102Sample(redRaw, irRaw)) {
      simFlag = 0;
    } else {
      float dtSec = SAMPLE_INTERVAL_US / 1000000.0f;
      float tSec  = millis() / 1000.0f;
      generateSimulatedMAX30102(dtSec, tSec, redRaw, irRaw);
      simFlag = 1;
    }

    // Formato: PPG,<timestamp_ms>,<ir_raw>,<red_raw>,<sim_flag>
    Serial.print("PPG,");
    Serial.print(millis());
    Serial.print(",");
    Serial.print(irRaw);
    Serial.print(",");
    Serial.print(redRaw);
    Serial.print(",");
    Serial.println(simFlag);
  }
}
