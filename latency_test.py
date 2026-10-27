import serial
import time
import statistics

PORT = "/dev/serial0"
BAUD = 57600
TRIALS = 20

ser = serial.Serial(PORT, BAUD, timeout=2)
time.sleep(1)

results = []

for i in range(TRIALS):
    ser.reset_input_buffer()

    token = str(time.monotonic_ns())
    command = f"PING,{token}\n"

    start = time.perf_counter()
    ser.write(command.encode())
    ser.flush()

    expected = f"PONG,{token}"
    response = ""

    timeout_start = time.perf_counter()

    while time.perf_counter() - timeout_start < 2:
        line = ser.readline().decode(errors="ignore").strip()

        if line == expected:
            response = line
            break

    if response:
        latency_ms = (time.perf_counter() - start) * 1000
        results.append(latency_ms)
        print(f"Test {i+1:02d}: {latency_ms:.2f} ms")
    else:
        print(f"Test {i+1:02d}: CEVAP YOK")

    time.sleep(0.5)

ser.close()

if results:
    print("\n--- TELEMETRY ROUND-TRIP LATENCY ---")
    print(f"Successful trials : {len(results)}/{TRIALS}")
    print(f"Minimum           : {min(results):.2f} ms")
    print(f"Maximum           : {max(results):.2f} ms")
    print(f"Average           : {statistics.mean(results):.2f} ms")
    print(f"Median            : {statistics.median(results):.2f} ms")
