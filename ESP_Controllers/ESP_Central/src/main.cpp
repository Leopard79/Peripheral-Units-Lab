#include <Arduino.h>

#include "Stabilizer.h"
#include "Tracking.h"

#include "Sender.h"
#include "Receiver.h"


void setup() {
    Serial.begin(115200);
    
    initStabilizer();
    initRadio();
}

void loop() {
    updateStabilizer();
    checkRadioData();
}
