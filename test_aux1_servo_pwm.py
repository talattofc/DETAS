from pymavlink import mavutil
import time

PORT = "/dev/ttyAMA4"
BAUD = 57600

# Orange Cube AUX OUT 1 = SERVO9
SERVO_NUMBER = 9

# Arduino testinde 700-2300 çalışmış.
# Cube testinde biraz güvenli aralıkla başlıyoruz.
MIN_PWM = 1250
MAX_PWM = 2600
CENTER_PWM = 2400

print("Orange Cube MAVLink bağlantısı açılıyor...")
master = mavutil.mavlink_connection(
    PORT,
    baud=BAUD,
    source_system=255,
    source_component=190
)

print("Heartbeat bekleniyor...")
master.wait_heartbeat(timeout=15)

print("Bağlandı.")
print("target_system:", master.target_system)
print("target_component:", master.target_component)
print("")
print("AUX OUT 1 için SERVO_NUMBER =", SERVO_NUMBER)
print("PWM aralığı:", MIN_PWM, "-", MAX_PWM)
print("")
print("Kullanım:")
print("  1500 yaz -> servo 1500 PWM konumuna gider")
print("  1000 yaz -> servo 1000 PWM konumuna gider")
print("  center yaz -> 1500 PWM")
print("  sweep yaz -> 800-2200 arası 100'er tarama yapar")
print("  q yaz -> çıkış")
print("")

def clamp_pwm(value):
    value = int(value)

    if value < MIN_PWM:
        value = MIN_PWM

    if value > MAX_PWM:
        value = MAX_PWM

    return value

def send_pwm(pwm):
    pwm = clamp_pwm(pwm)

    print(f"SERVO{SERVO_NUMBER} / AUX1 -> {pwm}")

    master.mav.command_long_send(
        master.target_system,
        1,
        mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
        0,
        SERVO_NUMBER,
        pwm,
        0,
        0,
        0,
        0,
        0
    )

    time.sleep(0.15)

def sweep():
    print("Tarama başlıyor...")

    for pwm in range(MIN_PWM, MAX_PWM + 1, 100):
        send_pwm(pwm)
        time.sleep(0.10)

    time.sleep(0.2)

    for pwm in range(MAX_PWM, MIN_PWM - 1, -100):
        send_pwm(pwm)
        time.sleep(0.10)

    print("Tarama bitti.")

send_pwm(CENTER_PWM)

while True:
    try:
        value = input("PWM gir: ").strip().lower()

        if value in ["q", "quit", "exit", "çık", "cik"]:
            print("Çıkılıyor.")
            break

        if value in ["center", "orta", "c"]:
            send_pwm(CENTER_PWM)
            continue

        if value in ["sweep", "tara", "scan"]:
            sweep()
            continue

        pwm = int(value)
        send_pwm(pwm)

    except KeyboardInterrupt:
        print("\nÇıkılıyor.")
        break

    except Exception as e:
        print("Geçersiz giriş. Örnek: 1500")
        print("Hata:", e)
