import os
import sys
import io
import time
import json
import queue
import wave
from enum import Enum
from datetime import datetime
import numpy as np
import sounddevice as sd
import pygame
import pyttsx3
from vosk import Model, KaldiRecognizer

# استدعاء مكتبة لوحة المفاتيح المدمجة في ويندوز لزر الطوارئ الفوري
if os.name == "nt":
    import msvcrt

# تهيئة مشغل الصوت بزمن تأخير منخفض جداً (< 10ms) لتشغيل تنبيهات WAV الفورية
pygame.mixer.pre_init(44100, -16, 1, 512)
pygame.mixer.init()

# تهيئة محرك النطق المحلي الأوفلاين (pyttsx3)
tts_engine = pyttsx3.init()
tts_engine.setProperty("rate", 160)
tts_engine.setProperty("volume", 1.0)

# =====================================================================
# 1. رموز الأوامر القياسية (Command Enum IDs) وقاموس الأوامر الإنجليزية
# =====================================================================
class CommandID(str, Enum):
    SET_MODE_A = "SET_MODE_A"           # Mode A: Sky Shield (Anti-Drone)
    SET_MODE_B = "SET_MODE_B"           # Mode B: Blind-Spot Guard
    SET_MODE_C = "SET_MODE_C"           # Mode C: Tactical Periscope
    SET_MODE_D = "SET_MODE_D"           # Mode D: Standby / Sleep Mode

    QUERY_TIME = "QUERY_TIME"           # Query current time
    QUERY_VITALS = "QUERY_VITALS"       # Query soldier vitals (Heart rate & Temp)

    EMERGENCY_OFF = "SET_MODE_D"        # Emergency Kill-Switch OFF
    EMERGENCY_ON = "EMERGENCY_RESUME"   # Emergency Resume ON

# قاموس المطابقة (Intent Mapper): فقط هذه العبارات هي التي ستظهر في التيرمنال وتُنطق
INTENT_MAPPER = {
    # Mode A: Anti-Drone / Sky Shield
    "mode one": CommandID.SET_MODE_A,

    # Mode B: Blind-Spot Guard
    "mode two": CommandID.SET_MODE_B,

    # Mode C: Tactical Periscope

    "mode three": CommandID.SET_MODE_C,

    # Mode D: Standby & Power Saving
  
    "standby": CommandID.SET_MODE_D,

    # Status Queries (Time & Vitals)

    "time": CommandID.QUERY_TIME,
    "health": CommandID.QUERY_VITALS,

}

ALLOWED_GRAMMAR = list(INTENT_MAPPER.keys()) + ["[unk]"]

# حالة تشغيل النظام (True = Active, False = Emergency Stopped)
system_running = True

# قراءات الجندي الصحية (يتم تحديثها من الكود الرئيسي Main)
soldier_vitals = {
    "heart_rate": 78,     # bpm
    "skin_temp": 36.8     # Celsius
}

# =====================================================================
# 2. توليد وتحميل نغمات التحذير بصيغة WAV في الذاكرة (< 10ms Latency)
# =====================================================================
SOUND_EFFECTS = {}

def _create_memory_wav(samples, fs=44100):
    """إنشاء ملف WAV قياسي في الذاكرة العشوائية مباشرة لسرعة استجابة فورية"""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(fs)
        pcm_data = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
        wav_file.writeframes(pcm_data.tobytes())
    buf.seek(0)
    return pygame.mixer.Sound(file=buf)

