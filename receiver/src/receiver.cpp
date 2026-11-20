#include <Arduino.h>
// ESP32 المستقبل (Receiver)
#include <WiFi.h>
#include <esp_now.h>

typedef struct {
  uint8_t type;   // 1 = handshake, 2 = رقم
  uint8_t value;
} Message;

bool connected = false;

void handleData(const uint8_t *mac, const uint8_t *data, int len) {
  if (len != sizeof(Message)) return;
  Message m;
  memcpy(&m, data, sizeof(m));

  if (!connected) {
    connected = true;
    Serial.println("ESP-NOW connection with the sender established successfully");
  }
  if (m.type == 2) {
    Serial.print("Number received: ");
    Serial.println(m.value);
  }
}

#if ESP_ARDUINO_VERSION_MAJOR >= 3
void onReceive(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  handleData(info->src_addr, data, len);
}
#else
void onReceive(const uint8_t *mac, const uint8_t *data, int len) {
  handleData(mac, data, len);
}
#endif

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  delay(500);
  Serial.print("Receiver MAC: ");
  Serial.println(WiFi.macAddress());   // انسخه إلى كود المرسل

  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed");
    return;
  }
  esp_now_register_recv_cb(onReceive);
  Serial.println("Waiting for sender...");
}

void loop() {}
