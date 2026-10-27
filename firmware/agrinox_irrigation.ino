/* Agrinox field device example (ESP32)
   Required libraries: ArduinoJson, DHT sensor library, ModbusMaster.
   Replace the configuration values before flashing. Relay is active LOW here;
   verify your relay electrically. Pump is forced OFF on boot and failures. */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <ModbusMaster.h>

const char* WIFI_SSID = "CHANGE_ME";
const char* WIFI_PASSWORD = "CHANGE_ME";
const char* API_BASE = "http://192.168.1.10:8000/api/v1";
const char* DEVICE_ID = "CHANGE_TO_DEVICE_UID";
const char* DEVICE_KEY = "CHANGE_TO_ONE_TIME_DEVICE_KEY";

constexpr int SOIL_PIN = 34;
constexpr int WATER_LEVEL_PIN = 35;
constexpr int DHT_PIN = 4;
constexpr int TRIG_PIN = 5;
constexpr int ECHO_PIN = 18;
constexpr int RELAY_PIN = 23;
constexpr int RS485_RX = 16;
constexpr int RS485_TX = 17;
constexpr int RELAY_OFF = HIGH;
constexpr int RELAY_ON = LOW;
constexpr unsigned long SEND_EVERY_MS = 60000;
constexpr unsigned long COMMAND_EVERY_MS = 10000;
constexpr unsigned long LOCAL_MAX_PUMP_MS = 600000;
constexpr float LOCAL_MIN_TANK_PERCENT = 15.0;

DHT dht(DHT_PIN, DHT22);  // Change to DHT11 when required.
HardwareSerial rs485(2);
ModbusMaster npk;
String readingBuffer[10];
int bufferHead = 0, bufferCount = 0;
unsigned long lastSend = 0, lastCommandPoll = 0, pumpStartedAt = 0;
bool pumpRunning = false;

void pumpOff() {
  digitalWrite(RELAY_PIN, RELAY_OFF);
  pumpRunning = false;
  pumpStartedAt = 0;
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  pumpOff(); // Network loss must not leave an unmonitored pump running.
  WiFi.disconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long started = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - started < 15000) delay(300);
}

float soilMoisturePercent() {
  int raw = analogRead(SOIL_PIN);
  return constrain(100.0f * (3000 - raw) / (3000 - 1200), 0.0f, 100.0f); // Calibrate dry/wet values locally.
}

float tankLevelPercent() {
  digitalWrite(TRIG_PIN, LOW); delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10); digitalWrite(TRIG_PIN, LOW);
  long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  if (duration <= 0) return -1;
  float distanceCm = duration * 0.0343f / 2.0f;
  return constrain(100.0f * (100.0f - distanceCm) / 90.0f, 0.0f, 100.0f); // Configure tank geometry.
}

bool readNpk(float &n, float &p, float &k) {
  uint8_t result = npk.readHoldingRegisters(0x001E, 3); // Confirm registers in the sensor manual.
  if (result != npk.ku8MBSuccess) return false;
  n = npk.getResponseBuffer(0); p = npk.getResponseBuffer(1); k = npk.getResponseBuffer(2);
  return n >= 0 && n <= 10000 && p >= 0 && p <= 10000 && k >= 0 && k <= 10000;
}

void addReading(JsonArray readings, const char* key, float value, const char* unit, bool valid) {
  JsonObject item = readings.add<JsonObject>();
  item["key"] = key; item["value"] = value; item["unit"] = unit; item["valid"] = valid; item["simulated"] = false;
}

String collectReadings() {
  DynamicJsonDocument doc(2048);
  doc["firmware_version"] = "irrigation-1.0.0";
  JsonArray readings = doc.createNestedArray("readings");
  float moisture = soilMoisturePercent();
  float tank = tankLevelPercent();
  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();
  float n = 0, p = 0, k = 0;
  addReading(readings, "soil_moisture", moisture, "%", moisture >= 0 && moisture <= 100);
  addReading(readings, "tank_level", tank, "%", tank >= 0 && tank <= 100);
  addReading(readings, "temperature", temperature, "°C", !isnan(temperature) && temperature >= -20 && temperature <= 80);
  addReading(readings, "humidity", humidity, "%", !isnan(humidity) && humidity >= 0 && humidity <= 100);
  if (readNpk(n, p, k)) {
    addReading(readings, "nitrogen", n, "mg/kg", true);
    addReading(readings, "phosphorus", p, "mg/kg", true);
    addReading(readings, "potassium", k, "mg/kg", true);
  }
  String body; serializeJson(doc, body); return body;
}

