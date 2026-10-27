import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import serial
from serial.tools import list_ports


ESP32_VIDS = {0x303A, 0x10C4, 0x1A86, 0x0403}
OPEN_ATTEMPTS = 3
OPEN_RETRY_SECONDS = 0.6
DEVICE_BOOT_SECONDS = 2.0
RESPONSE_SECONDS = 4.0
PROJECT_ROOT = Path(__file__).resolve().parents[3]
FIRMWARE_SKETCH = PROJECT_ROOT / "firmware" / "agrinox_npk_only"
FIRMWARE_BUILD = PROJECT_ROOT / "firmware" / "build" / "agrinox_npk_only"
FIRMWARE_BINARY = FIRMWARE_BUILD / "agrinox_npk_only.ino.bin"
FIRMWARE_MERGED_BINARY = FIRMWARE_BUILD / "agrinox_npk_only.ino.merged.bin"
ESP32_FQBN = "esp32:esp32:esp32"
_firmware_lock = threading.Lock()


def _arduino_cli() -> Path:
    candidates = [
        os.getenv("ARDUINO_CLI_PATH"),
        r"C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe",
        r"C:\Program Files (x86)\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe",
    ]
    for value in candidates:
        if value and Path(value).is_file():
            return Path(value)
    raise RuntimeError("The Agrinox firmware tool is not installed on this computer")


