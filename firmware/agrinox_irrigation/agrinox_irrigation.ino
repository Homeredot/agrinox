/*
  Agrinox irrigation controller reference firmware

  Libraries:
    - ArduinoJson 7.x
    - DHT sensor library
    - ModbusMaster (only needed when an RS485 NPK sensor is connected)

  Safety rule: the relay is active HIGH in this example and is always driven
  OFF at boot, on stale/invalid measurements, on emergency input, and after a
  network failure while the pump is running. Adapt pins and calibration to the
  exact sensors installed in the field.
*/

#include <Arduino.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <HTTPClient.h>
#include <ModbusMaster.h>
#include <WiFi.h>

// Replace these values before flashing. Never commit a production device key.
const char *WIFI_SSID = "YOUR_WIFI_NAME";
const char *WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char *SERVER_BASE_URL = "http://192.168.1.10:8000/api/v1";
const char *DEVICE_ID = "DEVICE_UID_FROM_AGRINOX";
const char *DEVICE_KEY = "ONE_TIME_DEVICE_KEY_FROM_AGRINOX";

constexpr uint8_t SOIL_MOISTURE_PIN = 34;
constexpr uint8_t DHT_PIN = 4;
constexpr uint8_t ULTRASONIC_TRIG_PIN = 5;
constexpr uint8_t ULTRASONIC_ECHO_PIN = 18;
constexpr uint8_t FLOW_PIN = 27;
constexpr uint8_t RELAY_PIN = 26;
constexpr uint8_t EMERGENCY_STOP_PIN = 25;
constexpr uint8_t RS485_RX_PIN = 16;
constexpr uint8_t RS485_TX_PIN = 17;
constexpr uint8_t RS485_DE_RE_PIN = 21;

constexpr int SOIL_ADC_DRY = 3200;  // Calibrate in dry reference soil.
constexpr int SOIL_ADC_WET = 1350;  // Calibrate in saturated reference soil.
constexpr float TANK_HEIGHT_CM = 150.0;
constexpr unsigned long SENSOR_INTERVAL_MS = 30000;
constexpr unsigned long COMMAND_INTERVAL_MS = 5000;
constexpr unsigned long CONFIG_INTERVAL_MS = 60000;
constexpr unsigned long WIFI_FAILSAFE_MS = 15000;
constexpr size_t BUFFER_CAPACITY = 12;

DHT dht(DHT_PIN, DHT22);
HardwareSerial npkSerial(2);
ModbusMaster npk;

volatile uint32_t flowPulses = 0;
bool pumpRunning = false;
bool emergencyLatched = false;
unsigned long pumpStartedAt = 0;
unsigned long pumpStopAt = 0;
unsigned long lastPumpStoppedAt = 0;
unsigned long lastValidReadingAt = 0;
unsigned long wifiLostAt = 0;
long activeCommandId = -1;
long pendingFailureCommandId = -1;
String pendingFailureMessage;

struct SafetyConfig {
  bool remoteEnabled = false;
  bool deviceRemoteEnabled = false;
  bool emergencyStop = true;
  bool safetyValidated = false;
  unsigned long maxRuntimeMs = 600000;
  unsigned long cooldownMs = 900000;
  float minTankPercent = 15.0;
  unsigned long maxReadingAgeMs = 1800000;
} safety;

struct Snapshot {
  float soilMoisture;
  float temperature;
  float humidity;
  float tankPercent;
  float flowLitersMinute;
  float nitrogen;
  float phosphorus;
  float potassium;
  bool npkValid;
  bool valid;
};

Snapshot buffer[BUFFER_CAPACITY];
size_t bufferHead = 0;
size_t bufferCount = 0;
Snapshot latestSnapshot{};

void IRAM_ATTR onFlowPulse() { flowPulses++; }

void rs485Transmit() { digitalWrite(RS485_DE_RE_PIN, HIGH); }
void rs485Receive() { digitalWrite(RS485_DE_RE_PIN, LOW); }

void pumpOff() {
  digitalWrite(RELAY_PIN, LOW);
  pumpRunning = false;
  pumpStopAt = 0;
  lastPumpStoppedAt = millis();
}

bool finiteRange(float value, float minimum, float maximum) {
  return isfinite(value) && value >= minimum && value <= maximum;
}

