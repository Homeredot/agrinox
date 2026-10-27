#include <Arduino.h>

// Example hardware: an analog soil sensor signal connected to GPIO 34.
// This reports the uncalibrated ADC value honestly as "raw". Calibrate the
// sensor before changing the unit and value to a moisture percentage.
constexpr uint8_t SOIL_SENSOR_PIN = 34;
constexpr unsigned long SERIAL_BAUD = 115200;

String jsonEscape(const String &value) {
  String escaped;
  escaped.reserve(value.length());
  for (size_t index = 0; index < value.length(); index++) {
    const char character = value.charAt(index);
    if (character == '\\' || character == '"') escaped += '\\';
    escaped += character;
  }
  return escaped;
}

String deviceUid() {
  const uint64_t chipId = ESP.getEfuseMac();
  char value[32];
  snprintf(value, sizeof(value), "esp32-%04x%08x",
           static_cast<uint16_t>(chipId >> 32),
           static_cast<uint32_t>(chipId));
  return String(value);
}

void sendDiscovery() {
  Serial.print("{\"protocol\":\"agrinox-1\",\"device_uid\":\"");
  Serial.print(jsonEscape(deviceUid()));
  Serial.println("\",\"board\":\"ESP32\",\"firmware\":\"1.0.0\",\"sensors\":[{\"key\":\"soil_adc\",\"name\":\"Soil sensor\",\"type\":\"soil_moisture_raw\",\"unit\":\"raw\",\"pin\":\"GPIO34\"}]}");
}

void sendReadings() {
  const int soilAdc = analogRead(SOIL_SENSOR_PIN);
  Serial.print("{\"protocol\":\"agrinox-1\",\"readings\":{\"soil_adc\":");
  Serial.print(soilAdc);
  Serial.println("}}");
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  pinMode(SOIL_SENSOR_PIN, INPUT);
}

void loop() {
  if (!Serial.available()) return;

  const String command = Serial.readStringUntil('\n');
  if (command == "AGRINOX_DISCOVER") {
    sendDiscovery();
  } else if (command == "AGRINOX_READ") {
    sendReadings();
  }
}
