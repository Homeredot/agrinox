/*
  Agrinox ESP32 — RS485 soil NPK sensor only

  Wiring (ESP32 UART2):
    Sensor RO  -> ESP32 RX2 / GPIO16
    Sensor DI  -> ESP32 TX2 / GPIO17
    RS485 RE   -> ESP32 GPIO4
    RS485 DE   -> ESP32 GPIO5
    Sensor VCC -> the voltage required by the sensor/RS485 board
    Sensor GND -> power ground, shared with ESP32 GND

  Required Arduino libraries:
    - ModbusMaster by Doc Walker
    - ArduinoJson 7.x

  The common NPK register layout used here is slave 1, 9600 baud, holding
  registers 0x001E..0x0020 for N, P and K. Confirm these values in the exact
  sensor manual before relying on readings.
*/

#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <ModbusMaster.h>
#include <Preferences.h>
#include <WiFi.h>

// ---------- Your wiring ----------
constexpr uint8_t RS485_RX_PIN = 16;  // RX2 <- sensor RO
constexpr uint8_t RS485_TX_PIN = 17;  // TX2 -> sensor DI
constexpr uint8_t RS485_RE_PIN = 4;
constexpr uint8_t RS485_DE_PIN = 5;

constexpr uint8_t NPK_SLAVE_ID = 1;
constexpr uint32_t NPK_BAUD_RATE = 9600;
constexpr uint16_t NPK_FIRST_REGISTER = 0x001E;
constexpr unsigned long UPLOAD_INTERVAL_MS = 60000;
constexpr unsigned long HEARTBEAT_INTERVAL_MS = 30000;
constexpr unsigned long WIFI_RETRY_INTERVAL_MS = 10000;
constexpr size_t BUFFER_SIZE = 10;
constexpr char FIRMWARE_VERSION[] = "agrinox-npk-1.1.0";

HardwareSerial npkSerial(2);
ModbusMaster npk;
Preferences preferences;
String wifiSsid;
String wifiPassword;
String serverBaseUrl;
String deviceKey;

struct NpkReading {
  float nitrogen;
  float phosphorus;
  float potassium;
};

NpkReading readingBuffer[BUFFER_SIZE];
size_t bufferHead = 0;
size_t bufferCount = 0;
unsigned long lastUploadAt = 0;
unsigned long lastHeartbeatAt = 0;
unsigned long lastWifiAttemptAt = 0;

String deviceUid() {
  const uint64_t chipId = ESP.getEfuseMac();
  char value[32];
  snprintf(value, sizeof(value), "esp32-%04x%08x",
           static_cast<uint16_t>(chipId >> 32),
           static_cast<uint32_t>(chipId));
  return String(value);
}

void rs485Transmit() {
  digitalWrite(RS485_RE_PIN, HIGH);  // Disable receiver (RE is active LOW).
  digitalWrite(RS485_DE_PIN, HIGH);  // Enable transmitter.
  delayMicroseconds(200);
}

void rs485Receive() {
  delayMicroseconds(200);
  digitalWrite(RS485_DE_PIN, LOW);   // Disable transmitter.
  digitalWrite(RS485_RE_PIN, LOW);   // Enable receiver.
}

bool plausibleNpk(float value) {
  // This rejects corrupt Modbus responses, not agronomic extremes.
  return isfinite(value) && value >= 0.0f && value <= 10000.0f;
}

bool readNpk(NpkReading &reading) {
  npk.clearResponseBuffer();
  const uint8_t result = npk.readHoldingRegisters(NPK_FIRST_REGISTER, 3);
  if (result != npk.ku8MBSuccess) return false;

  reading.nitrogen = static_cast<float>(npk.getResponseBuffer(0));
  reading.phosphorus = static_cast<float>(npk.getResponseBuffer(1));
  reading.potassium = static_cast<float>(npk.getResponseBuffer(2));
  return plausibleNpk(reading.nitrogen) &&
         plausibleNpk(reading.phosphorus) &&
         plausibleNpk(reading.potassium);
}

