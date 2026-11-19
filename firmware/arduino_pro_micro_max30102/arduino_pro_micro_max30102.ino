/*
 * Pulse Monitor — Firmware Embarcado para Arduino Pro Micro (ATmega32U4)
 * Sensor Óptico: MAX30102 via I2C (SDA = Pino 2, SCL = Pino 3, VIN = 3.3V/5V, GND = GND)
 * Comunicação: USB Serial @ 115200 bps | Taxa de amostragem: 200 Hz (5 ms)
 *
 * Funcionalidades:
 *  - Diagnóstico elétrico dos pinos SDA (2) / SCL (3) e recuperação de barramento I2C.
 *  - Suporte automático a TWI Hardware (Wire com timeout de 25 ms) e fallback para
 *    I2C Open-Drain por Software (essencial quando o módulo MAX30102 usa pull-ups
 *    de 1.8V/3.3V abaixo do limiar TWI 0.7*VCC=3.5V do ATmega32U4 5V).
 *  - Autodetecção do MAX30102 (0x57, PART_ID 0x15) e leitura sincronizada pela FIFO.
 *  - Fallback automático para simulador embarcado quando o sensor está desconectado.
 *  - Comandos seriais: PING, STATUS, SCAN, MODE:<AUTO|REAL|SIM>,
 *    SET_BPM:<v>, SET_SPO2:<v>, SET_NOISE60:<0|1>, SET_MOTION:<0|1>
 */

#include <Wire.h>
#include <math.h>

#define PIN_SDA 2
#define PIN_SCL 3

#define MAX30102_I2C_ADDR 0x57
#define SAMPLE_INTERVAL_US 5000UL  // 200 Hz -> Nyquist = 100 Hz (permite filtro notch 60 Hz)

// Registradores essenciais do MAX30102
#define REG_INTR_STATUS_1 0x00
#define REG_INTR_STATUS_2 0x01
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
#define REG_REV_ID        0xFE
#define REG_PART_ID       0xFF

enum OperatingMode {
  MODE_AUTO = 0,
  MODE_SIM  = 1,
  MODE_REAL = 2
};

OperatingMode requestedMode = MODE_AUTO;
bool max30102Present = false;
bool useSoftI2C = false;
uint8_t detectedPartId = 0;
uint8_t detectedRevId = 0;
uint8_t lastPinNoPullSda = 0;
uint8_t lastPinNoPullScl = 0;
uint16_t i2cErrorStreak = 0;
unsigned long i2cTimeoutCount = 0;

// Parâmetros do simulador MAX30102 embarcado
float simBpm = 62.0f;
float simSpo2 = 98.0f;
bool simNoise60Hz = true;
bool simMotionDrift = true;
float simPhase = 0.0f;

unsigned long lastSampleUs = 0;
String cmdBuffer = "";

// ===================== Software I2C Open-Drain (seguro para 1.8V/3.3V) =====================

static inline void sdaLow()  { digitalWrite(PIN_SDA, LOW); pinMode(PIN_SDA, OUTPUT); }
static inline void sdaHigh() { pinMode(PIN_SDA, INPUT); }
static inline void sclLow()  { digitalWrite(PIN_SCL, LOW); pinMode(PIN_SCL, OUTPUT); }
static inline void sclHigh() { pinMode(PIN_SCL, INPUT); }

static void softDelay() {
  delayMicroseconds(2);
}

void softI2CInit() {
  Wire.end();
  digitalWrite(PIN_SDA, LOW);
  digitalWrite(PIN_SCL, LOW);
  sdaHigh();
  sclHigh();
  delayMicroseconds(20);
}

void softI2CStart() {
  sdaHigh();
  sclHigh();
  softDelay();
  sdaLow();
  softDelay();
  sclLow();
  softDelay();
}

void softI2CRepStart() {
  sdaHigh();
  softDelay();
  sclHigh();
  softDelay();
  sdaLow();
  softDelay();
  sclLow();
  softDelay();
}

void softI2CStop() {
  sdaLow();
  softDelay();
  sclHigh();
  softDelay();
  sdaHigh();
  softDelay();
}

bool softI2CWriteByte(uint8_t data) {
  for (uint8_t mask = 0x80; mask != 0; mask >>= 1) {
    if (data & mask) {
      sdaHigh();
    } else {
      sdaLow();
    }
    softDelay();
    sclHigh();
    softDelay();
    sclLow();
    softDelay();
  }
  sdaHigh();
  softDelay();
  sclHigh();
  softDelay();
  bool ack = (digitalRead(PIN_SDA) == LOW);
  sclLow();
  softDelay();
  return ack;
}

