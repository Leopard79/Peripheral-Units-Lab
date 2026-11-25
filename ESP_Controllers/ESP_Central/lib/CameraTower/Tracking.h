#pragma once
#include <Arduino.h>
#include <ESP32Servo.h>

class Tracking {
public:
    void begin(int panPin, int tiltPin);
    void track3Zones(int x);   // تحريك 3 اتجاهات (يسار / أمام / يمين) وتثبيت Tilt على 90
    void goNeutral();
    int getPanAngle() const { return _panAngle; }
    int getTiltAngle() const { return _tiltAngle; }

private:
    Servo _panServo;
    Servo _tiltServo;
    int _panAngle = 90;
    int _tiltAngle = 90;
};