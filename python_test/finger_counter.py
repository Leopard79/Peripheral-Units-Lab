# pip install opencv-python mediapipe==0.10.14 pyserial
import time
import cv2
import mediapipe as mp
import serial

SERIAL_PORT = "COM4"      # غيّره لمنفذ ESP32 المرسل
BAUD = 115200
CAMERA_INDEX = 0
SEND_INTERVAL = 0.05      # 20Hz

# ===== إعدادات التتبع =====
FINGER_MODE = "any"       # "index" = السبابة فقط ، "any" = أعلى إصبع في الصورة
PAN_MIN, PAN_MAX = 0, 180
TILT_MIN, TILT_MAX = 30, 150   # حدود آمنة لمنصتك
INVERT_PAN = False        # اعكسها إذا كان السيرفو يتحرك بعكس الإصبع
INVERT_TILT = False
MARGIN = 0.10             # هامش من أطراف الصورة ليصل السيرفو للحدود
SMOOTH = 0.35             # 0..1 (أقل = أنعم وأبطأ)

TIP_IDS = [4, 8, 12, 16, 20]

esp_serial = None
try:
    esp_serial = serial.Serial()
    esp_serial.port = SERIAL_PORT
    esp_serial.baudrate = BAUD
    esp_serial.timeout = 0.05
    esp_serial.dtr = False
    esp_serial.rts = False
    esp_serial.open()
    time.sleep(2)
    print(f"[Serial] Connected on {SERIAL_PORT}")
except Exception as e:
    print(f"[Serial Warning] {e}. Running without ESP32.")


def send_to_esp32(message):
    if esp_serial and esp_serial.is_open:
        try:
            esp_serial.write(message.encode("utf-8"))
        except Exception as e:
            print(f"[Serial Error]: {e}")


def pick_tip(hl):
    """يرجع (x, y) طرف الإصبع المتتبَّع بإحداثيات 0..1"""
    if FINGER_MODE == "index":
        p = hl.landmark[8]
    else:
        p = min((hl.landmark[i] for i in TIP_IDS), key=lambda q: q.y)
    return p.x, p.y


def to_angle(v, lo, hi, invert):
    v = (v - MARGIN) / (1 - 2 * MARGIN)
    v = max(0.0, min(1.0, v))
    if invert:
        v = 1 - v
    return lo + v * (hi - lo)


mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(max_num_hands=1,
                       min_detection_confidence=0.7,
                       min_tracking_confidence=0.6)

cap = cv2.VideoCapture(CAMERA_INDEX)
last_serial_time = 0
was_visible = False
pan_s, tilt_s = 90.0, 90.0

print("Press 'q' to quit.")

while cap.isOpened():
    ok, frame = cap.read()
    if not ok:
        break

    frame = cv2.flip(frame, 1)          # مرآة ليكون الاتجاه طبيعياً
    h, w = frame.shape[:2]
    result = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    visible = False
    if result.multi_hand_landmarks:
        visible = True
        hl = result.multi_hand_landmarks[0]
        mp_draw.draw_landmarks(frame, hl, mp_hands.HAND_CONNECTIONS)

        tx, ty = pick_tip(hl)
        pan_t = to_angle(tx, PAN_MIN, PAN_MAX, INVERT_PAN)
        tilt_t = to_angle(ty, TILT_MIN, TILT_MAX, INVERT_TILT)

        # تنعيم
        pan_s += (pan_t - pan_s) * SMOOTH
        tilt_s += (tilt_t - tilt_s) * SMOOTH
        pan, tilt = int(round(pan_s)), int(round(tilt_s))

        # زاوية التهديد: 0 = أمام ، سالب = يسار ، موجب = يمين (0..359)
        threat = (pan - 90) % 360

        px, py = int(tx * w), int(ty * h)
        cv2.circle(frame, (px, py), 12, (0, 0, 255), -1)

        now = time.time()
        if now - last_serial_time >= SEND_INTERVAL:
            last_serial_time = now
            send_to_esp32(f"D,{pan},{tilt},{threat}\n")

        cv2.putText(frame, f"PAN {pan}  TILT {tilt}  THREAT {threat}",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    if visible != was_visible:
        print("[Target] ON" if visible else "[Target] OFF")
        was_visible = visible

    cv2.imshow("Finger Tracking (MediaPipe)", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

send_to_esp32("S\n")
if esp_serial and esp_serial.is_open:
    esp_serial.close()
cap.release()
cv2.destroyAllWindows()