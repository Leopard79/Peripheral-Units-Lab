import time
import threading
import numpy as np
import cv2
import web_app

def create_mock_frame(detected, direction, angle):
    """توليد صورة وهمية للعرض"""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    if detected:
        frame[:] = (0, 0, 150)  # خلفية حمراء
        cv2.putText(frame, f"THREAT DETECTED!", (120, 200), cv2.FONT_HERSHEY_DUPLEX, 1.2, (255, 255, 255), 2)
        cv2.putText(frame, f"Dir: {direction} | Angle: {angle} deg", (120, 260), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    else:
        frame[:] = (0, 100, 0)  # خلفية خضراء
        cv2.putText(frame, "AREA CLEAR - SCANNING", (100, 240), cv2.FONT_HERSHEY_DUPLEX, 1, (255, 255, 255), 2)
    return frame

def main():
    print("Starting Web Server Thread...")
    server_thread = threading.Thread(target=web_app.start_web_server, args=("0.0.0.0", 5000), daemon=True)
    server_thread.start()

    # سيناريوهات الاختبار: (الاكتشاف, الاتجاه, الزاوية)
    scenarios = [
        (False, "None", 0),
        (True, "Left", 315),
        (True, "Front", 0),
        (True, "Right", 45)
    ]
    
    scenario_idx = 0
    last_switch_time = time.time()
    
    print("\nStarting Main Control Loop (simulating 30 FPS)...")
    try:
        while True:
            current_time = time.time()
            
            # تغيير الحالة كل ثانيتين
            if current_time - last_switch_time > 2.0:
                scenario_idx = (scenario_idx + 1) % len(scenarios)
                last_switch_time = current_time
                
            detected, direction, angle = scenarios[scenario_idx]
            frame = create_mock_frame(detected, direction, angle)
            
            # محاكاة إرسال التحديث المستمر
            web_app.update_alert(detected, direction, angle, "MODE_A", frame)
            
            # التقاط ضغطات الأزرار من واجهة الويب
            cmd = web_app.pop_last_command()
            if cmd:
                print(f">>> [MAIN TEST SCRIPT] Extracted command from queue: {cmd}")
                
            # محاكاة زمن دورة المعالجة (حوالي 30-33 لفة بالثانية)
            time.sleep(0.03)
            
    except KeyboardInterrupt:
        print("\nTest terminated.")

if __name__ == "__main__":
    main()