void enqueueReading(const NpkReading &reading) {
  if (bufferCount == BUFFER_SIZE) {
    // Keep the newest samples when the network has been unavailable for long.
    bufferHead = (bufferHead + 1) % BUFFER_SIZE;
    bufferCount--;
  }
  const size_t index = (bufferHead + bufferCount) % BUFFER_SIZE;
  readingBuffer[index] = reading;
  bufferCount++;
}

void addReading(JsonArray readings, const char *key, float value) {
  JsonObject item = readings.add<JsonObject>();
  item["key"] = key;
  item["value"] = value;
  item["unit"] = "mg/kg";
  item["valid"] = true;
  item["simulated"] = false;
}

bool credentialsConfigured() {
  return wifiSsid.length() > 0 && serverBaseUrl.length() > 0 && deviceKey.length() > 0;
}

bool uploadReading(const NpkReading &reading) {
  if (WiFi.status() != WL_CONNECTED || !credentialsConfigured()) return false;

  JsonDocument document;
  document["firmware_version"] = FIRMWARE_VERSION;
  JsonArray readings = document["readings"].to<JsonArray>();
  addReading(readings, "nitrogen", reading.nitrogen);
  addReading(readings, "phosphorus", reading.phosphorus);
  addReading(readings, "potassium", reading.potassium);

  String body;
  serializeJson(document, body);

  HTTPClient http;
  const String url = serverBaseUrl + "/iot/readings";
  if (!http.begin(url)) return false;
  http.setTimeout(7000);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-ID", deviceUid());
  http.addHeader("X-Device-Key", deviceKey);
  const int status = http.POST(body);
  http.end();
  return status >= 200 && status < 300;
}

bool sendHeartbeat() {
  if (WiFi.status() != WL_CONNECTED || !credentialsConfigured()) return false;

  JsonDocument document;
  document["firmware_version"] = FIRMWARE_VERSION;
  document["wifi_rssi"] = WiFi.RSSI();
  document["ip_address"] = WiFi.localIP().toString();
  String body;
  serializeJson(document, body);

  HTTPClient http;
  const String url = serverBaseUrl + "/iot/heartbeat";
  if (!http.begin(url)) return false;
  http.setTimeout(7000);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-ID", deviceUid());
  http.addHeader("X-Device-Key", deviceKey);
  const int status = http.POST(body);
  http.end();
  return status >= 200 && status < 300;
}

void flushBuffer() {
  while (bufferCount > 0 && WiFi.status() == WL_CONNECTED) {
    if (!uploadReading(readingBuffer[bufferHead])) return;
    bufferHead = (bufferHead + 1) % BUFFER_SIZE;
    bufferCount--;
  }
}

void maintainWifi() {
  if (wifiSsid.length() == 0) return;
  if (WiFi.status() == WL_CONNECTED) return;
  const unsigned long now = millis();
  if (now - lastWifiAttemptAt < WIFI_RETRY_INTERVAL_MS) return;
  lastWifiAttemptAt = now;
  WiFi.disconnect();
  WiFi.begin(wifiSsid.c_str(), wifiPassword.c_str());
}

void loadConfiguration() {
  preferences.begin("agrinox", true);
  wifiSsid = preferences.getString("wifi_ssid", "");
  wifiPassword = preferences.getString("wifi_pass", "");
  serverBaseUrl = preferences.getString("server_url", "");
  deviceKey = preferences.getString("device_key", "");
  preferences.end();
}

void sendConfigurationStatus(bool saved, const char *message) {
  JsonDocument document;
  document["protocol"] = "agrinox-1";
  document["configured"] = saved;
  document["message"] = message;
  document["device_uid"] = deviceUid();
  serializeJson(document, Serial);
  Serial.println();
}

void saveConfiguration(const String &json) {
  JsonDocument document;
  if (deserializeJson(document, json) != DeserializationError::Ok) {
    sendConfigurationStatus(false, "Invalid configuration JSON");
    return;
  }
  const char *ssid = document["wifi_ssid"] | "";
  const char *password = document["wifi_password"] | "";
  const char *server = document["server_url"] | "";
  const char *key = document["device_key"] | "";
  if (strlen(ssid) == 0 || strlen(server) == 0 || strlen(key) == 0) {
    sendConfigurationStatus(false, "Wi-Fi, server URL and device key are required");
    return;
  }
  preferences.begin("agrinox", false);
  preferences.putString("wifi_ssid", ssid);
  preferences.putString("wifi_pass", password);
  preferences.putString("server_url", server);
  preferences.putString("device_key", key);
  preferences.end();
  loadConfiguration();
  WiFi.disconnect(true);
  WiFi.begin(wifiSsid.c_str(), wifiPassword.c_str());
  lastWifiAttemptAt = millis();
  sendConfigurationStatus(true, "Configuration saved");
}

