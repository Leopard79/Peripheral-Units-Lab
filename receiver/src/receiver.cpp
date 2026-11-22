#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_arduino_version.h>
//اول تعديل
typedef struct __attribute__((packed)) {
    uint8_t  alertActive;
    int16_t  threatAngle;
    uint32_t msgCounter;
} DroneAlertPacket;

volatile bool          hasNewPacket  = false;
volatile uint8_t       latestActive  = 0;
volatile int16_t       latestAngle   = 0;
volatile uint32_t      latestCounter = 0;
volatile unsigned long lastRxTime    = 0;

bool linkUp = false;
const unsigned long LINK_TIMEOUT = 5000;

void handleData(const uint8_t *data, int len) {
    if (len != sizeof(DroneAlertPacket)) return;
    DroneAlertPacket pkt;
    memcpy(&pkt, data, sizeof(pkt));
    latestActive  = pkt.alertActive;
    latestAngle   = pkt.threatAngle;
    latestCounter = pkt.msgCounter;
    lastRxTime    = millis();
    hasNewPacket  = true;
}

#if ESP_ARDUINO_VERSION_MAJOR >= 3
void onReceive(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
    handleData(data, len);
}
#else
void onReceive(const uint8_t *mac, const uint8_t *data, int len) {
    handleData(data, len);
}
#endif

void setup() {
    Serial.begin(115200);
    delay(500);
    WiFi.mode(WIFI_STA);
    Serial.print("[INFO] Receiver MAC: ");
    Serial.println(WiFi.macAddress());

    if (esp_now_init() != ESP_OK) {
        Serial.println("[ERROR] ESP-NOW init failed");
        return;
    }
    esp_now_register_recv_cb(onReceive);
    Serial.println("[READY] Waiting for sender...");
}

void loop() {
    if (hasNewPacket) {
        uint8_t  active = latestActive;
        int16_t  angle  = latestAngle;
        uint32_t count  = latestCounter;
        hasNewPacket = false;

        if (!linkUp) {
            linkUp = true;
            Serial.println("[LINK] connected to sender");
        }
        if (active == 1) {
            Serial.print("[ALERT] Drone Detected! Threat Angle: ");
            Serial.print(angle);
            Serial.print(" deg (Msg #");
            Serial.print(count);
            Serial.println(")");
        }
    }

    if (linkUp && (millis() - lastRxTime > LINK_TIMEOUT)) {
        linkUp = false;
        Serial.println("[LINK] lost");
    }
}