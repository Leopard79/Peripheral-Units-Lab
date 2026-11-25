#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_arduino_version.h>

typedef struct __attribute__((packed)) {
    uint8_t  alertActive;   // 0 = Heartbeat, 1 = Drone Alert
    int16_t  threatAngle;
    int16_t  pan;
    int16_t  tilt;
    uint32_t msgCounter;
} DroneAlertPacket;

class RadioSender {
public:
    bool begin(const uint8_t mac[6]);
    void sendPacket(uint8_t active, int16_t angle, int16_t pan, int16_t tilt);
    bool isLinked() const;

private:
    uint8_t _peerMac[6];
    uint32_t _counter = 0;
};