float readSoilMoisture() {
  int raw = analogRead(SOIL_MOISTURE_PIN);
  return constrain(100.0f * (SOIL_ADC_DRY - raw) / float(SOIL_ADC_DRY - SOIL_ADC_WET), 0.0f, 100.0f);
}

float readTankPercent() {
  digitalWrite(ULTRASONIC_TRIG_PIN, LOW);
  delayMicroseconds(3);
  digitalWrite(ULTRASONIC_TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(ULTRASONIC_TRIG_PIN, LOW);
  unsigned long duration = pulseIn(ULTRASONIC_ECHO_PIN, HIGH, 35000);
  if (duration == 0) return NAN;
  float distanceCm = duration * 0.0343f / 2.0f;
  return constrain((TANK_HEIGHT_CM - distanceCm) * 100.0f / TANK_HEIGHT_CM, 0.0f, 100.0f);
}

bool readNpk(float &nitrogen, float &phosphorus, float &potassium) {
  // Common RS485 NPK probes expose N/P/K at holding register 0x001E.
  // Confirm the address and scaling in the probe's own manual.
  uint8_t result = npk.readHoldingRegisters(0x001E, 3);
  if (result != npk.ku8MBSuccess) return false;
  nitrogen = npk.getResponseBuffer(0);
  phosphorus = npk.getResponseBuffer(1);
  potassium = npk.getResponseBuffer(2);
  return finiteRange(nitrogen, 0, 10000) && finiteRange(phosphorus, 0, 10000) && finiteRange(potassium, 0, 10000);
}

Snapshot sampleSensors() {
  static unsigned long lastFlowSample = millis();
  static uint32_t previousPulses = 0;
  Snapshot sample{};
  sample.soilMoisture = readSoilMoisture();
  sample.temperature = dht.readTemperature();
  sample.humidity = dht.readHumidity();
  sample.tankPercent = readTankPercent();
  noInterrupts();
  uint32_t pulses = flowPulses;
  interrupts();
  unsigned long elapsed = max(1UL, millis() - lastFlowSample);
  sample.flowLitersMinute = ((pulses - previousPulses) / 7.5f) * (60000.0f / elapsed); // Calibrate pulses/litre.
  previousPulses = pulses;
  lastFlowSample = millis();
  sample.npkValid = readNpk(sample.nitrogen, sample.phosphorus, sample.potassium);
  sample.valid = finiteRange(sample.soilMoisture, 0, 100) &&
                 finiteRange(sample.temperature, -20, 80) &&
                 finiteRange(sample.humidity, 0, 100) &&
                 finiteRange(sample.tankPercent, 0, 100) &&
                 finiteRange(sample.flowLitersMinute, 0, 1000);
  if (sample.valid) lastValidReadingAt = millis();
  return sample;
}

void enqueueSnapshot(const Snapshot &sample) {
  size_t index = (bufferHead + bufferCount) % BUFFER_CAPACITY;
  if (bufferCount == BUFFER_CAPACITY) {
    bufferHead = (bufferHead + 1) % BUFFER_CAPACITY;
    index = (bufferHead + bufferCount - 1) % BUFFER_CAPACITY;
  } else {
    bufferCount++;
  }
  buffer[index] = sample;
}

void addReading(JsonArray readings, const char *key, float value, const char *unit, bool valid) {
  JsonObject item = readings.add<JsonObject>();
  item["key"] = key;
  item["value"] = isfinite(value) ? value : 0;
  item["unit"] = unit;
  item["valid"] = valid;
  item["simulated"] = false;
}

bool beginRequest(HTTPClient &http, const String &url) {
  if (WiFi.status() != WL_CONNECTED || !http.begin(url)) return false;
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-ID", DEVICE_ID);
  http.addHeader("X-Device-Key", DEVICE_KEY);
  http.setTimeout(5000);
  return true;
}

bool sendSnapshot(const Snapshot &sample) {
  JsonDocument document;
  document["firmware_version"] = "agrinox-irrigation-1.0.0";
  JsonArray readings = document["readings"].to<JsonArray>();
  addReading(readings, "soil_moisture", sample.soilMoisture, "%", finiteRange(sample.soilMoisture, 0, 100));
  addReading(readings, "temperature", sample.temperature, "C", finiteRange(sample.temperature, -20, 80));
  addReading(readings, "humidity", sample.humidity, "%", finiteRange(sample.humidity, 0, 100));
  addReading(readings, "tank_level", sample.tankPercent, "%", finiteRange(sample.tankPercent, 0, 100));
  addReading(readings, "flow_rate", sample.flowLitersMinute, "L/min", finiteRange(sample.flowLitersMinute, 0, 1000));
  if (sample.npkValid) {
    addReading(readings, "nitrogen", sample.nitrogen, "mg/kg", true);
    addReading(readings, "phosphorus", sample.phosphorus, "mg/kg", true);
    addReading(readings, "potassium", sample.potassium, "mg/kg", true);
  }
  String body;
  serializeJson(document, body);
  HTTPClient http;
  if (!beginRequest(http, String(SERVER_BASE_URL) + "/iot/readings")) return false;
  int status = http.POST(body);
  http.end();
  return status >= 200 && status < 300;
}

void flushBuffer() {
  while (bufferCount > 0 && WiFi.status() == WL_CONNECTED) {
    if (!sendSnapshot(buffer[bufferHead])) return;
    bufferHead = (bufferHead + 1) % BUFFER_CAPACITY;
    bufferCount--;
  }
}

bool reportCommand(long commandId, const char *status, const String &message) {
  JsonDocument document;
  document["status"] = status;
  document["message"] = message;
  String body;
  serializeJson(document, body);
  HTTPClient http;
  if (!beginRequest(http, String(SERVER_BASE_URL) + "/iot/commands/" + commandId + "/status")) return false;
  int response = http.POST(body);
  http.end();
  return response >= 200 && response < 300;
}

void stopActiveWithFailure(const String &message) {
  if (!pumpRunning && activeCommandId < 1) {
    digitalWrite(RELAY_PIN, LOW);
    return;
  }
  long commandId = activeCommandId;
  pumpOff();
  activeCommandId = -1;
  if (commandId < 1) return;
  if (!reportCommand(commandId, "failed", message + "; pump OFF")) {
    pendingFailureCommandId = commandId;
    pendingFailureMessage = message + "; pump OFF";
  }
}

bool safeToStart(unsigned long durationMs, String &reason) {
  if (emergencyLatched || digitalRead(EMERGENCY_STOP_PIN) == LOW || safety.emergencyStop) reason = "Emergency stop is active";
  else if (!safety.remoteEnabled || !safety.deviceRemoteEnabled || !safety.safetyValidated) reason = "Remote control or safety validation is disabled";
  else if (!latestSnapshot.valid || millis() - lastValidReadingAt > safety.maxReadingAgeMs) reason = "Sensor readings are invalid or stale";
  else if (latestSnapshot.tankPercent < safety.minTankPercent) reason = "Tank is below the configured safety minimum";
  else if (durationMs > safety.maxRuntimeMs) reason = "Requested runtime exceeds the configured maximum";
  else if (lastPumpStoppedAt && millis() - lastPumpStoppedAt < safety.cooldownMs) reason = "Pump cooldown is still active";
  else return true;
  return false;
}

void fetchConfig() {
  HTTPClient http;
  if (!beginRequest(http, String(SERVER_BASE_URL) + "/iot/config")) return;
  int response = http.GET();
  if (response == 200) {
    JsonDocument document;
    if (deserializeJson(document, http.getString()) == DeserializationError::Ok) {
      safety.remoteEnabled = document["remote_control_enabled"] | false;
      safety.deviceRemoteEnabled = document["device_remote_control_enabled"] | false;
      safety.emergencyStop = document["emergency_stop"] | true;
      safety.safetyValidated = document["safety_validated"] | false;
      safety.maxRuntimeMs = 1000UL * (document["max_pump_runtime_seconds"] | 600);
      safety.cooldownMs = 60000UL * (document["cooldown_minutes"] | 15);
      safety.minTankPercent = document["min_tank_percent"] | 15.0;
      safety.maxReadingAgeMs = 60000UL * (document["max_reading_age_minutes"] | 30);
    }
  }
  http.end();
}

void handleCommand(JsonObject command) {
  long commandId = command["id"] | -1;
  String action = command["command"] | "";
  if (commandId < 1) return;
  if (action == "stop" || action == "emergency_stop") {
    pumpOff();
    if (action == "emergency_stop") emergencyLatched = true;
    reportCommand(commandId, "executed", action == "stop" ? "Pump OFF" : "Emergency stop applied; pump OFF");
    return;
  }
  if (action != "start") {
    reportCommand(commandId, "rejected", "Unknown command; pump remains OFF");
    return;
  }
  unsigned long durationMs = 1000UL * (command["duration_seconds"] | 0);
  String reason;
  if (!safeToStart(durationMs, reason)) {
    pumpOff();
    reportCommand(commandId, "rejected", reason + "; pump remains OFF");
    return;
  }
  digitalWrite(RELAY_PIN, HIGH);
  pumpRunning = true;
  pumpStartedAt = millis();
  pumpStopAt = pumpStartedAt + durationMs;
  activeCommandId = commandId;
  reportCommand(commandId, "executed", "Pump ON; local maximum-runtime cutoff armed");
}

void fetchCommands() {
  HTTPClient http;
  if (!beginRequest(http, String(SERVER_BASE_URL) + "/iot/commands")) return;
  int response = http.GET();
  if (response == 200) {
    JsonDocument document;
    if (deserializeJson(document, http.getString()) == DeserializationError::Ok) {
      for (JsonObject command : document.as<JsonArray>()) handleCommand(command);
    }
  }
  http.end();
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long started = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - started < 10000) delay(250);
}

