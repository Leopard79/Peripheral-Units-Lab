import os
import sys
import io
import time
import json
import queue
import wave
import tempfile
import hashlib
from enum import Enum
from datetime import datetime
import numpy as np
import sounddevice as sd
import pygame
import pyttsx3
from gtts import gTTS
from vosk import Model, KaldiRecognizer
import arabic_reshaper
from bidi.algorithm import get_display

# استدعاء مكتبة لوحة المفاتيح المدمجة في ويندوز للاستجابة الفورية بدون تثبيت مكاتب إضافية
if os.name == "nt":
    import msvcrt

# تهيئة مشغل الصوت بزمن تأخير منخفض جداً (< 10ms) لتشغيل تنبيهات WAV الفورية
pygame.mixer.pre_init(44100, -16, 1, 512)
pygame.mixer.init()

# تهيئة محرك النطق المحلي الاحتياطي (pyttsx3)
tts_engine = pyttsx3.init()
tts_engine.setProperty("rate", 155)

# مسار آمن في النظام لحفظ الأصوات العربية أوفلاين (يتجنب مشاكل صلاحيات OneDrive)
AUDIO_CACHE_DIR = os.path.join(tempfile.gettempdir(), "falcon_eye_tts_cache")
os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)

def print_ar(text):
    """ربط الحروف العربية وتصحيح اتجاهها للطباعة السليمة في الطرفية"""
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    print(bidi_text)

# =====================================================================
# 1. رموز الأوامر الصوتية القياسية ومتغير حالة الطوارئ العام
# =====================================================================
class CommandID(str, Enum):
    # أوامر طلب تفعيل الأنماط الأربعة (من الميكروفون -> إلى الكود الرئيسي Main)
    SET_MODE_A = "SET_MODE_A"           # النمط الأول: درع السماء
    SET_MODE_B = "SET_MODE_B"           # النمط الثاني: تأمين الخلف (الحارس الصامت)
    SET_MODE_C = "SET_MODE_C"           # النمط الثالث: المنظار التكتيكي
    SET_MODE_D = "SET_MODE_D"           # النمط الرابع: وضع السكون / إيقاف العتاد

    # أوامر الاستعلام الصوتي عن الحالة
    QUERY_TIME = "QUERY_TIME"           # طلب الوقت / الساعة
    QUERY_VITALS = "QUERY_VITALS"       # طلب الحالة الصحية (النبض والحرارة)

    # رموز خاصة بزر الطوارئ من الكيبورد
    EMERGENCY_OFF = "SET_MODE_D"        # إيقاف طوارئ (يفعل وضع السكون ويوقف المحركات)
    EMERGENCY_ON = "EMERGENCY_RESUME"   # إعادة تشغيل النظام بعد الطوارئ

# قاموس المطابقة (Intent Mapper): مخصص لأوامر الجندي الصوتية فقط
INTENT_MAPPER = {
    "تفعيل النظام الف": CommandID.SET_MODE_A,
    "تفعيل النظام واحد": CommandID.SET_MODE_A,
    "درع السماء": CommandID.SET_MODE_A,
    "تأمين الخلف": CommandID.SET_MODE_B,
    "تفعيل النظام باء": CommandID.SET_MODE_B,
    "تفعيل النظام اثنين": CommandID.SET_MODE_B,
    "الحارس الصامت": CommandID.SET_MODE_B,
    "المنظار التكتيكي": CommandID.SET_MODE_C,
    "تفعيل النظام جيم": CommandID.SET_MODE_C,
    "تفعيل النظام ثلاثة": CommandID.SET_MODE_C,
    "وضع السكون": CommandID.SET_MODE_D,
    "تفعيل النظام دال": CommandID.SET_MODE_D,
    "تفعيل النظام اربعة": CommandID.SET_MODE_D,
    "ايقاف مؤقت": CommandID.SET_MODE_D,
    "الوقت": CommandID.QUERY_TIME,
    "الساعة": CommandID.QUERY_TIME,
    "الحالة الصحية": CommandID.QUERY_VITALS,
    "النبض": CommandID.QUERY_VITALS
}

ALLOWED_GRAMMAR = list(INTENT_MAPPER.keys()) + ["[unk]"]

# حالة تشغيل النظام (True = يعمل، False = متوقف بزر الطوارئ)
system_running = True

