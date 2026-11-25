import base64
import logging
import socket
import threading
import time
import cv2
from flask import Flask, jsonify, render_template, request

logging.getLogger("werkzeug").setLevel(logging.ERROR)

app = Flask(__name__, template_folder="templates")

# متغير عام لحفظ الحالة الحالية + آخر صورة + آخر حرف مرسل من الهاتف
system_state = {
    "detected": False,
    "direction": "None",
    "angle": 0,
    "mode": "MODE_A",
    "last_update": time.strftime("%H:%M:%S"),
    "timestamp": time.time(),
    "image": None,          # Base64 JPEG
    "image_time": None,
    "last_command": None,
    "image_seq": 0          # عداد لتعقب الصور الجديدة
}

_state_lock = threading.Lock()
_last_frame_sent_time = 0.0
# تم التعديل إلى 0.25 ثانية لتقليل عبء التشفير على الخيط الرئيسي (4 إطارات بالثانية)
FRAME_INTERVAL_SECONDS = 0.25  

def _encode_frame_base64(frame) -> str | None:
    if frame is None:
        return None
    try:
        # تصغير الصورة لعرض 480 بكسل لتسريع عملية التشفير وتقليل حجم نقل البيانات
        h, w = frame.shape[:2]
        if w > 480:
            new_h = int(h * (480 / w))
            frame = cv2.resize(frame, (480, new_h))
            
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 70]
        success, buffer = cv2.imencode(".jpg", frame, encode_params)
        if not success:
            return None
        return base64.b64encode(buffer).decode("utf-8")
    except Exception:
        return None

def update_frame(frame) -> None:
    global _last_frame_sent_time
    now = time.time()
    if now - _last_frame_sent_time < FRAME_INTERVAL_SECONDS:
        return

    encoded = _encode_frame_base64(frame)
    if encoded is None:
        return

    with _state_lock:
        system_state["image"] = encoded
        system_state["image_time"] = time.strftime("%H:%M:%S")
        system_state["image_seq"] += 1
        _last_frame_sent_time = now

def update_alert(
    detected: bool,
    direction: str = "None",
    angle: int = 0,
    mode: str = "MODE_A",
    frame=None,
) -> None:
    """تُستدعى من main_test.py لتحديث حالة التنبيه والاتجاه والزاوية ووضع النظام (والصورة اختيارياً)."""
    with _state_lock:
        system_state["detected"] = bool(detected)
        system_state["direction"] = direction if detected else "None"
        system_state["angle"] = int(angle) if detected else 0
        system_state["mode"] = str(mode)
        system_state["last_update"] = time.strftime("%H:%M:%S")
        system_state["timestamp"] = time.time()

    if frame is not None:
        update_frame(frame)

def get_last_command() -> str | None:
    """للتوافق القديم"""
    with _state_lock:
        return system_state["last_command"]

def pop_last_command() -> str | None:
    """ترجع آخر حرف أرسله الجوال ثم تصفره لمنع تنفيذ الأمر مرتين."""
    with _state_lock:
        cmd = system_state["last_command"]
        system_state["last_command"] = None
        return cmd

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status", methods=["GET"])
def get_status():
    with _state_lock:
        data = dict(system_state)
        # حساب عمر التحديث بالملي ثانية ليتمكن الهاتف من كشف انقطاع الاتصال
        data["age_ms"] = int((time.time() - data["timestamp"]) * 1000)
        return jsonify(data)

@app.route("/api/command", methods=["POST"])
def receive_command():
    payload = request.get_json(silent=True) or {}
    letter = str(payload.get("command", "")).strip().upper()
    if not letter:
        return jsonify({"ok": False, "error": "Empty command"}), 400

    with _state_lock:
        system_state["last_command"] = letter

    print(f"[TERMINAL] Pressed button: {letter} ({time.strftime('%H:%M:%S')})", flush=True)
    return jsonify({"ok": True, "command": letter})

def _get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def start_web_server(host: str = "0.0.0.0", port: int = 5000) -> None:
    local_ip = _get_local_ip()
    print("=" * 56, flush=True)
    print("FALCON EYE - LOCAL TACTICAL WEB GUI ONLINE", flush=True)
    print(f"Local PC    : http://127.0.0.1:{port}", flush=True)
    print(f"Mobile Wi-Fi: http://{local_ip}:{port}", flush=True)
    print("=" * 56, flush=True)
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)