def init_warning_sounds():
    fs = 44100
    # 1. صافرة إنذار الدرون (Mode A)
    t1 = np.linspace(0, 0.16, int(fs * 0.16), False)
    siren = np.concatenate([0.7 * np.sin(2 * np.pi * 1300 * t1),
                            0.7 * np.sin(2 * np.pi * 900 * t1)] * 3)
    SOUND_EFFECTS["DRONE_SIREN"] = _create_memory_wav(siren, fs)

    # 2. نغمة تنبيه تكتيكية منخفضة لكشف التسلل الخلفي (Mode B)
    t2 = np.linspace(0, 0.12, int(fs * 0.12), False)
    whisper_tone = np.concatenate([0.25 * np.sin(2 * np.pi * 320 * t2),
                                   np.zeros(int(fs * 0.06)),
                                   0.25 * np.sin(2 * np.pi * 320 * t2)])
    SOUND_EFFECTS["TACTICAL_LOW"] = _create_memory_wav(whisper_tone, fs)

    # 3. تنبيه صوتي خفيف عند دخول هدف مربع الكشف (Mode C)
    t3 = np.linspace(0, 0.08, int(fs * 0.08), False)
    scope_beep = 0.35 * np.sin(2 * np.pi * 880 * t3)
    SOUND_EFFECTS["SCOPE_BEEP"] = _create_memory_wav(scope_beep, fs)

    # 4. إنذار طارئ لكسر السكون عند وصول تحذير من الفرقة (Mode D)
    t4 = np.linspace(0, 0.1, int(fs * 0.1), False)
    sos_alarm = np.concatenate([0.8 * np.sin(2 * np.pi * 1500 * t4),
                                np.zeros(int(fs * 0.05))] * 4)
    SOUND_EFFECTS["SQUAD_SOS"] = _create_memory_wav(sos_alarm, fs)

init_warning_sounds()

# =====================================================================
# 3. دوال النطق الإنجليزي المصلحة والتحذيرات القادمة من (Main -> Speaker)
# =====================================================================
audio_queue = queue.Queue()

def clear_audio_queue():
    """تفريغ طابور الميكروفون لمنع النظام من سماع صدى صوته"""
    while not audio_queue.empty():
        try:
            audio_queue.get_nowait()
        except queue.Empty:
            break

def stop_all_audio_immediately():
    """قطع كافة الأصوات والصافرات الجارية فوراً عند ضغط زر الطوارئ"""
    pygame.mixer.stop()
    clear_audio_queue()

def play_wav_alert(sound_key):
    """تشغيل ملف WAV الفوري عبر السماعة"""
    if not system_running:
        return
    if sound_key in SOUND_EFFECTS:
        channel = SOUND_EFFECTS[sound_key].play()
        while channel.get_busy():
            if not system_running:
                stop_all_audio_immediately()
                break
            pygame.time.wait(5)

def speak_tts(text, force_speak=False):
    """
    نطق الرسائل بالإنجليزية أوفلاين في كل مرة دون توقف بعد الأمر الأول
    (تتجاوز مشكلة تعليق حلقة runAndWait في ويندوز مع بقاء الميكروفون يعمل)
    """
    if not system_running and not force_speak:
        return

    print(f"   [Audio Out -> Speaker]: {text}")

    try:
        # الطريقة المباشرة المتزامنة على ويندوز (تضمن النطق في كل مرة 100%)
        if hasattr(tts_engine, "proxy") and hasattr(tts_engine.proxy, "_driver") and hasattr(tts_engine.proxy._driver, "_tts"):
            tts_engine.proxy._driver._tts.Speak(text, 0)
        else:
            # بديل قياسي لأنظمة Linux / Raspberry Pi
            pyttsx3._activeEngines.clear()
            eng = pyttsx3.init()
            eng.setProperty("rate", 160)
            eng.say(text)
            eng.runAndWait()
            eng.stop()
    except Exception:
        try:
            pyttsx3._activeEngines.clear()
            eng = pyttsx3.init()
            eng.setProperty("rate", 160)
            eng.say(text)
            eng.runAndWait()
        except Exception as err:
            print(f"   [TTS Error]: {err}")

    # تفريغ ما التقطه الميكروفون أثناء تحدث السماعة
    clear_audio_queue()

def send_audio_warning(warning_type, direction_label="North East", azimuth_deg=45):
    """[تُستدعى حصرياً من الكود الرئيسي Main] لإطلاق التحذيرات الصوتية الأربعة"""
    if not system_running:
        print("[Muted Alert]: System is currently disabled by Emergency Switch.")
        return

    w_type = warning_type.upper()
    print(f"\n[Warning Received from Main]: Type={w_type} | Direction={direction_label} | Angle={azimuth_deg}")

    if w_type in ("DRONE", "MODE_A_DRONE"):
        play_wav_alert("DRONE_SIREN")
        speak_tts(f"Warning! Drone detected, angle {azimuth_deg} degrees, {direction_label}")

    elif w_type in ("MOTION", "MODE_B_BLINDSPOT"):
        play_wav_alert("TACTICAL_LOW")
        speak_tts(f"Alert! Rear motion detected, direction {direction_label}")

    elif w_type in ("TARGET", "MODE_C_TARGET"):
        print("   [Audio Out -> Speaker]: Tactical Scope Beep (Target in Box)")
        play_wav_alert("SCOPE_BEEP")
        clear_audio_queue()

    elif w_type in ("SOS", "MODE_D_SQUAD_SOS"):
        play_wav_alert("SQUAD_SOS")
        speak_tts(f"Emergency alert from squad! Threat at angle {azimuth_deg} degrees")

