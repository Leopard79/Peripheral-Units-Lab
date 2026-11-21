import threading
import time
import cv2
import serial
from ultralytics import YOLO
#testing vs code commits
# استدعاء دوال الصوت من ملف زميلك
import voice_system as vs

# =====================================================================
# 1. إعدادات الاتصال التسلسلي مع ESP32 المرسل (مع إصلاح DTR/RTS)
# =====================================================================
SERIAL_PORT = "COM10"  # <-- تأكد من رقم المنفذ في Device Manager
BAUD_RATE = 115200
esp_serial = None

try:
    esp_serial = serial.Serial()
    esp_serial.port = SERIAL_PORT
    esp_serial.baudrate = BAUD_RATE
    esp_serial.timeout = 0.05
    esp_serial.dtr = False  # يمنع بقاء ESP32 في وضع Reset
    esp_serial.rts = False
    esp_serial.open()
    time.sleep(2)
    print(f"[Serial] تم الاتصال بـ ESP32 بنجاح على المنفذ {SERIAL_PORT}")
except Exception as e:
    print(
        f"[Serial Warning] لم يتم الاتصال بـ ESP32 ({e}). سيعمل النظام بالصوت والكاميرا فقط."
    )


def send_to_esp32(message):
    """إرسال الأوامر إلى ESP32 المرسل مع طباعة للتأكد"""
    if esp_serial and esp_serial.is_open:
        try:
            esp_serial.write(message.encode("utf-8"))
            print(f"[TX -> ESP32]: {message.strip()}")
        except Exception as e:
            print(f"[Serial Error]: {e}")


# =====================================================================
# 2. إعدادات حالة النظام والأوامر الصوتية
# =====================================================================
current_mode = "MODE_A"


def handle_voice_commands(event):
    global current_mode
    vs.on_voice_message_received(event)

    cmd = event["cmd_id"]
    if cmd == vs.CommandID.SET_MODE_A:
        current_mode = "MODE_A"
    elif cmd == vs.CommandID.SET_MODE_D:
        current_mode = "STANDBY"
        send_to_esp32("S\n")


voice_thread = threading.Thread(
    target=vs.start_voice_module, args=(handle_voice_commands,), daemon=True
)
voice_thread.start()

# =====================================================================
# 3. قسم الرؤية الحاسوبية + إرسال الإحداثيات والتنبيهات
# =====================================================================
model = YOLO(
    "C:\\Users\\Rami\\Desktop\\Githup\\Peripheral-Units-Lab\\main\\best.pt"
)

cap = cv2.VideoCapture(1)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

last_alert_time = 0
ALERT_COOLDOWN = 6.0

last_serial_time = 0
SERIAL_INTERVAL = 0.05  # 20Hz

print("جاري تشغيل الكاميرا... اضغط 'q' للإغلاق.")

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        print("لم يتم العثور على الكاميرا.")
        break

    if current_mode == "STANDBY":
        cv2.putText(
            frame,
            "STANDBY MODE",
            (30, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            2,
        )
        cv2.imshow("Custom Tumbler Detection", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
        continue

    results = model.predict(
        source=frame, conf=0.7, device=0, show=False, verbose=False,imgsz=640
    )

    boxes = results[0].boxes
    if len(boxes) > 0:
        current_time = time.time()

        x1, y1, x2, y2 = boxes[0].xyxy[0]
        center_x = int((x1 + x2) / 2)
        center_y = int((y1 + y2) / 2)

        if center_x < 210:
            direction, angle = "Left", 315
        elif center_x > 430:
            direction, angle = "Right", 45
        else:
            direction, angle = "Front", 0

        # أ) إرسال الإحداثيات إلى ESP32 المرسل
        if current_time - last_serial_time >= SERIAL_INTERVAL:
            last_serial_time = current_time
            serial_msg = f"D,{center_x},{center_y},{angle}\n"
            send_to_esp32(serial_msg)

        # ب) إرسال التحذير الصوتي للسماعة
        if current_time - last_alert_time > ALERT_COOLDOWN:
            last_alert_time = current_time
            threading.Thread(
                target=vs.send_audio_warning,
                args=("MODE_A_DRONE", direction, angle),
                daemon=True,
            ).start()

    annotated_frame = results[0].plot()
    cv2.imshow("Custom Tumbler Detection", annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

if esp_serial and esp_serial.is_open:
    send_to_esp32("S\n")
    esp_serial.close()

cap.release()
cv2.destroyAllWindows()