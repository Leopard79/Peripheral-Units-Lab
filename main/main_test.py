import threading
import time
import cv2
import serial
from ultralytics import YOLO
import voice_system as vs
import web_app as web

# =====================================================================
# 1. الاتصال التسلسلي مع ESP32 المرسل
# =====================================================================
SERIAL_PORT = "COM10"
BAUD_RATE = 115200
esp_serial = None

try:
    esp_serial = serial.Serial()
    esp_serial.port = SERIAL_PORT
    esp_serial.baudrate = BAUD_RATE
    esp_serial.timeout = 0.05
    esp_serial.dtr = False
    esp_serial.rts = False
    esp_serial.open()
    time.sleep(2)
    print(f"[Serial] تم الاتصال بـ ESP32 بنجاح على المنفذ {SERIAL_PORT}")
except Exception as e:
    print(f"[Serial Warning] لم يتم الاتصال بـ ESP32 ({e}). سيعمل النظام بالصوت والويب فقط.")


def send_to_esp32(message):
    if esp_serial and esp_serial.is_open:
        try:
            esp_serial.write(message.encode("utf-8"))
        except Exception as e:
            print(f"[Serial Error]: {e}")


# =====================================================================
# 2. آلة الحالة (صوت + جوال)
# =====================================================================
current_mode = "MODE_A"
ACTIVE_MODES = {"MODE_A", "STANDBY"}

PHONE_KEY_TO_MODE = {"A": "MODE_A", "B": "MODE_B", "C": "MODE_C", "D": "STANDBY"}
VOICE_CMD_TO_MODE = {
    vs.CommandID.SET_MODE_A: "MODE_A",
    vs.CommandID.SET_MODE_B: "MODE_B",
    vs.CommandID.SET_MODE_C: "MODE_C",
    vs.CommandID.SET_MODE_D: "STANDBY",
}


def apply_mode(new_mode, source):
    global current_mode
    if new_mode not in ACTIVE_MODES:
        print(f"[Mode] {new_mode} غير مفعّل حالياً (المصدر: {source})")
        return
    if new_mode == current_mode:
        return
    current_mode = new_mode
    print(f"[Mode] -> {new_mode} (المصدر: {source})")
    if new_mode == "STANDBY":
        send_to_esp32("S\n")


def handle_voice_commands(event):
    vs.on_voice_message_received(event)
    new_mode = VOICE_CMD_TO_MODE.get(event["cmd_id"])
    if new_mode:
        apply_mode(new_mode, "VOICE")


def poll_phone_command():
    pop = getattr(web, "pop_last_command", None)
    if pop is None:
        return
    letter = pop()
    if letter:
        new_mode = PHONE_KEY_TO_MODE.get(letter.upper())
        if new_mode:
            apply_mode(new_mode, "PHONE")


threading.Thread(target=vs.start_voice_module, args=(handle_voice_commands,), daemon=True).start()
threading.Thread(target=web.start_web_server, daemon=True).start()

# =====================================================================
# 3. الرؤية الحاسوبية + منطق الإنذار الذكي واللقطة الواحدة
# =====================================================================
model = YOLO("C:\\Users\\Rami\\Desktop\\Githup\\Peripheral-Units-Lab\\main\\best.pt")

cap = cv2.VideoCapture(1)  # غيّره إلى 0 إذا كنت تستخدم كاميرا اللابتوب الداخلية
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

# متغيرات الإنذار الذكي (بدون تكرار مزعج)
target_present = False
last_announced_dir = None
last_seen_time = 0.0
TARGET_LOST_RESET_SEC = 3.0  # إذا اختفى الهدف 3 ثوانٍ نعتبره هدفاً جديداً عند عودته

last_serial_time = 0.0
SERIAL_INTERVAL = 0.05  # 20Hz

print("جاري تشغيل الكاميرا... اضغط 'q' للإغلاق.")

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        print("لم يتم العثور على الكاميرا.")
        break

    poll_phone_command()
    now = time.time()

    # ---------------- STANDBY ----------------
    if current_mode == "STANDBY":
        target_present = False
        last_announced_dir = None
        cv2.putText(frame, "STANDBY MODE", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        web.update_alert(False, mode="STANDBY")
        cv2.imshow("Falcon Eye - Mode A", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
        continue

    # ---------------- MODE_A ----------------
    results = model.predict(source=frame, conf=0.7, device=0, show=False, verbose=False, imgsz=640)
    boxes = results[0].boxes
    annotated_frame = results[0].plot()

    detected = len(boxes) > 0
    direction, angle = "None", 0
    snapshot_to_send = None

    if detected:
        last_seen_time = now
        x1, y1, x2, y2 = boxes[0].xyxy[0]
        center_x = int((x1 + x2) / 2)
        center_y = int((y1 + y2) / 2)

        if center_x < 210:
            direction, angle = "Left", 315
        elif center_x > 430:
            direction, angle = "Right", 45
        else:
            direction, angle = "Front", 0

        # 1) إرسال الإحداثيات إلى ESP32 المرسل
        if now - last_serial_time >= SERIAL_INTERVAL:
            last_serial_time = now
            send_to_esp32(f"D,{center_x},{center_y},{angle}\n")

        # 2) الإنذار الصوتي الذكي + لقطة الهاتف (فقط عند أول رصد أو عند تغيّر الاتجاه)
        is_new_target = not target_present
        dir_changed = (direction != last_announced_dir)

        if is_new_target or dir_changed:
            target_present = True
            last_announced_dir = direction
            snapshot_to_send = annotated_frame  # إرسال صورة واحدة فقط للهاتف

            threading.Thread(
                target=vs.send_audio_warning,
                args=("MODE_A_DRONE", direction, angle),
                daemon=True,
            ).start()
    else:
        # إذا اختفى الهدف لأكثر من 3 ثوانٍ نصفر الحالة لاستقباله كهدف جديد لاحقاً
        if target_present and (now - last_seen_time > TARGET_LOST_RESET_SEC):
            target_present = False
            last_announced_dir = None

    # تحديث حالة الهاتف (يرسل الصورة فقط عندما تكون snapshot_to_send غير فارغة)
    web.update_alert(detected, direction, angle, "MODE_A", snapshot=snapshot_to_send)

    cv2.imshow("Falcon Eye - Mode A", annotated_frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

if esp_serial and esp_serial.is_open:
    send_to_esp32("S\n")
    esp_serial.close()

cap.release()
cv2.destroyAllWindows()