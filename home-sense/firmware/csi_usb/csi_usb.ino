// Router LLTF CSI over USB/UART at 115200. No radar GPIOs are driven.
#include <WiFi.h>
#include <atomic>
#include "esp_wifi.h"
#include "esp_system.h"
#include "esp_netif.h"
#include "ping/ping_sock.h"
#include "secrets.h"

struct Sample { uint32_t sequence, ms; int8_t rssi; uint8_t channel, invalid; int8_t iq[128]; };
static QueueHandle_t samples;
static uint8_t routerMac[6];
static std::atomic<uint32_t> sequence{0}, dropped{0};
static uint32_t lastSample = 0;
static char bootId[17];
static bool started = false;
static esp_ping_handle_t pingHandle;

static void receive(void*, wifi_csi_info_t* info) {
  if (!info || !info->buf || info->len != 128 || memcmp(info->mac, routerMac, 6)) return;
  uint32_t now = millis();
  if (now - lastSample < 50) return;
  lastSample = now;
  Sample s = {};
  s.sequence = ++sequence; s.ms = now; s.rssi = info->rx_ctrl.rssi;
  s.channel = info->rx_ctrl.channel; s.invalid = info->first_word_invalid;
  memcpy(s.iq, info->buf, 128);
  if (xQueueSend(samples, &s, 0) != pdTRUE) ++dropped;
}

static bool startCsi() {
  wifi_ap_record_t ap = {};
  if (esp_wifi_sta_get_ap_info(&ap) != ESP_OK) return false;
  memcpy(routerMac, ap.bssid, 6);
  wifi_csi_config_t config = {};
  config.lltf_en = true; config.htltf_en = false; config.stbc_htltf2_en = false;
  config.ltf_merge_en = true; config.channel_filter_en = true;
  if (esp_wifi_set_csi_config(&config) != ESP_OK ||
      esp_wifi_set_csi_rx_cb(receive, nullptr) != ESP_OK || esp_wifi_set_csi(true) != ESP_OK) return false;
  esp_wifi_set_ps(WIFI_PS_NONE);
  esp_netif_ip_info_t ip = {};
  if (esp_netif_get_ip_info(esp_netif_get_handle_from_ifkey("WIFI_STA_DEF"), &ip) != ESP_OK) return false;
  esp_ping_config_t ping = ESP_PING_DEFAULT_CONFIG();
  ping.count = 0; ping.interval_ms = 50; ping.data_size = 1;
  ping.target_addr.type = ESP_IPADDR_TYPE_V4; ping.target_addr.u_addr.ip4.addr = ip.gw.addr;
  esp_ping_callbacks_t callbacks = {};
  if (esp_ping_new_session(&ping, &callbacks, &pingHandle) != ESP_OK || esp_ping_start(pingHandle) != ESP_OK) return false;
  Serial.printf("{\"type\":\"ready\",\"firmware\":\"HAVEN_CSI_USB_v1\",\"boot\":\"%s\",\"channel\":%u,\"iq_bytes\":128,\"rate_limit_hz\":20}\n", bootId, ap.primary);
  return true;
}

void setup() {
  Serial.begin(115200);
  snprintf(bootId, sizeof(bootId), "%08lx%08lx", (unsigned long)esp_random(), (unsigned long)esp_random());
  samples = xQueueCreate(64, sizeof(Sample));
  if (!samples) { Serial.println("{\"type\":\"error\",\"reason\":\"queue_allocation\"}"); return; }
  WiFi.mode(WIFI_STA); WiFi.begin(CSI_WIFI_SSID, CSI_WIFI_PASSWORD);
}

void loop() {
  static uint32_t disconnectedAt = 0, lastStatus = 0;
  if (WiFi.status() != WL_CONNECTED) {
    if (!disconnectedAt) disconnectedAt = millis();
    if (started && millis() - disconnectedAt > 10000) ESP.restart();
  } else {
    disconnectedAt = 0;
    if (!started && samples) {
      started = startCsi();
      if (!started) { Serial.println("{\"type\":\"error\",\"reason\":\"csi_start\"}"); delay(1000); ESP.restart(); }
    }
  }
  Sample s;
  if (samples && xQueueReceive(samples, &s, pdMS_TO_TICKS(5)) == pdTRUE) {
    if (millis() - s.ms > 1000) { ++dropped; return; }
    // Hex keeps full signed IQ losslessly while fitting the 115200 UART budget.
    static const char hex[] = "0123456789abcdef";
    char iq[257];
    for (int i=0; i<128; ++i) { uint8_t b=(uint8_t)s.iq[i]; iq[2*i]=hex[b>>4]; iq[2*i+1]=hex[b&15]; }
    iq[256]=0;
    Serial.printf("{\"type\":\"csi\",\"boot\":\"%s\",\"sequence\":%lu,\"device_ms\":%lu,\"rssi\":%d,\"channel\":%u,\"first_word_invalid\":%s,\"iq_hex\":\"%s\"}\n",
      bootId, (unsigned long)s.sequence, (unsigned long)s.ms, s.rssi, s.channel, s.invalid ? "true" : "false", iq);
  }
  if (millis()-lastStatus >= 5000) {
    lastStatus=millis();
    Serial.printf("{\"type\":\"status\",\"wifi_connected\":%s,\"samples\":%lu,\"dropped\":%lu}\n",
      WiFi.status()==WL_CONNECTED ? "true" : "false", (unsigned long)sequence.load(), (unsigned long)dropped.load());
  }
}