def activate_mode_from_main(mode_name):
    """[تُستدعى من الكود الرئيسي Main] لتفعيل أي نمط برمجياً ('A', 'B', 'C', 'D')"""
    if not system_running:
        return
    mode_map = {
        "A": CommandID.SET_MODE_A, "MODE_A": CommandID.SET_MODE_A,
        "B": CommandID.SET_MODE_B, "MODE_B": CommandID.SET_MODE_B,
        "C": CommandID.SET_MODE_C, "MODE_C": CommandID.SET_MODE_C,
        "D": CommandID.SET_MODE_D, "MODE_D": CommandID.SET_MODE_D,
    }
    cmd_id = mode_map.get(mode_name.upper())
    if cmd_id:
        event = {
            "source": "MAIN_CODE",
            "cmd_id": cmd_id.value,
            "timestamp": int(time.time())
        }
        print(f"\n[Mode Change from Main]: Activating Mode {mode_name}")
        on_voice_message_received(event)

def update_vitals_from_main(heart_rate, skin_temp):
    """[تُستدعى من الكود الرئيسي Main] لتحديث قيم النبض والحرارة القادمة من MCU 1"""
    soldier_vitals["heart_rate"] = heart_rate
    soldier_vitals["skin_temp"] = skin_temp

# =====================================================================
# 4. دالة زر الطوارئ من الكيبورد (تشغيل / إطفاء النظام فوراً)
# =====================================================================
def toggle_emergency_power(callback_fn):
    """Toggle system ON/OFF immediately via keyboard Space or 'S' key"""
    global system_running
    system_running = not system_running

    if not system_running:
        stop_all_audio_immediately()
        print("\n" + "!" * 60)
        print("   [KEYBOARD EMERGENCY]: System Suspended & Hardware Disabled (OFF)")
        print("   (Press SPACE or 'S' to resume system operation)")
        print("!" * 60)

        emergency_event = {
            "source": "KEYBOARD_EMERGENCY",
            "cmd_id": CommandID.EMERGENCY_OFF.value,
            "status": "SYSTEM_OFF",
            "timestamp": int(time.time())
        }
        callback_fn(emergency_event)
        speak_tts("Emergency stop. System disabled.", force_speak=True)

    else:
        clear_audio_queue()
        print("\n" + "=" * 60)
        print("   [KEYBOARD EMERGENCY]: System Resumed and Active (ON)")
        print("=" * 60)

        resume_event = {
            "source": "KEYBOARD_EMERGENCY",
            "cmd_id": CommandID.EMERGENCY_ON.value,
            "status": "SYSTEM_ON",
            "timestamp": int(time.time())
        }
        callback_fn(resume_event)
        speak_tts("System resumed and active.", force_speak=True)

def check_keyboard_emergency(callback_fn):
    """Non-blocking keyboard listener for emergency toggle & exit"""
    if os.name == "nt" and msvcrt.kbhit():
        key = msvcrt.getch()
        if key in (b" ", b"s", b"S"):
            toggle_emergency_power(callback_fn)
            return "TOGGLED"
        elif key in (b"\x1b", b"q", b"Q"):
            return "EXIT"
    return None

# =====================================================================
# 5. قسم استقبال الأوامر الصوتية وتوليد الحدث الموحد (Vosk -> Main)
# =====================================================================
def on_voice_message_received(event):
    """Handle recognized voice event and speak English confirmation"""
    print(f"   [Generated SYSTEM_EVENT -> Main]: {json.dumps(event)}")

    if event.get("source") == "KEYBOARD_EMERGENCY":
        return

    cmd_id = event["cmd_id"]

    if cmd_id == CommandID.SET_MODE_A:
        speak_tts("Command received. Mode Alpha, Sky Shield activated.")
    elif cmd_id == CommandID.SET_MODE_B:
        speak_tts("Command received. Mode Bravo, Blind Spot Guard activated.")
    elif cmd_id == CommandID.SET_MODE_C:
        speak_tts("Command received. Mode Charlie, Tactical Periscope activated.")
    elif cmd_id == CommandID.SET_MODE_D:
        speak_tts("Command received. Standby mode activated.")
    elif cmd_id == CommandID.QUERY_TIME:
        now = datetime.now()
        speak_tts(f"The time is {now.strftime('%I:%M %p')}")
    elif cmd_id == CommandID.QUERY_VITALS:
        hr = soldier_vitals["heart_rate"]
        temp = soldier_vitals["skin_temp"]
        speak_tts(f"Heart rate is {hr} beats per minute, skin temperature is {temp} degrees.")

