"""DETAS AMG8833 termal sensor servisi."""

import threading
import time

from config import (
    AMG8833_ADDRESSES,
    AMG8833_HOTSPOT_THRESHOLD,
    AMG8833_I2C_BUS,
    AMG8833_MATRIX_SIZE,
    AMG8833_PIXEL_BASE,
    AMG8833_PIXEL_COUNT,
    AMG8833_READ_INTERVAL,
    AMG8833_RECONNECT_DELAY,
    AMG8833_THERMISTOR_H,
    AMG8833_THERMISTOR_L,
)
from services.logger_service import add_log
from services.state import state

try:
    from smbus2 import SMBus

    SMBUS_AVAILABLE = True
except Exception as exc:
    SMBus = None
    SMBUS_AVAILABLE = False
    _SMBUS_IMPORT_ERROR = exc


_thread_lock = threading.Lock()
_thermal_thread = None


def read_signed_12bit(raw):
    """AMG8833 signed 12-bit degerini Python integer'a cevirir."""
    value = raw & 0x0FFF

    if value & 0x800:
        value -= 4096

    return value


def find_amg8833(bus):
    """Config'teki adreslerden erisilebilir ilk AMG8833 adresini bulur."""
    for address in AMG8833_ADDRESSES:
        try:
            bus.read_byte(address)
            return address
        except Exception:
            pass

    return None


def read_thermistor(bus, address):
    """Sensor govde sicakligini okur."""
    low = bus.read_byte_data(address, AMG8833_THERMISTOR_L)
    high = bus.read_byte_data(address, AMG8833_THERMISTOR_H)

    raw = (high << 8) | low
    return read_signed_12bit(raw) * 0.0625


def read_amg_pixels(bus, address):
    """AMG8833 piksel sicakliklarini JSON uyumlu 8x8 liste olarak okur."""
    pixels = []

    for index in range(AMG8833_PIXEL_COUNT):
        register = AMG8833_PIXEL_BASE + index * 2
        low = bus.read_byte_data(address, register)
        high = bus.read_byte_data(address, register + 1)

        raw = (high << 8) | low
        temperature = read_signed_12bit(raw) * 0.25
        pixels.append(round(temperature, 2))

    return [
        pixels[row * AMG8833_MATRIX_SIZE:(row + 1) * AMG8833_MATRIX_SIZE]
        for row in range(AMG8833_MATRIX_SIZE)
    ]


def update_thermal_state(matrix, sensor_temp, address=None):
    """Okunan termal degerleri merkezi state'e yazar."""
    flat = [value for row in matrix for value in row]

    if not flat:
        raise ValueError("Termal matris bos olamaz")

    thermal_min = round(min(flat), 2)
    thermal_max = round(max(flat), 2)

    state.update(
        thermal_connected=True,
        thermal_address=address,
        thermal=matrix,
        thermal_min=thermal_min,
        thermal_max=thermal_max,
        thermal_sensor_temp=round(sensor_temp, 2),
        hotspot=1 if thermal_max >= AMG8833_HOTSPOT_THRESHOLD else 0,
    )

    return state.snapshot()


def read_thermal_once(bus, address):
    """Acik I2C bus uzerinden tek bir termal olcum yapar."""
    sensor_temp = read_thermistor(bus, address)
    matrix = read_amg_pixels(bus, address)
    return update_thermal_state(matrix, sensor_temp, address)


def thermal_worker():
    """AMG8833 sensorunu surekli okuyup hata durumunda yeniden baglanir."""
    if not SMBUS_AVAILABLE:
        add_log(f"AMG8833 icin smbus2 yok: {_SMBUS_IMPORT_ERROR}")
        state.update(thermal_connected=False)
        return

    while True:
        try:
            with SMBus(AMG8833_I2C_BUS) as bus:
                address = find_amg8833(bus)

                if address is None:
                    state.update(thermal_connected=False, thermal_address=None)
                    add_log("AMG8833 bulunamadi")
                    time.sleep(AMG8833_RECONNECT_DELAY)
                    continue

                state.update(thermal_connected=True, thermal_address=address)
                add_log(f"AMG8833 bulundu: 0x{address:02X}")

                while True:
                    try:
                        read_thermal_once(bus, address)
                        time.sleep(AMG8833_READ_INTERVAL)
                    except Exception as exc:
                        state.update(thermal_connected=False)
                        add_log(f"AMG8833 okuma hatasi: {exc}")
                        time.sleep(AMG8833_RECONNECT_DELAY)
                        break

        except Exception as exc:
            state.update(thermal_connected=False)
            add_log(f"AMG8833 bus hatasi: {exc}")
            time.sleep(AMG8833_RECONNECT_DELAY)


def start_thermal_thread():
    """Termal sensor worker'ini daemon thread olarak bir kez baslatir."""
    global _thermal_thread

    with _thread_lock:
        if _thermal_thread is not None and _thermal_thread.is_alive():
            return _thermal_thread

        _thermal_thread = threading.Thread(
            target=thermal_worker,
            name="detas-thermal",
            daemon=True,
        )
        _thermal_thread.start()
        return _thermal_thread


# Eski app.py isimlendirmesiyle uyumluluk.
amg8833_thread = thermal_worker
