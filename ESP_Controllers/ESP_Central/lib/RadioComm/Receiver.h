#pragma once
#include "Sender.h"  // لاستخدام نفس بنية DroneAlertPacket الموحدة 100%

class RadioReceiver {
public:
    bool begin();
    void update();
};