def audio_callback(indata, frames, time_info, status):
    if status:
        print(status, file=sys.stderr)
    if system_running:
        audio_queue.put(bytes(indata))

def parse_vosk_message(vosk_json_str, callback_fn=on_voice_message_received):
    """
    فلترة صارمة: لا يطبع أي شيء على التيرمنال ولا يخرج صوتاً
    إلا إذا كانت العبارة المنطوقة موجودة داخل قاموس INTENT_MAPPER
    """
    if not system_running:
        return

    vosk_raw_output = json.loads(vosk_json_str)
    raw_text = vosk_raw_output.get("text", "").strip()

    # إزالة رموز الكلمات غير المعروفة [unk] وتنظيف المسافات الزائدة
    clean_text = " ".join(raw_text.replace("[unk]", "").split())

    if not clean_text:
        return

    # البحث عن تطابق مع أوامر القاموس المعتمدة فقط
    matched_cmd_id = INTENT_MAPPER.get(clean_text)
    matched_phrase = clean_text if matched_cmd_id else None

    if not matched_cmd_id:
        for phrase, cid in INTENT_MAPPER.items():
            if phrase in clean_text:
                matched_cmd_id = cid
                matched_phrase = phrase
                break

    # لا يتم الطباعة على التيرمنال أو التوليد إلا إذا وُجد الأمر في القاموس فعلاً
    if matched_cmd_id:
        print(f"\n[Recognized Dictionary Command]: \"{matched_phrase}\"")
        system_event = {
            "source": "VOICE",
            "cmd_id": matched_cmd_id.value,
            "timestamp": int(time.time())
        }
        callback_fn(system_event)

def start_voice_module(main_callback=on_voice_message_received):
    """Start continuous offline English voice recognition & emergency listener"""
    model_path = "model_en"
    samplerate = 16000

    if not os.path.exists(model_path):
        print("Error: 'model_en' folder not found. Please download the English Vosk model.")
        sys.exit(1)

    print("Loading Offline English Voice Model (Vosk)...")
    model = Model(model_path)
    grammar = json.dumps(ALLOWED_GRAMMAR)
    recognizer = KaldiRecognizer(model, samplerate, grammar)

    with sd.RawInputStream(samplerate=samplerate, blocksize=4000, dtype="int16",
                           channels=1, callback=audio_callback):
        print("\n============================================================")
        print("   FALCON EYE - ENGLISH VOICE MODULE & STATE MACHINE READY")
        print("============================================================")
        print("• Mode A (Anti-Drone) : 'mode one'")
        print("• Mode B (Blind-Spot) : 'mode two'")
        print("• Mode C (Periscope)  : 'mode three'")
        print("• Mode D (Standby)    : 'standby'")
        print("• Status Queries      : 'time' |'health'")
        print("• [Emergency Switch]  : Press (SPACE) or (S) to Toggle System ON/OFF")
        print("• [Exit Program]      : Press (ESC) or (Q) to Quit\n")

        try:
            while True:
                kb_action = check_keyboard_emergency(main_callback)
                if kb_action == "EXIT":
                    print("\nSystem terminated via keyboard.")
                    break
                elif kb_action == "TOGGLED":
                    recognizer.Reset()
                    continue

                if not system_running:
                    time.sleep(0.05)
                    continue

                try:
                    data = audio_queue.get(timeout=0.05)
                except queue.Empty:
                    continue

                if recognizer.AcceptWaveform(data):
                    parse_vosk_message(recognizer.Result(), main_callback)
                    recognizer.Reset()

        except KeyboardInterrupt:
            print("\nVoice module stopped successfully.")

if __name__ == "__main__":
    start_voice_module()