def _run_firmware_command(arguments: list[str], timeout: int) -> None:
    try:
        completed = subprocess.run(
            [str(_arduino_cli()), *arguments],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Firmware installation timed out. Reconnect the ESP32 and try again.") from exc
    if completed.returncode != 0:
        output = (completed.stderr or completed.stdout or "Firmware operation failed").strip()
        raise RuntimeError(output[-1200:])


def _ensure_firmware_binary() -> None:
    source = FIRMWARE_SKETCH / "agrinox_npk_only.ino"
    if FIRMWARE_MERGED_BINARY.is_file() and FIRMWARE_MERGED_BINARY.stat().st_mtime >= source.stat().st_mtime:
        return
    FIRMWARE_BUILD.mkdir(parents=True, exist_ok=True)
    _run_firmware_command(
        ["compile", "--fqbn", ESP32_FQBN, "--output-dir", str(FIRMWARE_BUILD), str(FIRMWARE_SKETCH)],
        timeout=300,
    )


def _upload_merged_firmware(port: str) -> None:
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "esptool",
                "--chip",
                "esp32",
                "--port",
                port,
                "--baud",
                "460800",
                "--before",
                "default-reset",
                "--after",
                "hard-reset",
                "write-flash",
                "0x0",
                str(FIRMWARE_MERGED_BINARY),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Firmware upload timed out. Reconnect the ESP32 and try again.") from exc
    if completed.returncode != 0:
        output = (completed.stderr or completed.stdout or "Firmware upload failed").strip()
        raise RuntimeError(output[-1200:])


def _validate_esp32_port(port: str) -> None:
    match = next((item for item in list_ports.comports() if item.device.casefold() == port.casefold()), None)
    if not match:
        raise ValueError(f"{port} is not connected")
    text = " ".join(filter(None, [match.description, match.manufacturer, match.product])).casefold()
    if match.vid not in ESP32_VIDS and not any(term in text for term in ("esp32", "espressif", "cp210", "ch340", "usb serial")):
        raise ValueError(f"{port} is not recognized as an ESP32 USB connection")


def flash_firmware(port: str) -> dict:
    if not _firmware_lock.acquire(blocking=False):
        raise RuntimeError("Another firmware installation is already running")
    try:
        _validate_esp32_port(port)
        _ensure_firmware_binary()
        _upload_merged_firmware(port)
        time.sleep(2.5)
        return exchange(port, "AGRINOX_DISCOVER")
    finally:
        _firmware_lock.release()


def configure_firmware(port: str, wifi_ssid: str, wifi_password: str, server_url: str, device_key: str) -> dict:
    command = "AGRINOX_CONFIG " + json.dumps(
        {
            "wifi_ssid": wifi_ssid,
            "wifi_password": wifi_password,
            "server_url": server_url.rstrip("/"),
            "device_key": device_key,
        },
        separators=(",", ":"),
    )
    result = exchange(port, command)
    if result.get("configured") is not True:
        raise RuntimeError(result.get("message") or "The ESP32 did not save its configuration")
    return result


def local_device_api_url(configured_url: str | None = None) -> str:
    if configured_url:
        return configured_url.rstrip("/")
    connection = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        connection.connect(("8.8.8.8", 80))
        address = connection.getsockname()[0]
    except OSError:
        address = "127.0.0.1"
    finally:
        connection.close()
    return f"http://{address}:8000/api/v1"


def _open_serial(port: str, baud_rate: int) -> serial.Serial:
    last_error: Exception | None = None
    for attempt in range(OPEN_ATTEMPTS):
        try:
            return serial.Serial(
                port=port,
                baudrate=baud_rate,
                timeout=0.35,
                write_timeout=2,
                rtscts=False,
                dsrdtr=False,
            )
        except (serial.SerialException, OSError) as exc:
            last_error = exc
            if attempt + 1 < OPEN_ATTEMPTS:
                time.sleep(OPEN_RETRY_SECONDS)
    assert last_error is not None
    raise last_error


def _friendly_port_error(port: str, error: Exception) -> tuple[str, str, str]:
    detail = str(error)
    lowered = detail.casefold()
    if "device attached to the system is not functioning" in lowered or "winerror 31" in lowered:
        return (
            "port_unavailable",
            f"Windows detected {port}, but the USB connection is not responding.",
            "Unplug the device, reconnect it with a data-capable USB cable, wait a few seconds, then scan again.",
        )
    if isinstance(error, (serial.SerialException, PermissionError, OSError)) and any(
        term in lowered for term in ("access is denied", "permissionerror", "permission denied", "resource busy")
    ):
        return (
            "port_busy",
            f"{port} is being used by another program.",
            "Close Arduino Serial Monitor, Serial Plotter, PlatformIO, PuTTY, or any other serial app, then scan again.",
        )
    if "did not answer" in lowered:
        return (
            "no_response",
            f"{port} opened, but the device did not answer Agrinox.",
            "Upload the Agrinox firmware at 115200 baud, close Serial Monitor, press the ESP32 reset button, then scan again.",
        )
    if "not compatible" in lowered:
        return (
            "incompatible",
            f"A device answered on {port}, but it is not running the Agrinox protocol.",
            "Upload the Agrinox firmware and scan again.",
        )
    return ("probe_failed", f"Could not communicate with the device on {port}.", detail)


def exchange(port: str, command: str, baud_rate: int = 115200) -> dict:
    with _open_serial(port, baud_rate) as connection:
        # Opening a USB serial connection can reset an ESP32. Give the board
        # enough time to boot, then ignore boot messages until valid JSON arrives.
        time.sleep(DEVICE_BOOT_SECONDS)
        connection.reset_input_buffer()
        connection.write(f"{command}\n".encode("utf-8"))
        connection.flush()
        deadline = time.monotonic() + RESPONSE_SECONDS
        incompatible_payload = False
        while time.monotonic() < deadline:
            raw = connection.readline().decode("utf-8", errors="replace").strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if payload.get("protocol") == "agrinox-1":
                return payload
            incompatible_payload = True
    if incompatible_payload:
        raise ValueError("Device is not compatible with Agrinox")
    raise ValueError("Device did not answer the Agrinox serial command")


def scan_usb_ports(probe: bool = True) -> list[dict]:
    results = []
    for info in list_ports.comports():
        text = " ".join(filter(None, [info.description, info.manufacturer, info.product])).casefold()
        likely_esp32 = info.vid in ESP32_VIDS or any(term in text for term in ("esp32", "espressif", "cp210", "ch340", "usb serial"))
        item = {
            "port": info.device,
            "description": info.description,
            "manufacturer": info.manufacturer,
            "vid": f"{info.vid:04X}" if info.vid is not None else None,
            "pid": f"{info.pid:04X}" if info.pid is not None else None,
            "serial_number": info.serial_number,
            "likely_esp32": likely_esp32,
            "identified": False,
            "device": None,
            "error": None,
            "error_code": None,
            "action": None,
        }
        if probe and likely_esp32:
            try:
                item["device"] = exchange(info.device, "AGRINOX_DISCOVER")
                item["identified"] = True
            except (serial.SerialException, OSError, json.JSONDecodeError, ValueError) as exc:
                error_code, message, action = _friendly_port_error(info.device, exc)
                item["error_code"] = error_code
                item["error"] = message
                item["action"] = action
        results.append(item)
    return results