void bufferReading(const String &body) {
  int index = (bufferHead + bufferCount) % 10;
  readingBuffer[index] = body;
  if (bufferCount < 10) bufferCount++; else bufferHead = (bufferHead + 1) % 10;
}

bool apiRequest(const String &path, const char* method, const String &body, String &response) {
  if (WiFi.status() != WL_CONNECTED) return false;
  HTTPClient http;
  http.begin(String(API_BASE) + path);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-ID", DEVICE_ID);
  http.addHeader("X-Device-Key", DEVICE_KEY);
  int code = strcmp(method, "GET") == 0 ? http.GET() : http.POST(body);
  response = http.getString(); http.end();
  return code >= 200 && code < 300;
}

void flushReadings() {
  while (bufferCount > 0) {
    String response;
    if (!apiRequest("/iot/readings", "POST", readingBuffer[bufferHead], response)) return;
    readingBuffer[bufferHead] = ""; bufferHead = (bufferHead + 1) % 10; bufferCount--;
  }
}

void reportCommand(int id, const char* status, const char* message) {
  DynamicJsonDocument doc(256); doc["status"] = status; doc["message"] = message;
  String body, response; serializeJson(doc, body);
  apiRequest("/iot/commands/" + String(id) + "/status", "POST", body, response);
}

void pollCommands() {
  String automaticResponse;
  // A 409 response is normal when automatic mode is off or irrigation is not recommended.
  apiRequest("/iot/automatic/evaluate", "POST", "{}", automaticResponse);
  String response;
  if (!apiRequest("/iot/commands", "GET", "", response)) { pumpOff(); return; }
  DynamicJsonDocument doc(4096);
  if (deserializeJson(doc, response)) { pumpOff(); return; }
  for (JsonObject command : doc.as<JsonArray>()) {
    int id = command["id"];
    String action = command["command"].as<String>();
    if (command["simulated"] | false) { reportCommand(id, "executed", "SIMULATED command acknowledged; relay was not changed"); continue; }
    if (action == "stop" || action == "emergency_stop") { pumpOff(); reportCommand(id, "executed", "Pump switched OFF"); continue; }
    float tank = tankLevelPercent();
    unsigned long requestedMs = min((unsigned long)(command["duration_seconds"] | 0) * 1000UL, LOCAL_MAX_PUMP_MS);
    if (action != "start" || tank < LOCAL_MIN_TANK_PERCENT || requestedMs == 0) { pumpOff(); reportCommand(id, "rejected", "Local tank/runtime safety check failed"); continue; }
    digitalWrite(RELAY_PIN, RELAY_ON); pumpRunning = true; pumpStartedAt = millis();
    reportCommand(id, "executed", "Pump switched ON; local maximum runtime guard active");
  }
}

void setup() {
  pinMode(RELAY_PIN, OUTPUT); pumpOff();
  pinMode(TRIG_PIN, OUTPUT); pinMode(ECHO_PIN, INPUT);
  analogReadResolution(12); dht.begin();
  rs485.begin(9600, SERIAL_8N1, RS485_RX, RS485_TX); npk.begin(1, rs485);
  connectWiFi();
}

void loop() {
  if (pumpRunning && millis() - pumpStartedAt >= LOCAL_MAX_PUMP_MS) pumpOff();
  connectWiFi();
  if (millis() - lastSend >= SEND_EVERY_MS) { lastSend = millis(); bufferReading(collectReadings()); flushReadings(); }
  if (millis() - lastCommandPoll >= COMMAND_EVERY_MS) { lastCommandPoll = millis(); pollCommands(); }
  delay(100);
}