uint8_t softI2CReadByte(bool sendAck) {
  uint8_t val = 0;
  sdaHigh();
  for (uint8_t i = 0; i < 8; i++) {
    val <<= 1;
    sclHigh();
    softDelay();
    if (digitalRead(PIN_SDA) == HIGH) {
      val |= 1;
    }
    sclLow();
    softDelay();
  }
  if (sendAck) {
    sdaLow();
  } else {
    sdaHigh();
  }
  softDelay();
  sclHigh();
  softDelay();
  sclLow();
  softDelay();
  sdaHigh();
  return val;
}

bool softI2CProbe(uint8_t addr) {
  softI2CStart();
  bool ack = softI2CWriteByte((uint8_t)(addr << 1));
  softI2CStop();
  return ack;
}

bool softWriteRegister(uint8_t reg, uint8_t value) {
  softI2CStart();
  bool ok = softI2CWriteByte((uint8_t)(MAX30102_I2C_ADDR << 1));
  if (ok) ok = softI2CWriteByte(reg);
  if (ok) ok = softI2CWriteByte(value);
  softI2CStop();
  return ok;
}

bool softReadRegisters(uint8_t reg, uint8_t *buf, uint8_t len) {
  softI2CStart();
  bool ok = softI2CWriteByte((uint8_t)(MAX30102_I2C_ADDR << 1));
  if (ok) ok = softI2CWriteByte(reg);
  if (!ok) {
    softI2CStop();
    return false;
  }
  softI2CRepStart();
  ok = softI2CWriteByte((uint8_t)((MAX30102_I2C_ADDR << 1) | 1));
  if (!ok) {
    softI2CStop();
    return false;
  }
  for (uint8_t i = 0; i < len; i++) {
    buf[i] = softI2CReadByte(i + 1 < len);
  }
  softI2CStop();
  return true;
}

// ===================== Hardware Wire I2C com Timeout =====================

void configureWireBus() {
  Wire.begin();
  Wire.setClock(50000UL);
  Wire.setWireTimeout(25000, true);
  Wire.clearWireTimeoutFlag();
}

bool checkAndClearWireTimeout() {
  if (Wire.getWireTimeoutFlag()) {
    Wire.clearWireTimeoutFlag();
    i2cTimeoutCount++;
    return true;
  }
  return false;
}

void recoverI2CBus() {
  Wire.end();
  pinMode(PIN_SDA, INPUT);
  pinMode(PIN_SCL, INPUT);
  delayMicroseconds(50);
  lastPinNoPullSda = digitalRead(PIN_SDA);
  lastPinNoPullScl = digitalRead(PIN_SCL);

  if (lastPinNoPullSda == LOW && lastPinNoPullScl == HIGH) {
    for (uint8_t i = 0; i < 9; i++) {
      sclLow();
      delayMicroseconds(10);
      sclHigh();
      delayMicroseconds(10);
    }
    delayMicroseconds(50);
    lastPinNoPullSda = digitalRead(PIN_SDA);
    lastPinNoPullScl = digitalRead(PIN_SCL);
  }
}

// ===================== Camada unificada de acesso ao MAX30102 =====================

bool writeRegister(uint8_t reg, uint8_t value) {
  if (useSoftI2C) {
    return softWriteRegister(reg, value);
  }
  Wire.beginTransmission(MAX30102_I2C_ADDR);
  Wire.write(reg);
  Wire.write(value);
  uint8_t err = Wire.endTransmission();
  if (checkAndClearWireTimeout()) return false;
  return (err == 0);
}

bool readRegisters(uint8_t reg, uint8_t *buf, uint8_t len) {
  if (useSoftI2C) {
    return softReadRegisters(reg, buf, len);
  }
  Wire.beginTransmission(MAX30102_I2C_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0 || checkAndClearWireTimeout()) {
    return false;
  }
  uint8_t got = Wire.requestFrom((uint8_t)MAX30102_I2C_ADDR, len, (uint8_t)true);
  if (checkAndClearWireTimeout() || got < len || Wire.available() < len) {
    return false;
  }
  for (uint8_t i = 0; i < len; i++) {
    buf[i] = Wire.read();
  }
  return true;
}

bool readRegister(uint8_t reg, uint8_t &value) {
  return readRegisters(reg, &value, 1);
}

