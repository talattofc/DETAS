import serial
import time
import statistics

PORT = "/dev/serial0"
BAUD = 57600
SAMPLE_COUNT = 20

print(f"Port aciliyor: {PORT} @ {BAUD}")

ser = serial.Serial(
    port=PORT,
    baudrate=BAUD,
    timeout=2
)

print("Telemetri paketleri bekleniyor...\n")

intervals = []
last_time = None

try:
    while len(intervals) < SAMPLE_COUNT:
        raw = ser.readline()

        if not raw:
            continue

        now = time.perf_counter()
        text = raw.decode("utf-8", errors="replace").strip()

        if not text:
            continue

        print(f"Paket alindi: {text}")

        if last_time is not None:
            interval_ms = (now - last_time) * 1000
            intervals.append(interval_ms)

            print(
                f"Interval {len(intervals):02d}: "
                f"{interval_ms:.1f} ms"
            )

        last_time = now

finally:
    ser.close()

if intervals:
    print("\n--- TELEMETRY TEST RESULT ---")
    print(f"Samples : {len(intervals)}")
    print(f"Minimum : {min(intervals):.1f} ms")
    print(f"Maximum : {max(intervals):.1f} ms")
    print(f"Average : {statistics.mean(intervals):.1f} ms")
    print(f"Median  : {statistics.median(intervals):.1f} ms")
