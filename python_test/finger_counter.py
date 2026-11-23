# pip install opencv-python mediapipe==0.10.14 pyserial
import time
import cv2
import mediapipe as mp
import serial

SERIAL_PORT = "COM10"      # غيّره لمنفذ ESP32 المرسل
BAUD = 115200
CAMERA_INDEX = 0          # كاميرا اللابتوب
SEND_INTERVAL = 0.05      # 20Hz كما في main

esp_serial = None
try:
    esp_serial = serial.Serial()
    esp_serial.port = SERIAL_PORT
    esp_serial.baudrate = BAUD
    esp_serial.timeout = 0.05
    esp_serial.dtr = False   # نفس إعدادات main
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


mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(max_num_hands=1,
                       min_detection_confidence=0.7,
                       min_tracking_confidence=0.6)

cap = cv2.VideoCapture(CAMERA_INDEX)
last_serial_time = 0
was_visible = False

print("Press 'q' to quit.")

while cap.isOpened():
    ok, frame = cap.read()
    if not ok:
        break

    h, w = frame.shape[:2]
    result = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    visible = False
    if result.multi_hand_landmarks:
        visible = True
        hl = result.multi_hand_landmarks[0]
        mp_draw.draw_landmarks(frame, hl, mp_hands.HAND_CONNECTIONS)

        center_x = int(sum(p.x for p in hl.landmark) / len(hl.landmark) * w)
        center_y = int(sum(p.y for p in hl.landmark) / len(hl.landmark) * h)

        if center_x < w * 0.33:
            direction, angle = "Left", 315
        elif center_x > w * 0.67:
            direction, angle = "Right", 45
        else:
            direction, angle = "Front", 0

        now = time.time()
        if now - last_serial_time >= SEND_INTERVAL:
            last_serial_time = now
            send_to_esp32(f"D,{center_x},{center_y},{angle}\n")

        cv2.putText(frame, f"TARGET {direction} ({center_x},{center_y})",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    if visible != was_visible:
        print("[Target] ON" if visible else "[Target] OFF")
        was_visible = visible

    cv2.imshow("Link Test (MediaPipe)", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

send_to_esp32("S\n")
if esp_serial and esp_serial.is_open:
    esp_serial.close()
cap.release()
cv2.destroyAllWindows()