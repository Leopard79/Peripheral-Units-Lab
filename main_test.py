import threading
import time
import cv2
import web_app


def main():
    web_thread = threading.Thread(
        target=web_app.start_web_server,
        kwargs={"host": "0.0.0.0", "port": 5000},
        daemon=True,
    )
    web_thread.start()

    cap = cv2.VideoCapture(0)
    while True:
        ret, frame = cap.read()
        if ret:
            # يرسل الصورة تلقائياً بحد أقصى مرة واحدة كل 1 ثانية
            web_app.update_frame(frame)

            # مثال تحديث حالة التنبيه مع الإطار:
            # web_app.update_alert(detected=True, direction="Right", angle=45, mode="MODE_A", frame=frame)
        time.sleep(0.03)


if __name__ == "__main__":
    main()