void sendDiscovery() {
  JsonDocument document;
  document["protocol"] = "agrinox-1";
  document["device_uid"] = deviceUid();
  document["board"] = "ESP32 NPK monitor";
  document["firmware"] = FIRMWARE_VERSION;
  JsonArray sensors = document["sensors"].to<JsonArray>();

  JsonObject nitrogen = sensors.add<JsonObject>();
  nitrogen["key"] = "nitrogen";
  nitrogen["name"] = "Soil nitrogen (N)";
  nitrogen["type"] = "nitrogen";
  nitrogen["unit"] = "mg/kg";
  nitrogen["pin"] = "RS485 RX2/TX2";

  JsonObject phosphorus = sensors.add<JsonObject>();
  phosphorus["key"] = "phosphorus";
  phosphorus["name"] = "Soil phosphorus (P)";
  phosphorus["type"] = "phosphorus";
  phosphorus["unit"] = "mg/kg";
  phosphorus["pin"] = "RS485 RX2/TX2";

  JsonObject potassium = sensors.add<JsonObject>();
  potassium["key"] = "potassium";
  potassium["name"] = "Soil potassium (K)";
  potassium["type"] = "potassium";
  potassium["unit"] = "mg/kg";
  potassium["pin"] = "RS485 RX2/TX2";

  serializeJson(document, Serial);
  Serial.println();
}

void sendUsbReading() {
  NpkReading reading{};
  JsonDocument document;
  document["protocol"] = "agrinox-1";
  JsonObject readings = document["readings"].to<JsonObject>();
  if (readNpk(reading)) {
    readings["nitrogen"] = reading.nitrogen;
    readings["phosphorus"] = reading.phosphorus;
    readings["potassium"] = reading.potassium;
  } else {
    document["error"] = "NPK sensor did not return a valid Modbus response";
  }
  serializeJson(document, Serial);
  Serial.println();
}

void handleUsbCommands() {
  if (!Serial.available()) return;
  String command = Serial.readStringUntil('\n');
  command.trim();
  if (command == "AGRINOX_DISCOVER") {
    sendDiscovery();
  } else if (command == "AGRINOX_READ") {
    sendUsbReading();
  } else if (command.startsWith("AGRINOX_CONFIG ")) {
    saveConfiguration(command.substring(15));
  }
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(2500);

  pinMode(RS485_RE_PIN, OUTPUT);
  pinMode(RS485_DE_PIN, OUTPUT);
  rs485Receive();

  npkSerial.begin(NPK_BAUD_RATE, SERIAL_8N1, RS485_RX_PIN, RS485_TX_PIN);
  npk.begin(NPK_SLAVE_ID, npkSerial);
  npk.preTransmission(rs485Transmit);
  npk.postTransmission(rs485Receive);

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(false);
  loadConfiguration();
  if (wifiSsid.length() > 0) WiFi.begin(wifiSsid.c_str(), wifiPassword.c_str());
  lastWifiAttemptAt = millis();
}

void loop() {
  handleUsbCommands();
  maintainWifi();
  if (WiFi.status() == WL_CONNECTED) flushBuffer();

  const unsigned long now = millis();
  if (WiFi.status() == WL_CONNECTED &&
      (lastHeartbeatAt == 0 || now - lastHeartbeatAt >= HEARTBEAT_INTERVAL_MS)) {
    lastHeartbeatAt = now;
    sendHeartbeat();
  }
  if (now - lastUploadAt < UPLOAD_INTERVAL_MS) {
    delay(5);
    return;
  }
  lastUploadAt = now;

  NpkReading reading{};
  if (!readNpk(reading)) return;

  // Send immediately when possible; otherwise preserve it for a later retry.
  if (!uploadReading(reading)) enqueueReading(reading);
}

