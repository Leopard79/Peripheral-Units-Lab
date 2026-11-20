# pip install opencv-python mediapipe==0.10.14 pyserial
import cv2
import mediapipe as mp
import serial
import time
import math

SERIAL_PORT = "COM4"      # غيّره لمنفذ ESP32 المرسل (Linux/Mac: /dev/ttyUSB0)
BAUD = 115200
STABLE_FRAMES = 8         # عدد الفريمات المتطابقة قبل الإرسال

ser = serial.Serial(SERIAL_PORT, BAUD, timeout=1)
time.sleep(2)  # انتظار إعادة تشغيل الـ ESP32

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(max_num_hands=1,
                       min_detection_confidence=0.7,
                       min_tracking_confidence=0.6)


def dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def count_fingers(lm):
    """عدّ الأصابع المرفوعة (لا يعتمد على اتجاه اليد)."""
    count = 0
    wrist = lm[0]
    # السبابة، الوسطى، البنصر، الخنصر
    for tip, pip in [(8, 6), (12, 10), (16, 14), (20, 18)]:
        if dist(lm[tip], wrist) > dist(lm[pip], wrist):
            count += 1
    # الإبهام: الطرف أبعد عن قاعدة الخنصر من المفصل
    if dist(lm[4], lm[17]) > dist(lm[3], lm[17]):
        count += 1
    return count


cap = cv2.VideoCapture(0)
history = []
last_sent = None

while True:
    ok, frame = cap.read()
    if not ok:
        break
    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)

    n = 0
    if result.multi_hand_landmarks:
        hl = result.multi_hand_landmarks[0]
        mp_draw.draw_landmarks(frame, hl, mp_hands.HAND_CONNECTIONS)
        n = count_fingers(hl.landmark)

    # إرسال الرقم فقط عندما يثبت ويتغير
    history.append(n)
    history = history[-STABLE_FRAMES:]
    if (len(history) == STABLE_FRAMES and len(set(history)) == 1
            and 1 <= n <= 5 and n != last_sent):
        ser.write(f"{n}\n".encode())
        last_sent = n
        print("Output:", n)
    if n == 0:
        last_sent = None  # عند خفض اليد يمكن إرسال نفس الرقم مجدداً

    cv2.putText(frame, str(n), (30, 100), cv2.FONT_HERSHEY_SIMPLEX,
                3, (0, 255, 0), 6)
    cv2.imshow("Finger Counter (q = exit)", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
ser.close()
