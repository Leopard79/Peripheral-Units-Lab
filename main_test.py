import cv2
import time
import threading
from ultralytics import YOLO

# استدعاء دوال الصوت من ملف زميلك (تأكد أن اسمه voice_system.py)
import voice_system as vs

# متغير لتحديد حالة النظام (نبدأ بالوضع A افتراضياً للتجربة، أو يمكنك جعله "STANDBY")
current_mode = "MODE_A"

# 1. دالة تستقبل الأوامر الصوتية التي ينطقها الجندي في الميكروفون
def handle_voice_commands(event):
    global current_mode
    # أولاً: دع كود زميلك ينفذ الرد الصوتي الطبيعي (مثل نطق الساعة أو تأكيد الأمر)
    vs.on_voice_message_received(event)
    
    # ثانياً: تغيير حالة الكاميرا بناءً على الأمر الصوتي
    cmd = event["cmd_id"]
    if cmd == vs.CommandID.SET_MODE_A:
        current_mode = "MODE_A"
    elif cmd == vs.CommandID.SET_MODE_D:
        current_mode = "STANDBY"

# 2. تشغيل نظام الاستماع الصوتي (Vosk) في الخلفية لكي لا يوقف الكاميرا
voice_thread = threading.Thread(
    target=vs.start_voice_module, 
    args=(handle_voice_commands,), 
    daemon=True
)
voice_thread.start()

# =====================================================================
# قسم الرؤية الحاسوبية (كودك مع إضافة إرسال التحذير)
# =====================================================================

# استدعاء ملف الأوزان الخاص بالحافظة
model = YOLO("C:\\Users\\Rami\\Desktop\\Githup\\Peripheral-Units-Lab\\main\\best.pt")

cap = cv2.VideoCapture(1)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

# إعدادات مؤقت التهدئة (لمنع تداخل الأصوات)
last_alert_time = 0
ALERT_COOLDOWN = 6.0  # 6 ثوانٍ بين كل تحذير وآخر

print("جاري تشغيل الكاميرا... اضغط 'q' للإغلاق.")

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        print("لم يتم العثور على الكاميرا.")
        break

    # إذا قال الجندي "وضع السكون"، نعرض الكاميرا فقط بدون تشغيل YOLO
    if current_mode == "STANDBY":
        cv2.putText(frame, "STANDBY MODE", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.imshow("Custom Tumbler Detection", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
        continue

    # إرسال الإطار إلى نموذج YOLO
    results = model.predict(source=frame, conf=0.7, show=False, verbose=False)
    
    # فحص هل تم اكتشاف الحافظة في الإطار الحالي؟
    boxes = results[0].boxes
    if len(boxes) > 0:
        current_time = time.time()
        
        # إذا مرت 6 ثوانٍ على آخر تنبيه، نرسل تنبيهاً جديداً
        if current_time - last_alert_time > ALERT_COOLDOWN:
            last_alert_time = current_time
            
            # حساب موقع الحافظة في الشاشة (يسار، منتصف، يمين) لتجربة تغيير الكلام
            x1, y1, x2, y2 = boxes[0].xyxy[0]
            center_x = int((x1 + x2) / 2)
            
            if center_x < 420:
                direction, angle = "اليسار", 315
            elif center_x > 860:
                direction, angle = "اليمين", 45
            else:
                direction, angle = "الأمام", 0

            # إرسال التحذير للسماعة في خيط مستقل حتى لا تتجمد صورة الفيديو
            threading.Thread(
                target=vs.send_audio_warning,
                args=("MODE_A_DRONE", direction, angle),
                daemon=True
            ).start()

    # رسم المربعات وعرض الصورة
    annotated_frame = results[0].plot()
    cv2.imshow("Custom Tumbler Detection", annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()