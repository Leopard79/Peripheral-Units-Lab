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

# تهيئة مشغل الصوت بزمن تأخير منخفض جداً (< 10ms) لتشغيل تنبيهات WAV الفورية
pygame.mixer.pre_init(44100, -16, 1, 512)
pygame.mixer.init()

# تهيئة محرك النطق الاحتياطي (pyttsx3)
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
# 1. رموز الأوامر الصوتية القياسية (Command Enum IDs) وقاموس المطابقة
# =====================================================================
class CommandID(str, Enum):
    # أوامر طلب تفعيل الأنماط الأربعة (تُرسل كـ SYSTEM_EVENT إلى الكود الرئيسي Main)
    SET_MODE_A = "SET_MODE_A"       # النمط الأول: درع السماء
    SET_MODE_B = "SET_MODE_B"       # النمط الثاني: تأمين الخلف (الحارس الصامت)
    SET_MODE_C = "SET_MODE_C"       # النمط الثالث: المنظار التكتيكي
    SET_MODE_D = "SET_MODE_D"       # النمط الرابع: وضع السكون

    # أوامر الاستعلام الصوتي عن الحالة
    QUERY_TIME = "QUERY_TIME"       # طلب الوقت / الساعة
    QUERY_VITALS = "QUERY_VITALS"   # طلب الحالة الصحية (النبض والحرارة)

    # كلمات مخصصة لاختبار سماع التحذيرات الأربعة في المخبر
    TEST_ALERT_A = "TEST_ALERT_A"   # اختبار تحذير الدرون (Mode A)
    TEST_ALERT_B = "TEST_ALERT_B"   # اختبار تحذير التسلل الخلفي (Mode B)
    TEST_ALERT_C = "TEST_ALERT_C"   # اختبار تنبيه المنظار (Mode C)
    TEST_ALERT_D = "TEST_ALERT_D"   # اختبار إنذار الفرقة الطارئ (Mode D)

# قاموس المطابقة (Intent Mapper): يحول الكلمات المسموعة إلى Command IDs ثابتة
INTENT_MAPPER = {
    "تفعيل الوضع واحد": CommandID.SET_MODE_A,
    "درع السماء": CommandID.SET_MODE_A,
    "تأمين الخلف": CommandID.SET_MODE_B,
    "تفعيل الوضع الثاني": CommandID.SET_MODE_B,
    "الحارس الصامت": CommandID.SET_MODE_B,
    "تفعيل النظام ثلاثة": CommandID.SET_MODE_C,
    "وضع السكون": CommandID.SET_MODE_D,
    "ايقاف مؤقت": CommandID.SET_MODE_D,
    "الوقت": CommandID.QUERY_TIME,
    "الساعة": CommandID.QUERY_TIME,
    "الحالة الصحية": CommandID.QUERY_VITALS,
    "النبض": CommandID.QUERY_VITALS,
    # كلمات اختبار التحذيرات الصوتية
    "مسيرة": CommandID.TEST_ALERT_A,
    "حركة": CommandID.TEST_ALERT_B,
    "هدف": CommandID.TEST_ALERT_C,
    "طوارئ": CommandID.TEST_ALERT_D
}

ALLOWED_GRAMMAR = list(INTENT_MAPPER.keys()) + ["[unk]"]

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
# 3. قسم إرسال التحذيرات والردود الصوتية إلى السماعة (Audio Out)
# =====================================================================
audio_queue = queue.Queue()

def clear_audio_queue():
    """تفريغ طابور الميكروفون بعد انتهاء السماعة لمنع النظام من سماع صدى صوته"""
    while not audio_queue.empty():
        try:
            audio_queue.get_nowait()
        except queue.Empty:
            break

def play_wav_alert(sound_key):
    """تشغيل ملف WAV الفوري عبر السماعة"""
    if sound_key in SOUND_EFFECTS:
        channel = SOUND_EFFECTS[sound_key].play()
        while channel.get_busy():
            pygame.time.wait(5)

