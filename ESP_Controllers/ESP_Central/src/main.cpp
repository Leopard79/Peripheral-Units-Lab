#include <Arduino.h>
#include "Tracking.h"
#include "Stabilizer.h"
#include "Sender.h"
#include "Receiver.h"

// =========================================================
// اختر دور هذه اللوحة قبل الرفع:
// true  = ESP32 المرسل (متصل باللابتوب + محركات السيرفو)
// false = ESP32 المستقبل (شاشة إنذار الفرقة)
// =========================================================
#define IS_SENDER true

#if IS_SENDER
#define PAN_PIN  15
#define TILT_PIN 2

uint8_t receiverMac[] = {0x70, 0x4B, 0xCA, 0x8E, 0xED, 0x70};

Tracking tracker;
Stabilizer stabilizer;
RadioSender radio;

char lineBuf[32];
uint8_t lineLen = 0;
unsigned long lastAlertTime = 0;
unsigned long lastHeartbeatTime = 0;

void handleLine(const char *s) {
    if (strcmp(s, "S") == 0) {
        tracker.goNeutral();
        return;
    }

    int x = 0, y = 0, threatAngle = 0;
    if (sscanf(s, "D,%d,%d,%d", &x, &y, &threatAngle) == 3) {
        tracker.track3Zones(x);

        unsigned long now = millis();
        if (now - lastAlertTime >= 3000) {
            lastAlertTime = now;
            radio.sendPacket(1, (int16_t)threatAngle, (int16_t)tracker.getPanAngle(), (int16_t)tracker.getTiltAngle());
        }
    }
}

void setup() {
    Serial.begin(115200);
    tracker.begin(PAN_PIN, TILT_PIN);
    stabilizer.begin();
    radio.begin(receiverMac);
}

void loop() {
    while (Serial.available()) {
        char c = (char)Serial.read();
        if (c == '\n') {
            lineBuf[lineLen] = '\0';
            handleLine(lineBuf);
            lineLen = 0;
        } else if (c != '\r' && lineLen < sizeof(lineBuf) - 1) {
            lineBuf[lineLen++] = c;
        }
    }

    unsigned long now = millis();
    if (now - lastHeartbeatTime >= 2000) {
        lastHeartbeatTime = now;
        radio.sendPacket(0, 0, (int16_t)tracker.getPanAngle(), (int16_t)tracker.getTiltAngle());
    }
}

#else
RadioReceiver radio;

void setup() {
    Serial.begin(115200);
    delay(500);
    radio.begin();
}

void loop() {
    radio.update();
}
#endif