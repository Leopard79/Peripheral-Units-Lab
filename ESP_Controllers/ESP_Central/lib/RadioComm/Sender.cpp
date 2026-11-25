#include "Sender.h"

static volatile bool g_linked = false;

#if ESP_ARDUINO_VERSION_MAJOR >= 3
static void onSentCb(const wifi_tx_info_t *info, esp_now_send_status_t status) {
    g_linked = (status == ESP_NOW_SEND_SUCCESS);
}
#else
static void onSentCb(const uint8_t *mac, esp_now_send_status_t status) {
    g_linked = (status == ESP_NOW_SEND_SUCCESS);
}
#endif

bool RadioSender::begin(const uint8_t mac[6]) {
    memcpy(_peerMac, mac, 6);
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();

    if (esp_now_init() != ESP_OK) return false;
    esp_now_register_send_cb(onSentCb);

    esp_now_peer_info_t peer = {};
    memcpy(peer.peer_addr, _peerMac, 6);
    peer.channel = 0;
    peer.encrypt = false;
    return (esp_now_add_peer(&peer) == ESP_OK);
}

void RadioSender::sendPacket(uint8_t active, int16_t angle, int16_t pan, int16_t tilt) {
    DroneAlertPacket pkt;
    pkt.alertActive = active;
    pkt.threatAngle = angle;
    pkt.pan         = pan;
    pkt.tilt        = tilt;
    pkt.msgCounter  = ++_counter;
    esp_now_send(_peerMac, (uint8_t *)&pkt, sizeof(pkt));
}

bool RadioSender::isLinked() const {
    return g_linked;
}