def speak_tts(text):
    """نطق الرسائل والأرقام المتغيرة بالعربية عبر السماعة مع حفظها محلياً للعمل أوفلاين"""
    print_ar(f"   [إرسال للسماعة Audio Out]: {text}")

    # إنشاء اسم ملف ثابت لكل جملة عربية في الذاكرة المحلية
    file_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
    audio_path = os.path.join(AUDIO_CACHE_DIR, f"{file_hash}.mp3")

    try:
        # توليد الملف الصوتي العربي في المرة الأولى فقط وحفظه على الجهاز
        if not os.path.exists(audio_path):
            tts = gTTS(text=text, lang="ar")
            tts.save(audio_path)

        # تشغيل الصوت العربي المحفوظ محلياً عبر السماعة بدون إنترنت
        pygame.mixer.music.load(audio_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.wait(10)
        pygame.mixer.music.unload()

    except Exception:
        # المحرك الاحتياطي pyttsx3 في حال عدم توفر الملف
        tts_engine.say(text)
        tts_engine.runAndWait()

    clear_audio_queue()

def send_audio_warning(warning_type, direction_label="شمال شرق", azimuth_deg=45):
    """
    الدالة المسؤولة عن إرسال التحذيرات الصوتية للسماعة حسب نمط التشغيل:
    يستدعيها الكود الرئيسي (Main) مباشرة عند كشف خطر من الكاميرا أو الفرقة
    """
    if warning_type == "MODE_A_DRONE":
        # تحذير النمط الأول: صافرة إنذار + نطق زاوية وجهة الدرون
        play_wav_alert("DRONE_SIREN")
        speak_tts(f"تحذير مسيرة، زاوية {azimuth_deg}، جهة {direction_label}")

    elif warning_type == "MODE_B_BLINDSPOT":
        # تحذير النمط الثاني: نغمة تكتيكية منخفضة + همس باتجاه التسلل بالخلف
        play_wav_alert("TACTICAL_LOW")
        speak_tts(f"تنبيه، حركة بالخلف، اتجاه {direction_label}")

    elif warning_type == "MODE_C_TARGET":
        # تحذير النمط الثالث: تنبيه صوتي خفيف عند دخول هدف مربع الكشف
        print_ar("   [إرسال للسماعة Audio Out]: نغمة تنبيه خفيفة (دخول هدف مربع الكشف)")
        play_wav_alert("SCOPE_BEEP")
        clear_audio_queue()

    elif warning_type == "MODE_D_SQUAD_SOS":
        # تحذير النمط الرابع: كسر السكون عند استقبال إنذار طارئ من الفرقة عبر ESP-NOW
        play_wav_alert("SQUAD_SOS")
        speak_tts(f"إنذار طارئ من الفرقة، خطر بزاوية {azimuth_deg}")

# =====================================================================
# 4. قسم استقبال الأوامر الصوتية وتوليد الحدث الموحد (SYSTEM_EVENT)
# =====================================================================
def on_voice_message_received(event):
    """معالجة الرسالة الصوتية المستقبلة وإرسال الرد أو التحذير المناسب"""
    print_ar(f"\n[تم توليد حدث للنظام الرئيسي]: {json.dumps(event, ensure_ascii=False)}")
    cmd_id = event["cmd_id"]

    # إشعار صوتي بتلقي أمر تغيير النمط
    if cmd_id == CommandID.SET_MODE_A:
        speak_tts("تم استلام الأمر، تفعيل النظام ألف، درع السماء")
    elif cmd_id == CommandID.SET_MODE_B:
        speak_tts("تم استلام الأمر، تأمين الخلف")
    elif cmd_id == CommandID.SET_MODE_C:
        speak_tts("تم استلام الأمر، المنظار التكتيكي")
    elif cmd_id == CommandID.SET_MODE_D:
        speak_tts("تم استلام الأمر، وضع السكون")

    # الرد الصوتي على استعلامات الجندي (الساعة / الحالة الصحية)
    elif cmd_id == CommandID.QUERY_TIME:
        now = datetime.now()
        speak_tts(f"الساعة الآن {now.hour} و {now.minute} دقيقة")

    elif cmd_id == CommandID.QUERY_VITALS:
        hr = soldier_vitals["heart_rate"]
        temp = soldier_vitals["skin_temp"]
        speak_tts(f"معدل النبض {hr} نبضة، وحرارة الجلد {temp} درجة")

    # تشغيل التحذيرات الصوتية عند نطق كلمات الاختبار في المخبر
    elif cmd_id == CommandID.TEST_ALERT_A:
        send_audio_warning("MODE_A_DRONE", direction_label="شمال شرق", azimuth_deg=45)
    elif cmd_id == CommandID.TEST_ALERT_B:
        send_audio_warning("MODE_B_BLINDSPOT", direction_label="الجنوب")
    elif cmd_id == CommandID.TEST_ALERT_C:
        send_audio_warning("MODE_C_TARGET")
    elif cmd_id == CommandID.TEST_ALERT_D:
        send_audio_warning("MODE_D_SQUAD_SOS", azimuth_deg=110)

def audio_callback(indata, frames, time_info, status):
    if status:
        print(status, file=sys.stderr)
    audio_queue.put(bytes(indata))

def parse_vosk_message(vosk_json_str, callback_fn=on_voice_message_received):
    """تحويل نص Vosk الخام إلى SYSTEM_EVENT قياسي وتمريره عبر الـ Callback"""
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
    """تشغيل حلقة الاستماع للأوامر الصوتية عبر الميكروفون"""
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
        print_ar("   وحدة الصوت (استقبال الأوامر + إرسال التحذيرات الصوتية)")
        print_ar("========================================================")
        print_ar("• أوامر الاستعلام: 'الوقت' | 'الساعة' | 'الحالة الصحية' | 'النبض'")
        print_ar("• رسائل الأنماط (تُرسل للـ Main): 'تفعيل النظام الف' | 'تأمين الخلف' | 'المنظار التكتيكي' | 'وضع السكون'")
        print_ar("• اختبار التحذيرات الصوتية: 'مسيرة' | 'حركة' | 'هدف' | 'طوارئ'\n")

        try:
            while True:
                data = audio_queue.get()
                if recognizer.AcceptWaveform(data):
                    parse_vosk_message(recognizer.Result(), main_callback)
                    recognizer.Reset()
        except KeyboardInterrupt:
            print_ar("\nتم إيقاف وحدة الصوت بنجاح.")

if __name__ == "__main__":
    start_voice_module()