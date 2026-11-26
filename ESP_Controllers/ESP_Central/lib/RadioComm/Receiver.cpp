#include "Receiver.h"

static volatile bool g_hasNew = false;
static DroneAlertPacket g_latestPkt;
static volatile unsigned long g_lastRxTime = 0;
static bool g_linkUp = false;
static const unsigned long LINK_TIMEOUT = 5000;

static void handleIncoming(const uint8_t *data, int len) {
    if (len != sizeof(DroneAlertPacket)) return;
    memcpy((void *)&g_latestPkt, data, sizeof(DroneAlertPacket));
    g_lastRxTime = millis();
    g_hasNew = true;
}

#if ESP_ARDUINO_VERSION_MAJOR >= 3
static void onRecvCb(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
    handleIncoming(data, len);
}
#else
static void onRecvCb(const uint8_t *mac, const uint8_t *data, int len) {
    handleIncoming(data, len);
}
#endif

bool RadioReceiver::begin() {
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();
    Serial.print("[INFO] Receiver MAC: ");
    Serial.println(WiFi.macAddress());

    if (esp_now_init() != ESP_OK) return false;
    esp_now_register_recv_cb(onRecvCb);
    Serial.println("[READY] Waiting for drone alerts...");
    return true;
}

void RadioReceiver::update() {
    if (g_hasNew) {
        DroneAlertPacket pkt;
        memcpy(&pkt, (const void *)&g_latestPkt, sizeof(pkt));
        g_hasNew = false;

        if (!g_linkUp) {
            g_linkUp = true;
            Serial.println("[LINK] Connected to Sender");
        }
        if (pkt.alertActive == 1) {
            const char *dir = (pkt.pan > 100) ? "LEFT" : (pkt.pan < 80) ? "RIGHT" : "FRONT";
            Serial.print("[ALERT] Drone Detected! Dir: ");
            Serial.print(dir);
            Serial.print(" | Pan: "); Serial.print(pkt.pan);
            Serial.print(" | Tilt: "); Serial.print(pkt.tilt);
            Serial.print(" | Angle: "); Serial.print(pkt.threatAngle);
            Serial.print(" deg (Msg #"); Serial.print(pkt.msgCounter);
            Serial.println(")");
        }
    }

    if (g_linkUp && (millis() - g_lastRxTime > LINK_TIMEOUT)) {
        g_linkUp = false;
        Serial.println("[LINK] Lost");
    }
}