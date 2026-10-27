# Agrinox irrigation controller

This reference sketch connects an ESP32 field device to the Agrinox FastAPI backend. It reads soil moisture, DHT22 temperature/humidity, an ultrasonic tank sensor, an optional flow sensor, and an optional Modbus RS485 NPK probe.

## Before flashing

1. Register the device and its sensors in Device Management.
2. Assign the device to a field, create its one-time key in Smart Irrigation, and copy the device ID and key into the sketch.
3. Update Wi-Fi, server address, pins, tank height, soil calibration values, flow calibration, and the NPK register map.
4. Install ArduinoJson, the DHT sensor library, and ModbusMaster.
5. Confirm whether the relay is active HIGH or active LOW. The supplied sketch assumes active HIGH.
6. Test the emergency-stop input, empty-tank cutoff, maximum runtime, and relay behavior with the pump electrically disconnected.

The development URL may use plain HTTP on a trusted local network. A deployed system should use HTTPS with certificate validation and should store Wi-Fi and device credentials in protected ESP32 storage instead of source code.

Automatic mode must remain disabled until wiring, relay isolation, pump capacity, tank sensing, flow behavior, and physical emergency stop have been checked in the field. The firmware defaults the pump OFF whenever safety evidence is missing or unsafe.
