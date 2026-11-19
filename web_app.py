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
    "image": None,          # Base64 JPEG يحدّث كل ثانية كحد أقصى
    "image_time": None,
    "last_command": None,
}

_state_lock = threading.Lock()
_last_frame_sent_time = 0.0
FRAME_INTERVAL_SECONDS = 0.05


def _encode_frame_base64(frame) -> str | None:
    if frame is None:
        return None
    try:
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 70]
        success, buffer = cv2.imencode(".jpg", frame, encode_params)
        if not success:
            return None
        return base64.b64encode(buffer).decode("utf-8")
    except Exception:
        return None


def update_frame(frame) -> None:
    """تحديث الصورة الفورية بحد أقصى مرة واحدة كل 1 ثانية."""
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
    with _state_lock:
        return system_state["last_command"]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status", methods=["GET"])
def get_status():
    with _state_lock:
        return jsonify(dict(system_state))


@app.route("/api/command", methods=["POST"])
def receive_command():
    payload = request.get_json(silent=True) or {}
    letter = str(payload.get("command", "")).strip()
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
    """تشغّل سيرفر Flask بدون Reloader أو Debug لتناسب العمل داخل threading.Thread."""
    local_ip = _get_local_ip()
    print("=" * 56, flush=True)
    print("FALCON EYE - LOCAL TACTICAL WEB GUI ONLINE", flush=True)
    print(f"Local PC    : http://127.0.0.1:{port}", flush=True)
    print(f"Mobile Wi-Fi: http://{local_ip}:{port}", flush=True)
    print("=" * 56, flush=True)
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)