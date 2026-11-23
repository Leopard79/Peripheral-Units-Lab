#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_arduino_version.h>
#include <ESP32Servo.h>

#define PAN_PIN  15
#define TILT_PIN 2

uint8_t receiverMacAddress[] = {0x70, 0x4B, 0xCA, 0x8E, 0xED, 0x70};

const int NEUTRAL_PAN  = 90;
const int NEUTRAL_TILT = 90;
const unsigned long TARGET_TIMEOUT = 1000;   // ما وصلت D => رجوع للمنتصف

const unsigned long ESPNOW_COOLDOWN    = 300;   // كل 0.3 ثانية إنذار أثناء التتبع
const unsigned long HELLO_INTERVAL     = 500;
const unsigned long HEARTBEAT_INTERVAL = 2000;

// يجب أن يكون مطابقاً تماماً في المستقبل
typedef struct __attribute__((packed)) {
    uint8_t  alertActive;   // 0 = handshake/heartbeat، 1 = إنذار
    int16_t  threatAngle;
    int16_t  pan;
    int16_t  tilt;
    uint32_t msgCounter;
} DroneAlertPacket;

Servo panServo;
Servo tiltServo;

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

void sendPacket(uint8_t active, int16_t angle, int16_t pan, int16_t tilt) {
    DroneAlertPacket pkt;
    pkt.alertActive = active;
    pkt.threatAngle = angle;
    pkt.pan         = pan;
    pkt.tilt        = tilt;
    pkt.msgCounter  = ++packetCounter;
    esp_now_send(receiverMacAddress, (uint8_t *)&pkt, sizeof(pkt));
}

void goNeutral() {
    panServo.write(NEUTRAL_PAN);
    tiltServo.write(NEUTRAL_TILT);
}

void handleLine(const char *s) {
    if (strcmp(s, "S") == 0) {
        goNeutral();
        if (targetActive) Serial.println("[TARGET] OFF (S)");
        targetActive = false;
        return;
    }

    int pan = 0, tilt = 0, threatAngle = 0;
    if (sscanf(s, "D,%d,%d,%d", &pan, &tilt, &threatAngle) == 3) {
        unsigned long now = millis();
        lastDTime = now;

        pan  = constrain(pan, 0, 180);
        tilt = constrain(tilt, 0, 180);

        if (!targetActive) {
            targetActive = true;
            Serial.println("[TARGET] ON");
        }

        // تتبع مباشر: السيرفو يأخذ نفس زاوية الإصبع
        panServo.write(pan);
        tiltServo.write(tilt);

        if (now - lastAlertTime >= ESPNOW_COOLDOWN) {
            lastAlertTime = now;
            sendPacket(1, (int16_t)threatAngle, (int16_t)pan, (int16_t)tilt);
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
        goNeutral();
        Serial.println("[TARGET] OFF (timeout)");
    }

    if (!linked) {
        if (now - lastHelloTime >= HELLO_INTERVAL) {
            lastHelloTime = now;
            sendPacket(0, 0, NEUTRAL_PAN, NEUTRAL_TILT);
        }
    } else if (now - lastHeartbeatTime >= HEARTBEAT_INTERVAL) {
        lastHeartbeatTime = now;
        sendPacket(0, 0, NEUTRAL_PAN, NEUTRAL_TILT);
    }

    if (linked != prevLinked) {
        prevLinked = linked;
        Serial.println(linked ? "[LINK] up" : "[LINK] down");
    }
}