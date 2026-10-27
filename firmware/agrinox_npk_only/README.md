# Agrinox NPK-only ESP32 firmware

This sketch reads only soil nitrogen, phosphorus and potassium from a Modbus
RS485 probe. It supports both Agrinox USB discovery and authenticated Wi-Fi
upload to `POST /api/v1/iot/readings`.

## Wiring

| RS485 board | ESP32 |
| --- | --- |
| RO | RX2 / GPIO16 |
| DI | TX2 / GPIO17 |
| RE | GPIO4 |
| DE | GPIO5 |
| GND | GND |

Power the probe and RS485 converter at the voltage specified by their manuals.
All grounds must be common. Do not connect a 5 V logic output directly to an
ESP32 3.3 V input unless the converter guarantees 3.3 V-safe logic.

## Install from Agrinox

1. Connect the ESP32 to the computer with a data-capable USB cable and close
   Arduino Serial Monitor or any other program using its COM port.
2. Open **Device Management** and select **Register a device**.
3. On the detected ESP32, select **Install firmware**.
4. Enter only the Wi-Fi name and password, then keep the cable connected while
   Agrinox flashes and verifies the bundled firmware.
5. Agrinox automatically creates the device identity, API key and a name such
   as `NPK Monitor 112233`. Assign it to a field when ready.
6. Readings are sent every 60 seconds. View them in **Device Management → View
   sensors** and **Soil Quality & Advisory**.

The dashboard uses the bundled merged firmware image and Python `esptool`.
Farmers do not need Arduino IDE. Developers need the ESP32 core,
**ModbusMaster**, and **ArduinoJson 7** only when rebuilding the bundled image.

## Sensor protocol

The sketch uses Modbus slave address `1`, `9600 8N1`, and holding registers
`0x001E`, `0x001F`, and `0x0020`. These are common, but not universal. If the
probe manual gives different values, change `NPK_SLAVE_ID`, `NPK_BAUD_RATE`, or
`NPK_FIRST_REGISTER` before testing.

Low-cost NPK probes require local calibration and laboratory comparison.
Agrinox stores these readings as `needs_review`; it does not turn them into a
precise fertilizer prescription.

