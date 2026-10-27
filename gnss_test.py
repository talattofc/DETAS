from pymavlink import mavutil
import time
import math
import statistics

PORT = "/dev/ttyAMA4"
BAUD = 57600
TEST_DURATION = 60

# Google Maps sabit referans noktasi
REF_LAT = 36.6756190
REF_LON = 30.5588070


def distance_m(lat1, lon1, lat2, lon2):
    R = 6371000.0

    p1 = math.radians(lat1)
    p2 = math.radians(lat2)

    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1) * math.cos(p2)
        * math.sin(dl / 2) ** 2
    )

    return 2 * R * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )


def request_message(master, message_id, frequency_hz=2):
    interval_us = int(1_000_000 / frequency_hz)

    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
        0,
        message_id,
        interval_us,
        0, 0, 0, 0, 0
    )


print("MAVLink baglantisi aciliyor...")

master = mavutil.mavlink_connection(
    PORT,
    baud=BAUD
)

master.wait_heartbeat(timeout=15)

print("Heartbeat alindi.")

# GPS_RAW_INT = 24
request_message(
    master,
    mavutil.mavlink.MAVLINK_MSG_ID_GPS_RAW_INT,
    2
)

# GLOBAL_POSITION_INT = 33
request_message(
    master,
    mavutil.mavlink.MAVLINK_MSG_ID_GLOBAL_POSITION_INT,
    2
)

print("GPS mesajlari istendi.")
print("5 saniye veri bekleniyor...")
time.sleep(5)

print("\n60 saniyelik GNSS testi basliyor...\n")

start = time.time()

total_samples = 0
valid_fixes = 0
errors = []
satellites = []

while time.time() - start < TEST_DURATION:

    msg = master.recv_match(
        type="GPS_RAW_INT",
        blocking=True,
        timeout=3
    )

    if msg is None:
        print("GPS_RAW_INT bekleniyor...")
        continue

    total_samples += 1

    fix = int(msg.fix_type)
    sats = int(msg.satellites_visible)

    satellites.append(sats)

    if fix >= 3:

        valid_fixes += 1

        lat = msg.lat / 1e7
        lon = msg.lon / 1e7

        error = distance_m(
            REF_LAT,
            REF_LON,
            lat,
            lon
        )

        errors.append(error)

        print(
            f"Fix:{fix} "
            f"Sat:{sats:2d} "
            f"Lat:{lat:.7f} "
            f"Lon:{lon:.7f} "
            f"Error:{error:.2f} m"
        )

    else:

        print(
            f"Fix:{fix} "
            f"Sat:{sats:2d} "
            f"NO VALID FIX"
        )


print("\n--- GNSS TEST RESULT ---")
print(f"Total samples : {total_samples}")
print(f"Valid fixes   : {valid_fixes}")

if total_samples:
    availability = valid_fixes / total_samples * 100
    print(f"Fix availability : {availability:.2f}%")

if errors:
    print(f"Minimum error : {min(errors):.2f} m")
    print(f"Maximum error : {max(errors):.2f} m")
    print(f"Average error : {statistics.mean(errors):.2f} m")
    print(f"Median error  : {statistics.median(errors):.2f} m")

if satellites:
    print(
        f"Average satellites : "
        f"{statistics.mean(satellites):.1f}"
    )
