#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_arduino_version.h>

// Structure must match the transmitter
typedef struct {
    int counter;
    float temperature;
    char message[32];
} DataPacket;

DataPacket receivedData;

volatile bool newData = false;

// Receive callback
#if ESP_ARDUINO_VERSION_MAJOR >= 3

void OnDataRecv(const esp_now_recv_info_t *info,
                const uint8_t *incomingData,
                int len) {

#else

void OnDataRecv(const uint8_t *mac,
                const uint8_t *incomingData,
                int len) {

#endif

    if (len == sizeof(DataPacket)) {
        memcpy(&receivedData, incomingData, sizeof(receivedData));
        newData = true;
    }
}

void setup() {

    Serial.begin(115200);

    WiFi.mode(WIFI_STA);

    Serial.println();
    Serial.println("ESP32 Receiver Started");

    Serial.print("Receiver MAC: ");
    Serial.println(WiFi.macAddress());

    // Initialize ESP-NOW
    if (esp_now_init() != ESP_OK) {
        Serial.println("ESP-NOW Initialization Failed");
        return;
    }

    // Register receive callback
    esp_now_register_recv_cb(OnDataRecv);

    Serial.println("ESP-NOW Initialized Successfully");
    Serial.println("Waiting for Data...");
}

void loop() {

    if (newData) {

        newData = false;

        Serial.println("----------------------");

        Serial.print("Counter: ");
        Serial.println(receivedData.counter);

        Serial.print("Temperature: ");
        Serial.println(receivedData.temperature);

        Serial.print("Message: ");
        Serial.println(receivedData.message);

        Serial.println("----------------------");
    }
}