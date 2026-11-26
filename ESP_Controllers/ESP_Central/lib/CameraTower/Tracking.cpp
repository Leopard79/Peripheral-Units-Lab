#include "Tracking.h"

void Tracking::begin(int panPin, int tiltPin) {
    ESP32PWM::allocateTimer(0);
    ESP32PWM::allocateTimer(1);
    _panServo.setPeriodHertz(50);
    _tiltServo.setPeriodHertz(50);
    _panServo.attach(panPin, 500, 2400);
    _tiltServo.attach(tiltPin, 500, 2400);
    goNeutral();
}

void Tracking::goNeutral() {
    _panAngle = 90;
    _tiltAngle = 90;
    _panServo.write(_panAngle);
    _tiltServo.write(_tiltAngle);
}

void Tracking::track3Zones(int x) {
    // صورة 640x480: يسار (<210) -> 135° | أمام (210-430) -> 90° | يمين (>430) -> 45°
    // (اعكس 135 و 45 إذا تحرك المحرك بالاتجاه المعاكس)
    int targetPan = 90;
    if (x < 210) {
        targetPan = 135;
    } else if (x > 430) {
        targetPan = 45;
    }

    if (targetPan != _panAngle) {
        _panAngle = targetPan;
        _panServo.write(_panAngle);
    }

    // تثبيت الـ Tilt حالياً على 90
    _tiltAngle = 90;
    _tiltServo.write(_tiltAngle);
}