bool initMAX30102() {
  uint8_t partId = 0;
  if (!readRegister(REG_PART_ID, partId) || partId != 0x15) {
    return false;
  }

  Serial.println("STATUS,INIT_RESETTING");
  if (!writeRegister(REG_MODE_CONFIG, 0x40)) {
    return false;
  }
  delay(100);

  uint8_t dummy = 0;
  readRegister(REG_INTR_STATUS_1, dummy);
  readRegister(REG_INTR_STATUS_2, dummy);

  bool ok = true;
  ok &= writeRegister(REG_FIFO_WR_PTR, 0x00);
  ok &= writeRegister(REG_OVF_COUNTER, 0x00);
  ok &= writeRegister(REG_FIFO_RD_PTR, 0x00);
  // SMP_AVE=000 (1 amostra), FIFO_ROLLOVER_EN=1 (0x10), FIFO_A_FULL=0x0F
  ok &= writeRegister(REG_FIFO_CONFIG, 0x1F);
  // ADC 4096 nA (01), 200 Hz (010), LED_PW 411 us / 18-bit (11) -> 0x2B
  ok &= writeRegister(REG_SPO2_CONFIG, 0x2B);
  ok &= writeRegister(REG_LED1_PA, 0x24);      // Red LED ~7.2 mA
  ok &= writeRegister(REG_LED2_PA, 0x24);      // IR LED  ~7.2 mA
  ok &= writeRegister(REG_MODE_CONFIG, 0x03);  // Modo SpO2 (Red + IR)
  delay(20);

  Serial.println(ok ? "STATUS,INIT_OK" : "STATUS,INIT_FAIL");
  return ok;
}

void runConnectionPhase() {
  Serial.println("STATUS,FASE1_INICIO,VERIFICANDO_MAX30102");

  recoverI2CBus();
  Serial.print("DIAG,PINS_NO_PULLUP,SDA=");
  Serial.print(lastPinNoPullSda);
  Serial.print(",SCL=");
  Serial.println(lastPinNoPullScl);

  // 1) Tenta Hardware Wire primeiro
  useSoftI2C = false;
  configureWireBus();
  delay(20);

  Wire.beginTransmission(MAX30102_I2C_ADDR);
  uint8_t hwErr = Wire.endTransmission();
  bool hwTimeout = checkAndClearWireTimeout();
  bool ackOk = (!hwTimeout && hwErr == 0);

  if (!ackOk) {
    // 2) Fallback automático para Software I2C open-drain (compatível com pull-ups 1.8V/3.3V)
    softI2CInit();
    if (softI2CProbe(MAX30102_I2C_ADDR)) {
      useSoftI2C = true;
      ackOk = true;
    }
  }

  Serial.print("STATUS,I2C_TRANSPORT,");
  Serial.println(useSoftI2C ? "SOFT_I2C" : "HW_WIRE");
  Serial.print("STATUS,I2C_PROBE_0x57,");
  Serial.println(ackOk ? "ACK_OK" : "NO_ACK");

  detectedPartId = 0;
  detectedRevId = 0;
  bool idReadOk = false;
  if (ackOk) {
    idReadOk = readRegister(REG_PART_ID, detectedPartId);
    readRegister(REG_REV_ID, detectedRevId);
  }
  Serial.print("STATUS,PART_ID,0x");
  Serial.print(detectedPartId, HEX);
  Serial.print(",REV_ID,0x");
  Serial.print(detectedRevId, HEX);
  Serial.print(",READ_OK=");
  Serial.println(idReadOk ? 1 : 0);

  max30102Present = (idReadOk && detectedPartId == 0x15) ? initMAX30102() : false;
  i2cErrorStreak = 0;
  Serial.print("STATUS,FASE1_FIM,MAX30102_CONECTADO=");
  Serial.println(max30102Present ? "SIM" : "NAO");
}

// Retorna: 1 = amostra lida com sucesso, 0 = FIFO vazia (aguardando), -1 = erro I2C
int8_t readMAX30102Sample(uint32_t &redRaw, uint32_t &irRaw) {
  static unsigned long lastErrLogMs = 0;
  uint8_t ptrs[3] = {0, 0, 0};  // WR_PTR (0x04), OVF_COUNTER (0x05), RD_PTR (0x06)

  if (!readRegisters(REG_FIFO_WR_PTR, ptrs, 3)) {
    if (millis() - lastErrLogMs >= 500UL) {
      lastErrLogMs = millis();
      Serial.println("ERR_REAL,PTR_READ");
    }
    return -1;
  }

  uint8_t wrPtr = ptrs[0] & 0x1F;
  uint8_t rdPtr = ptrs[2] & 0x1F;
  if (wrPtr == rdPtr) {
    return 0;  // Aguardando próxima amostra de 200 Hz
  }

  uint8_t b[6];
  if (!readRegisters(REG_FIFO_DATA, b, 6)) {
    if (millis() - lastErrLogMs >= 500UL) {
      lastErrLogMs = millis();
      Serial.println("ERR_REAL,FIFO_READ");
    }
    return -1;
  }

  redRaw = (((uint32_t)b[0] << 16) | ((uint32_t)b[1] << 8) | (uint32_t)b[2]) & 0x03FFFFUL;
  irRaw  = (((uint32_t)b[3] << 16) | ((uint32_t)b[4] << 8) | (uint32_t)b[5]) & 0x03FFFFUL;
  return 1;
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

  float systolic  = 1.00f * gaussianPulse(simPhase, 0.25f, 0.085f);
  float dicrotic  = 0.34f * gaussianPulse(simPhase, 0.48f, 0.115f);
  float diastolic = 0.10f * gaussianPulse(simPhase, 0.72f, 0.100f);
  float pulse = (systolic + dicrotic + diastolic) - 0.34f;

  float rRatio = (110.0f - simSpo2) / 25.0f;
  if (rRatio < 0.1f) rRatio = 0.1f;

  const float dcIr  = 100000.0f;
  const float dcRed = 85000.0f;
  const float acIr  = 1200.0f;
  const float acRed = rRatio * (acIr / dcIr) * dcRed;

  float noise60 = simNoise60Hz ? (180.0f * sinf(2.0f * PI * 60.0f * tSec)) : 0.0f;
  float motion  = simMotionDrift ? (320.0f * sinf(2.0f * PI * 0.22f * tSec)) : 0.0f;

  float irVal  = dcIr  - acIr  * pulse + noise60 + motion;
  float redVal = dcRed - acRed * pulse + 0.85f * noise60 + 0.85f * motion;

  irRaw  = (uint32_t)constrain((long)irVal, 0L, 262143L);
  redRaw = (uint32_t)constrain((long)redVal, 0L, 262143L);
}