# قراءات الجندي الصحية (يتم تحديثها من الكود الرئيسي Main)
soldier_vitals = {
    "heart_rate": 78,     # النبض (bpm)
    "skin_temp": 36.8     # الحرارة (C)
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
    # 1. صافرة إنذار الدرون (النمط A)
    t1 = np.linspace(0, 0.16, int(fs * 0.16), False)
    siren = np.concatenate([0.7 * np.sin(2 * np.pi * 1300 * t1),
                            0.7 * np.sin(2 * np.pi * 900 * t1)] * 3)
    SOUND_EFFECTS["DRONE_SIREN"] = _create_memory_wav(siren, fs)

    # 2. نغمة تنبيه تكتيكية منخفضة لكشف التسلل الخلفي (النمط B)
    t2 = np.linspace(0, 0.12, int(fs * 0.12), False)
    whisper_tone = np.concatenate([0.25 * np.sin(2 * np.pi * 320 * t2),
                                   np.zeros(int(fs * 0.06)),
                                   0.25 * np.sin(2 * np.pi * 320 * t2)])
    SOUND_EFFECTS["TACTICAL_LOW"] = _create_memory_wav(whisper_tone, fs)

    # 3. تنبيه صوتي خفيف عند دخول هدف مربع الكشف (النمط C)
    t3 = np.linspace(0, 0.08, int(fs * 0.08), False)
    scope_beep = 0.35 * np.sin(2 * np.pi * 880 * t3)
    SOUND_EFFECTS["SCOPE_BEEP"] = _create_memory_wav(scope_beep, fs)

    # 4. إنذار طارئ لكسر السكون عند وصول تحذير من الفرقة (النمط D)
    t4 = np.linspace(0, 0.1, int(fs * 0.1), False)
    sos_alarm = np.concatenate([0.8 * np.sin(2 * np.pi * 1500 * t4),
                                np.zeros(int(fs * 0.05))] * 4)
    SOUND_EFFECTS["SQUAD_SOS"] = _create_memory_wav(sos_alarm, fs)

init_warning_sounds()

# =====================================================================
# 3. دوال الصوت والتحذيرات القادمة من الكود الرئيسي (Main -> السماعة)
# =====================================================================
audio_queue = queue.Queue()

def clear_audio_queue():
    """تفريغ طابور الميكروفون لمنع النظام من سماع صدى صوته أو أوامر متأخرة"""
    while not audio_queue.empty():
        try:
            audio_queue.get_nowait()
        except queue.Empty:
            break

def stop_all_audio_immediately():
    """قطع كافة الأصوات والصافرات الجارية فوراً عند ضغط زر الطوارئ"""
    pygame.mixer.stop()
    pygame.mixer.music.stop()
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
    """نطق الرسائل بالعربية عبر السماعة مع حفظها محلياً للعمل أوفلاين"""
    if not system_running and not force_speak:
        return

    print_ar(f"   [إرسال للسماعة Audio Out]: {text}")

    file_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
    audio_path = os.path.join(AUDIO_CACHE_DIR, f"{file_hash}.mp3")

    try:
        if not os.path.exists(audio_path):
            tts = gTTS(text=text, lang="ar")
            tts.save(audio_path)

        pygame.mixer.music.load(audio_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.wait(10)
        pygame.mixer.music.unload()

    except Exception:
        tts_engine.say(text)
        tts_engine.runAndWait()

    clear_audio_queue()

def send_audio_warning(warning_type, direction_label="شمال شرق", azimuth_deg=45):
    """
    [تُستدعى حصرياً من الكود الرئيسي Main]
    تستقبل أمر التحذير (مسيرة، حركة، هدف، طوارئ) من الـ Main وتطلقه في السماعة
    """
    if not system_running:
        print_ar("[تنبيه مكتوم]: النظام متوقف حالياً بواسطة زر الطوارئ.")
        return

    w_type = warning_type.upper()
    print_ar(f"\n[أمر تحذير مستلم من Main]: النوع={w_type} | الاتجاه={direction_label} | الزاوية={azimuth_deg}")

    if w_type in ("DRONE", "MODE_A_DRONE"):
        play_wav_alert("DRONE_SIREN")
        speak_tts(f"تحذير مسيرة، زاوية {azimuth_deg}، جهة {direction_label}")

    elif w_type in ("MOTION", "MODE_B_BLINDSPOT"):
        play_wav_alert("TACTICAL_LOW")
        speak_tts(f"تنبيه، حركة بالخلف، اتجاه {direction_label}")

    elif w_type in ("TARGET", "MODE_C_TARGET"):
        print_ar("   [إرسال للسماعة Audio Out]: نغمة تنبيه خفيفة (دخول هدف مربع الكشف)")
        play_wav_alert("SCOPE_BEEP")
        clear_audio_queue()

    elif w_type in ("SOS", "MODE_D_SQUAD_SOS"):
        play_wav_alert("SQUAD_SOS")
        speak_tts(f"إنذار طارئ من الفرقة، خطر بزاوية {azimuth_deg}")

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
        print_ar(f"\n[أمر تغيير نمط قادم من Main]: تفعيل {mode_name}")
        on_voice_message_received(event)

def update_vitals_from_main(heart_rate, skin_temp):
    """[تُستدعى من الكود الرئيسي Main] لتحديث قيم النبض والحرارة القادمة من MCU 1"""
    soldier_vitals["heart_rate"] = heart_rate
    soldier_vitals["skin_temp"] = skin_temp

# =====================================================================
# 4. دالة زر الطوارئ من الكيبورد (تشغيل / إطفاء النظام فوراً)
# =====================================================================
def toggle_emergency_power(callback_fn):
    """تبديل حالة النظام بين التشغيل والإيقاف الطارئ عند ضغط زر الكيبورد"""
    global system_running
    system_running = not system_running

    if not system_running:
        # إيقاف فوري لكافة الأصوات الجارية وتفريغ الميكروفون
        stop_all_audio_immediately()
        print_ar("\n" + "!" * 56)
        print_ar("   [طوارئ الكيبورد]: تم إيقاف النظام وتعطيل العتاد مؤقتاً (OFF)")
        print_ar("   (اضغط زر المسافة Space أو حرف S لإعادة تشغيل النظام)")
        print_ar("!" * 56)

        # إرسال أمر إيقاف طوارئ إلى الكود الرئيسي (Main) لإطفاء المحركات والكاميرا
        emergency_event = {
            "source": "KEYBOARD_EMERGENCY",
            "cmd_id": CommandID.EMERGENCY_OFF.value,
            "status": "SYSTEM_OFF",
            "timestamp": int(time.time())
        }
        callback_fn(emergency_event)
        speak_tts("إيقاف طوارئ، تم تعطيل النظام", force_speak=True)

    else:
        clear_audio_queue()
        print_ar("\n" + "=" * 56)
        print_ar("   [طوارئ الكيبورد]: تمت إعادة تشغيل النظام بنجاح (ON)")
        print_ar("=" * 56)

        resume_event = {
            "source": "KEYBOARD_EMERGENCY",
            "cmd_id": CommandID.EMERGENCY_ON.value,
            "status": "SYSTEM_ON",
            "timestamp": int(time.time())
        }
        callback_fn(resume_event)
        speak_tts("تمت إعادة تشغيل النظام", force_speak=True)

def check_keyboard_emergency(callback_fn):
    """فحص ضغطات الكيبورد لحظياً دون إبطاء حلقة الصوت"""
    if os.name == "nt" and msvcrt.kbhit():
        key = msvcrt.getch()
        # زر المسافة (Space) أو حرف 's' لتشغيل وإطفاء النظام
        if key in (b" ", b"s", b"S"):
            toggle_emergency_power(callback_fn)
            return "TOGGLED"
        # زر ESC أو حرف 'q' للخروج النهائي من البرنامج
        elif key in (b"\x1b", b"q", b"Q"):
            return "EXIT"
    return None

# =====================================================================
# 5. قسم استقبال الأوامر الصوتية من الميكروفون وتوليد الحدث (Vosk -> Main)
# =====================================================================
def on_voice_message_received(event):
    """معالجة الأوامر الصوتية المستقبلة وتوليد الرد الصوتي"""
    print_ar(f"\n[تم توليد حدث للنظام الرئيسي]: {json.dumps(event, ensure_ascii=False)}")

    # إذا كان الحدث قادماً من زر طوارئ الكيبورد نكتفي بطباعته وإرساله للـ Main
    if event.get("source") == "KEYBOARD_EMERGENCY":
        return

    cmd_id = event["cmd_id"]

    if cmd_id == CommandID.SET_MODE_A:
        speak_tts("تم استلام الأمر، تفعيل النظام ألف، درع السماء")
    elif cmd_id == CommandID.SET_MODE_B:
        speak_tts("تم استلام الأمر، تأمين الخلف")
    elif cmd_id == CommandID.SET_MODE_C:
        speak_tts("تم استلام الأمر، المنظار التكتيكي")
    elif cmd_id == CommandID.SET_MODE_D:
        speak_tts("تم استلام الأمر، وضع السكون")
    elif cmd_id == CommandID.QUERY_TIME:
        now = datetime.now()
        speak_tts(f"الساعة الآن {now.hour} و {now.minute} دقيقة")
    elif cmd_id == CommandID.QUERY_VITALS:
        hr = soldier_vitals["heart_rate"]
        temp = soldier_vitals["skin_temp"]
        speak_tts(f"معدل النبض {hr} نبضة، وحرارة الجلد {temp} درجة")

def audio_callback(indata, frames, time_info, status):
    if status:
        print(status, file=sys.stderr)
    if system_running:
        audio_queue.put(bytes(indata))

def parse_vosk_message(vosk_json_str, callback_fn=on_voice_message_received):
    """تحويل نص Vosk الخام إلى SYSTEM_EVENT قياسي وتمريره إلى الكود الرئيسي Main"""
    if not system_running:
        return

    vosk_raw_output = json.loads(vosk_json_str)
    recognized_text = vosk_raw_output.get("text", "").strip()

    if not recognized_text or recognized_text == "[unk]":
        return

    print_ar(f"\n[رسالة صوتية مستقبلة Vosk]: {json.dumps(vosk_raw_output, ensure_ascii=False)}")

    matched_cmd_id = INTENT_MAPPER.get(recognized_text)
    if not matched_cmd_id:
        for phrase, cid in INTENT_MAPPER.items():
            if phrase in recognized_text:
                matched_cmd_id = cid
                break

    if matched_cmd_id:
        system_event = {
            "source": "VOICE",
            "cmd_id": matched_cmd_id.value,
            "timestamp": int(time.time())
        }
        callback_fn(system_event)

def start_voice_module(main_callback=on_voice_message_received):
    """تشغيل حلقة الاستماع للأوامر الصوتية ومراقبة زر الطوارئ"""
    model_path = "model"
    samplerate = 16000

    if not os.path.exists(model_path):
        print_ar("خطأ: لم يتم العثور على مجلد 'model' بجانب الكود.")
        sys.exit(1)

    print_ar("جاري تحميل نموذج الصوت الأوفلاين (Vosk)...")
    model = Model(model_path)
    grammar = json.dumps(ALLOWED_GRAMMAR, ensure_ascii=False)
    recognizer = KaldiRecognizer(model, samplerate, grammar)

    with sd.RawInputStream(samplerate=samplerate, blocksize=4000, dtype="int16",
                           channels=1, callback=audio_callback):
        print_ar("\n========================================================")
        print_ar("   وحدة الصوت جاهزة (الأوامر من الميكروفون | التحذيرات من Main)")
        print_ar("========================================================")
        print_ar("• أوامر الميكروفون لتغيير النمط: 'تفعيل النظام الف' | 'تأمين الخلف' | 'المنظار التكتيكي' | 'وضع السكون'")
        print_ar("• أوامر الميكروفون للاستعلام: 'الوقت' | 'الساعة' | 'الحالة الصحية' | 'النبض'")
        print_ar("• [زر الطوارئ بالكيبورد]: اضغط (Space المسافة) أو حرف (S) لإيقاف/تشغيل النظام فوراً")
        print_ar("• [إغلاق البرنامج]: اضغط زر (ESC) أو حرف (Q) للخروج النهائي\n")

        try:
            while True:
                # 1. فحص زر الطوارئ من الكيبورد في كل دورة (استجابة فورية < 50ms)
                kb_action = check_keyboard_emergency(main_callback)
                if kb_action == "EXIT":
                    print_ar("\nتم إغلاق النظام نهائياً عبر الكيبورد.")
                    break
                elif kb_action == "TOGGLED":
                    recognizer.Reset()
                    continue

                # 2. إذا كان النظام متوقفاً بزر الطوارئ، ننتظر ضغطة التشغيل دون معالجة الصوت
                if not system_running:
                    time.sleep(0.05)
                    continue

                # 3. سحب الصوت من الطابور بمهلة زمنية قصيرة (0.05 ثانية) ليبقى الكيبورد سريع الاستجابة
                try:
                    data = audio_queue.get(timeout=0.05)
                except queue.Empty:
                    continue

                if recognizer.AcceptWaveform(data):
                    parse_vosk_message(recognizer.Result(), main_callback)
                    recognizer.Reset()

        except KeyboardInterrupt:
            print_ar("\nتم إيقاف وحدة الصوت بنجاح.")

if __name__ == "__main__":
    start_voice_module()