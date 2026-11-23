#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_arduino_version.h>
#include <ESP32Servo.h>

#define PAN_PIN  15
#define TILT_PIN 2

uint8_t receiverMacAddress[] = {0x70, 0x4B, 0xCA, 0x8E, 0xED, 0x70};

// ===== إعدادات التتبع (صورة 640x480) =====
const int   NEUTRAL_PAN  = 90;
const int   NEUTRAL_TILT = 90;
const int   CENTER_X     = 320;
const int   CENTER_Y     = 240;
const int   DEADZONE     = 20;      // بكسل
const float KP           = 0.012f;  // درجة لكل بكسل خطأ لكل رسالة (عدّلها بالتجربة)
const int   SIGN_PAN     = -1;      // اقلب الإشارة إذا هربت المنصة عن الهدف
const int   SIGN_TILT    = -1;
const bool  RETURN_NEUTRAL_ON_LOST = false;  // false = تثبت مكانها إذا ضاع الهدف

// حدود ميكانيكية آمنة للسيرفو (قلّصها إذا المنصة بتصطدم)
const float PAN_MIN  = 10.0f, PAN_MAX  = 170.0f;
const float TILT_MIN = 30.0f, TILT_MAX = 150.0f;

const unsigned long TARGET_TIMEOUT     = 1000;  // ما وصلت D خلال هالمدة => الهدف ضاع
const unsigned long ESPNOW_COOLDOWN    = 3000;
const unsigned long HELLO_INTERVAL     = 500;
const unsigned long HEARTBEAT_INTERVAL = 2000;

// الهيكل: يجب أن يطابق المستقبل تماماً
// alertActive: 0 = handshake/heartbeat، 1 = إنذار
typedef struct __attribute__((packed)) {
    uint8_t  alertActive;
    int16_t  threatAngle;
    uint32_t msgCounter;
} DroneAlertPacket;

Servo panServo;
Servo tiltServo;

float panAngle  = NEUTRAL_PAN;
float tiltAngle = NEUTRAL_TILT;

bool targetActive = false;
unsigned long lastDTime = 0;

volatile bool linked = false;
bool prevLinked = false;
uint32_t packetCounter = 0;
unsigned long lastAlertTime = 0, lastHelloTime = 0, lastHeartbeatTime = 0;

char lineBuf[32];
uint8_t lineLen = 0;
bool lineOverflow = false;

#if ESP_ARDUINO_VERSION_MAJOR >= 3
void onSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
    linked = (status == ESP_NOW_SEND_SUCCESS);
}
#else
void onSent(const uint8_t *mac, esp_now_send_status_t status) {
    linked = (status == ESP_NOW_SEND_SUCCESS);
}
#endif

void sendPacket(uint8_t active, int16_t angle) {
    DroneAlertPacket pkt;
    pkt.alertActive = active;
    pkt.threatAngle = angle;
    pkt.msgCounter  = ++packetCounter;
    esp_now_send(receiverMacAddress, (uint8_t *)&pkt, sizeof(pkt));
}

void goNeutral() {
    panAngle  = NEUTRAL_PAN;
    tiltAngle = NEUTRAL_TILT;
    panServo.write(NEUTRAL_PAN);
    tiltServo.write(NEUTRAL_TILT);
}

void trackTarget(int x, int y) {
    int errorX = x - CENTER_X;
    int errorY = y - CENTER_Y;

    if (abs(errorX) > DEADZONE) {
        panAngle = constrain(panAngle + SIGN_PAN * errorX * KP, PAN_MIN, PAN_MAX);
        panServo.write((int)panAngle);
    }
    if (abs(errorY) > DEADZONE) {
        tiltAngle = constrain(tiltAngle + SIGN_TILT * errorY * KP, TILT_MIN, TILT_MAX);
        tiltServo.write((int)tiltAngle);
    }
}

void handleLine(const char *s) {
    if (strcmp(s, "S") == 0) {
        goNeutral();
        if (targetActive) Serial.println("[TARGET] OFF (S)");
        targetActive = false;
        return;
    }

    int x = 0, y = 0, threatAngle = 0;
    if (sscanf(s, "D,%d,%d,%d", &x, &y, &threatAngle) == 3) {
        unsigned long now = millis();
        lastDTime = now;

        if (!targetActive) {
            targetActive = true;
            Serial.println("[TARGET] ON");
        }

        trackTarget(x, y);

        if (now - lastAlertTime >= ESPNOW_COOLDOWN) {
            lastAlertTime = now;
            sendPacket(1, (int16_t)threatAngle);
        }
    }
}

void readSerial() {
    while (Serial.available()) {
        char c = (char)Serial.read();
        if (c == '\n') {
            if (!lineOverflow) {
                lineBuf[lineLen] = 0;
                handleLine(lineBuf);
            }
            lineLen = 0;
            lineOverflow = false;
        } else if (c != '\r') {
            if (lineLen < sizeof(lineBuf) - 1) lineBuf[lineLen++] = c;
            else lineOverflow = true;
        }
    }
}

void setup() {
    Serial.begin(115200);

    WiFi.mode(WIFI_STA);
    if (esp_now_init() == ESP_OK) {
        esp_now_register_send_cb(onSent);
        esp_now_peer_info_t peer = {};
        memcpy(peer.peer_addr, receiverMacAddress, 6);
        peer.channel = 0;
        peer.encrypt = false;
        esp_now_add_peer(&peer);
    } else {
        Serial.println("[ERROR] ESP-NOW init failed");
    }

    ESP32PWM::allocateTimer(0);
    ESP32PWM::allocateTimer(1);
    panServo.setPeriodHertz(50);
    tiltServo.setPeriodHertz(50);
    panServo.attach(PAN_PIN, 500, 2400);
    tiltServo.attach(TILT_PIN, 500, 2400);
    goNeutral();
}

void loop() {
    readSerial();
    unsigned long now = millis();

    if (targetActive && (now - lastDTime > TARGET_TIMEOUT)) {
        targetActive = false;
        if (RETURN_NEUTRAL_ON_LOST) goNeutral();
        Serial.println("[TARGET] OFF (timeout)");
    }

    if (!linked) {
        if (now - lastHelloTime >= HELLO_INTERVAL) {
            lastHelloTime = now;
            sendPacket(0, 0);
        }
    } else if (now - lastHeartbeatTime >= HEARTBEAT_INTERVAL) {
        lastHeartbeatTime = now;
        sendPacket(0, 0);
    }

    if (linked != prevLinked) {
        prevLinked = linked;
        Serial.println(linked ? "[LINK] up" : "[LINK] down");
    }
}