void setup() {
  pinMode(RELAY_PIN, OUTPUT);
  pumpOff();
  lastPumpStoppedAt = 0; // Boot OFF is not a previous irrigation cycle.
  pinMode(EMERGENCY_STOP_PIN, INPUT_PULLUP);
  pinMode(ULTRASONIC_TRIG_PIN, OUTPUT);
  pinMode(ULTRASONIC_ECHO_PIN, INPUT);
  pinMode(FLOW_PIN, INPUT_PULLUP);
  pinMode(RS485_DE_RE_PIN, OUTPUT);
  rs485Receive();
  attachInterrupt(digitalPinToInterrupt(FLOW_PIN), onFlowPulse, FALLING);
  Serial.begin(115200);
  dht.begin();
  npkSerial.begin(9600, SERIAL_8N1, RS485_RX_PIN, RS485_TX_PIN);
  npk.begin(1, npkSerial);
  npk.preTransmission(rs485Transmit);
  npk.postTransmission(rs485Receive);
  connectWiFi();
  fetchConfig();
}

void loop() {
  static unsigned long lastSensorAt = 0;
  static unsigned long lastCommandAt = 0;
  static unsigned long lastConfigAt = 0;

  if (digitalRead(EMERGENCY_STOP_PIN) == LOW) {
    emergencyLatched = true;
    stopActiveWithFailure("Physical emergency stop activated");
  }
  if (pumpRunning && (millis() >= pumpStopAt || millis() - pumpStartedAt >= safety.maxRuntimeMs)) {
    pumpOff();
    if (activeCommandId > 0) reportCommand(activeCommandId, "completed", "Runtime completed; pump OFF");
    activeCommandId = -1;
  }

  if (WiFi.status() != WL_CONNECTED) {
    if (!wifiLostAt) wifiLostAt = millis();
    if (pumpRunning && millis() - wifiLostAt >= WIFI_FAILSAFE_MS) {
      stopActiveWithFailure("Network connection was unavailable beyond the fail-safe limit");
    }
    connectWiFi();
  } else {
    wifiLostAt = 0;
    if (pendingFailureCommandId > 0 && reportCommand(pendingFailureCommandId, "failed", pendingFailureMessage)) {
      pendingFailureCommandId = -1;
      pendingFailureMessage = "";
    }
  }

  if (millis() - lastSensorAt >= SENSOR_INTERVAL_MS) {
    lastSensorAt = millis();
    latestSnapshot = sampleSensors();
    if (!sendSnapshot(latestSnapshot)) enqueueSnapshot(latestSnapshot);
    else flushBuffer();
    if (!latestSnapshot.valid) stopActiveWithFailure("A required sensor reading became invalid");
    else if (latestSnapshot.tankPercent < safety.minTankPercent) stopActiveWithFailure("Tank level fell below the safety minimum");
  }
  if (millis() - lastConfigAt >= CONFIG_INTERVAL_MS) {
    lastConfigAt = millis();
    fetchConfig();
    if (safety.emergencyStop || !safety.remoteEnabled || !safety.deviceRemoteEnabled) stopActiveWithFailure("Server safety configuration no longer permits pumping");
  }
  if (millis() - lastCommandAt >= COMMAND_INTERVAL_MS) {
    lastCommandAt = millis();
    fetchCommands();
  }
  delay(10);
}