void printStatus() {
  Serial.print("STATUS,SUMMARY,MAX30102=");
  Serial.print(max30102Present ? "SIM" : "NAO");
  Serial.print(",TRANSPORT=");
  Serial.print(useSoftI2C ? "SOFT_I2C" : "HW_WIRE");
  Serial.print(",PART_ID=0x");
  Serial.print(detectedPartId, HEX);
  Serial.print(",REV_ID=0x");
  Serial.print(detectedRevId, HEX);
  Serial.print(",MODE=");
  Serial.print(requestedMode == MODE_AUTO ? "AUTO" : (requestedMode == MODE_REAL ? "REAL" : "SIM"));
  Serial.print(",TIMEOUTS=");
  Serial.println(i2cTimeoutCount);
}

void processSerialCommand(const String &cmd) {
  if (cmd == "PING") {
    bool usingReal = (requestedMode != MODE_SIM) && max30102Present;
    Serial.print("PONG,PULSE_MONITOR_V1,");
    Serial.println(usingReal ? 0 : 1);
  } else if (cmd == "STATUS") {
    printStatus();
  } else if (cmd == "SCAN") {
    runConnectionPhase();
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
    if (!max30102Present) {
      runConnectionPhase();
    }
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

void emitSample(uint32_t irRaw, uint32_t redRaw, int simFlag) {
  Serial.print("PPG,");
  Serial.print(millis());
  Serial.print(",");
  Serial.print(irRaw);
  Serial.print(",");
  Serial.print(redRaw);
  Serial.print(",");
  Serial.println(simFlag);
}

void setup() {
  Serial.begin(115200);
  unsigned long t0 = millis();
  while (!Serial && (millis() - t0 < 2000)) {}

  runConnectionPhase();
  lastSampleUs = micros();
}

void loop() {
  pollSerialCommands();

  bool useReal = (requestedMode != MODE_SIM) && max30102Present;

  if (useReal) {
    for (uint8_t burst = 0; burst < 4; burst++) {
      uint32_t redRaw = 0;
      uint32_t irRaw = 0;
      int8_t rc = readMAX30102Sample(redRaw, irRaw);
      if (rc == 1) {
        i2cErrorStreak = 0;
        emitSample(irRaw, redRaw, 0);
      } else if (rc == 0) {
        break;
      } else {
        i2cErrorStreak++;
        if (i2cErrorStreak >= 50) {
          Serial.println("STATUS,REAL_LOST_REPROBE");
          runConnectionPhase();
        }
        break;
      }
    }
    return;
  }

  if (requestedMode == MODE_REAL) {
    return;
  }

  unsigned long nowUs = micros();
  if ((unsigned long)(nowUs - lastSampleUs) >= SAMPLE_INTERVAL_US) {
    lastSampleUs += SAMPLE_INTERVAL_US;
    if ((unsigned long)(nowUs - lastSampleUs) > 50000UL) {
      lastSampleUs = nowUs;
    }

    uint32_t redRaw = 0;
    uint32_t irRaw = 0;
    float dtSec = SAMPLE_INTERVAL_US / 1000000.0f;
    float tSec  = millis() / 1000.0f;
    generateSimulatedMAX30102(dtSec, tSec, redRaw, irRaw);
    emitSample(irRaw, redRaw, 1);
  }
}
