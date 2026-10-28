#pragma once

// Copy this file as wifi_config.h in the same folder, then replace the values.
// wifi_config.h is ignored by Git so these secrets are not pushed to GitHub.

#define AGRINOX_WIFI_SSID "YOUR_WIFI_NAME"
#define AGRINOX_WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

// Use the LAN address of the computer running the Agrinox backend.
// Do not use 127.0.0.1: that would point back to the ESP32 itself.
#define AGRINOX_SERVER_URL "http://192.168.0.149:8000/api/v1"

// For the currently registered ESP32, leave this empty to retain the device
// key already stored in NVS. After erasing the ESP32, generate a new key from
// POST /api/v1/iot/devices/{device_id}/credentials and paste it here.
#define AGRINOX_DEVICE_KEY ""
