#include <Arduino.h>
// ESP32 المرسل (Sender) - يستقبل الرقم من بايثون عبر USB ويرسله بـ ESP-NOW
#include <WiFi.h>
#include <esp_now.h>

// ضع هنا MAC الخاص بالمستقبل (يظهر في السيريال مونيتور للمستقبل)
uint8_t receiverMAC[] = {0x70, 0x4B, 0xCA, 0x8E, 0xED, 0x70};

typedef struct {
  uint8_t type;   // 1 = handshake, 2 = رقم
  uint8_t value;
} Message;

volatile bool lastSendOk = false;
bool linked = false;

void handleSent(bool ok) { lastSendOk = ok; }

#if ESP_ARDUINO_VERSION_MAJOR >= 3
void onSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  handleSent(status == ESP_NOW_SEND_SUCCESS);
}
#else
void onSent(const uint8_t *mac, esp_now_send_status_t status) {
  handleSent(status == ESP_NOW_SEND_SUCCESS);
}
#endif

void sendMsg(uint8_t type, uint8_t value) {
  Message m = {type, value};
  esp_now_send(receiverMAC, (uint8_t *)&m, sizeof(m));
}

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);

  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed");
    return;
  }
  esp_now_register_send_cb(onSent);

  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, receiverMAC, 6);
  peer.channel = 0;
  peer.encrypt = false;
  esp_now_add_peer(&peer);
}

void loop() {
  // مرحلة الاتصال: أرسل handshake حتى ينجح
  if (!linked) {
    sendMsg(1, 0);
    delay(500);
    if (lastSendOk) linked = true;
    return;
  }

  // استقبال الرقم من بايثون وإرساله
  if (Serial.available()) {
    int n = Serial.parseInt();
    if (n >= 1 && n <= 5) sendMsg(2, (uint8_t)n);
  }
}
