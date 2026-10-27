# Agrinox ESP32 serial protocol

Device Management scans serial ports on the computer running the FastAPI backend. Registration is enabled only when an ESP32 returns a valid Agrinox response. The default connection is **115200 baud, 8 data bits, no parity, one stop bit**.

## Discovery

The backend sends:

```text
AGRINOX_DISCOVER\n
```

The board returns one newline-terminated JSON object:

```json
{"protocol":"agrinox-1","device_uid":"esp32-aabbccddeeff","board":"ESP32","firmware":"1.0.0","sensors":[{"key":"soil_adc","name":"Soil sensor","type":"soil_moisture_raw","unit":"raw","pin":"GPIO34"}]}
```

Requirements:

- `protocol` must be `agrinox-1`.
- `device_uid` must be stable and unique. The example derives it from the ESP32 eFuse MAC.
- Every sensor needs a stable `key`. The key is used to match readings later.
- Use an honest unit. For example, report `raw` until a soil sensor has been calibrated; do not label an uncalibrated ADC value as a percentage.

## Reading sensors

The backend sends:

```text
AGRINOX_READ\n
```

The board returns numeric readings keyed by the discovery sensor keys:

```json
{"protocol":"agrinox-1","readings":{"soil_adc":2174}}
```

Only numeric readings belonging to registered sensors are stored. The API records the server timestamp for every accepted value. A timeout or malformed response marks the device offline and does not create a made-up reading.

## Firmware example

Open `iot/esp32_agrinox_example/esp32_agrinox_example.ino` in Arduino IDE. It demonstrates the protocol with a real ADC read on GPIO 34. Change the sensor metadata and read function to match the hardware connected to the board.

The browser cannot access USB directly in this implementation. The backend must run on the Windows computer where the ESP32 is plugged in, and the serial port must not already be open in Arduino Serial Monitor or another program.
