#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <Preferences.h>
#include <WiFiClientSecure.h>
#include <WiFiUdp.h>
#include <HTTPClient.h>
#include <atomic>
#include <time.h>
#include "cJSON.h"
#include "mbedtls/base64.h"
#include "mbedtls/md.h"
#include <sys/time.h>
#include "csi_link.h"
#include "radar_link.h"
#if __has_include("secrets.h")
#include "secrets.h"
#else
#include "secrets.example.h"
#endif
#ifndef HAVEN_CSI_ONLY
#define HAVEN_CSI_ONLY 0
#endif

static SemaphoreHandle_t linkMutex;
static QueueHandle_t incomingCommands;
static String outgoing;
static uint32_t oldestByteMs;
static std::atomic<bool> linkOverflow{false};
static std::atomic<bool> diagnosticsReady{false};
static std::atomic<bool> collectWifiLogs{false};
static bool wifiFault = false;
static String pairedModule, pairedToken;
static String enrollmentSecret;
// A private, authenticated LAN clock lets a router without internet bootstrap TLS.
static bool syncLanClock() {
#if defined(HAVEN_TIME_HOST) && defined(HAVEN_TIME_KEY)
  if (WiFi.status() != WL_CONNECTED) return false;
  uint8_t key[32], nonce[8], request[11], reply[51];
  if (strlen(HAVEN_TIME_KEY) != 64) return false;
  for (int i=0;i<32;i++) {
    unsigned int byte=0;
    if (sscanf(HAVEN_TIME_KEY+2*i,"%2x",&byte)!=1) return false;
    key[i]=(uint8_t)byte;
  }
  memcpy(request,"HT1",3);
  for (int i=0;i<8;i++) nonce[i]=(uint8_t)esp_random();
  memcpy(request+3,nonce,8);
  WiFiUDP udp;
  if (!udp.begin(0)) return false;
  if (!udp.beginPacket(HAVEN_TIME_HOST,8767)) { udp.stop(); return false; }
  udp.write(request,sizeof(request));udp.endPacket();
  uint32_t started=millis();bool valid=false;
  while (millis()-started<800) {
    int size=udp.parsePacket();
    if (size==sizeof(reply) && udp.read(reply,sizeof(reply))==sizeof(reply) &&
        !memcmp(reply,request,sizeof(request))) {
      unsigned char mac[32];
      const mbedtls_md_info_t *md=mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
      if (md && mbedtls_md_hmac(md,key,sizeof(key),reply,19,mac)==0 &&
          !memcmp(mac,reply+19,sizeof(mac))) {
        uint64_t epoch=0;
        for (int i=11;i<19;i++) epoch=(epoch<<8)|reply[i];
        if (epoch>=1700000000ULL && epoch<4102444800ULL) {
          timeval tv={(time_t)epoch,0};settimeofday(&tv,nullptr);valid=true;
        }
      }
      break;
    }
    vTaskDelay(pdMS_TO_TICKS(20));
  }
  udp.stop();
  if (valid) ::Serial.println("[WIFI] Authenticated LAN clock ready");
  return valid;
#else
  return false;
#endif
}
static void requestEnrollment() {
  String endpoint = HAVEN_EXCHANGE_URL;
  endpoint.replace("/api/wifi/exchange", "/api/wifi/discover");
  String identity = WiFi.macAddress(); identity.replace(":", "");
  WiFiClientSecure tls; tls.setCACert(HAVEN_ROOT_CA);
  HTTPClient http; http.setConnectTimeout(5000); http.setTimeout(3000);
  if (!http.begin(tls, endpoint)) return;
  http.addHeader("Content-Type", "application/json");
  String body = "{\"deviceId\":\"" + identity + "\",\"requestSecret\":\"" + enrollmentSecret + "\"}";
  int enrollmentCode = http.POST(body);
  static uint32_t lastEnrollmentLog = 0;
  if (enrollmentCode != 200 && millis() - lastEnrollmentLog >= 5000) {
    char tlsError[160] = {};
    int tlsCode = tls.lastError(tlsError, sizeof(tlsError));
    ::Serial.printf("[WIFI] Enrollment HTTP status=%d tls=%d error=%s epoch=%lld\n", enrollmentCode, tlsCode, tlsError, (long long)time(nullptr));
    lastEnrollmentLog = millis();
  }
  if (enrollmentCode == 200) {
    cJSON* reply = cJSON_Parse(http.getString().c_str());
    cJSON* module = cJSON_GetObjectItemCaseSensitive(reply, "moduleId");
    cJSON* token = cJSON_GetObjectItemCaseSensitive(reply, "deviceToken");
    if (cJSON_IsString(module) && cJSON_IsString(token) && strlen(module->valuestring) <= 100 && strlen(token->valuestring) <= 100) {
      pairedModule = module->valuestring; pairedToken = token->valuestring;
      Preferences saved; saved.begin("haven", false);
      saved.putString("module", pairedModule); saved.putString("token", pairedToken);
      saved.putString("server", HAVEN_EXCHANGE_URL); saved.end();
      ::Serial.println("[WIFI] Device added to Haven");
    }
    cJSON_Delete(reply);
  }
  http.end();
}

// Tee diagnostics without making the acquisition loop wait for HTTPS or USB.
class DiagnosticStream : public Print {
 public:
  using Print::write;
  void begin(unsigned long baud) { ::Serial.begin(baud); }
  int available() { return ::Serial.available(); }
  int read() { return ::Serial.read(); }
  void flush() {} // HTTP delivery happens on a separate task.
  size_t write(uint8_t value) override {
    if (::Serial && ::Serial.availableForWrite() > 0) ::Serial.write(value);
    if (!collectWifiLogs || HAVEN_CSI_ONLY) return 1;
    if (linkMutex && xSemaphoreTake(linkMutex, pdMS_TO_TICKS(2))) {
      if (!outgoing.length()) oldestByteMs = millis();
      if (outgoing.length() < 32768) outgoing += (char)value;
      else linkOverflow = true;
      xSemaphoreGive(linkMutex);
    } else if (linkMutex) linkOverflow = true;
    return 1;
  }
};
static DiagnosticStream Diag;

static void wifiTask(void*) {
  WiFi.mode(WIFI_STA);
  WiFi.begin(HAVEN_WIFI_SSID, HAVEN_WIFI_PASSWORD);
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  char boot[33];
  snprintf(boot, sizeof(boot), "%08lx%08lx%08lx%08lx", (unsigned long)esp_random(), (unsigned long)esp_random(), (unsigned long)esp_random(), (unsigned long)esp_random());
  enrollmentSecret = boot;
  uint64_t sequence = 0;
  String pending;
  uint32_t pendingSince = 0;
  uint32_t lastExchangeMs = 0;
  uint32_t lastNetworkLog = 0;
  uint32_t lastClockAttempt = 0;
  for (;;) {
    if (millis() - lastNetworkLog >= 5000) {
      ::Serial.printf("[WIFI] status=%d ip=%s clock_ready=%u paired=%u\n",
        (int)WiFi.status(), WiFi.localIP().toString().c_str(),
        time(nullptr) >= 1700000000, !pairedToken.isEmpty());
      lastNetworkLog = millis();
    }
    if (collectWifiLogs && millis() - lastExchangeMs > 3000) linkOverflow = true;
    if (WiFi.status()==WL_CONNECTED && time(nullptr)<1700000000 && millis()-lastClockAttempt>=5000) {
      lastClockAttempt=millis();syncLanClock();
    }
    if (!diagnosticsReady || WiFi.status() != WL_CONNECTED || time(nullptr) < 1700000000) {
      vTaskDelay(pdMS_TO_TICKS(200)); continue;
    }
    if (pairedToken.isEmpty()) { requestEnrollment(); vTaskDelay(pdMS_TO_TICKS(2000)); continue; }
    startCsi();
    if (!collectWifiLogs) { lastExchangeMs = millis(); collectWifiLogs = true; }
    if (pending.isEmpty() && xSemaphoreTake(linkMutex, pdMS_TO_TICKS(20))) {
      pending = outgoing.substring(0, min((unsigned int)8192, outgoing.length()));
      pendingSince = outgoing.length() ? oldestByteMs : millis();
      outgoing.remove(0, pending.length());
      // Keep the oldest timestamp for any remainder; chunking cannot refresh it.
      xSemaphoreGive(linkMutex);
    }
    // Never upload stale logs as fresh observations. Reset Haven and restart ESP.
    if (pending.length() && millis() - pendingSince > 1000) {
      linkOverflow = true; vTaskDelay(pdMS_TO_TICKS(200)); continue;
    }
    unsigned char encoded[10925]; size_t encodedSize = 0;
    mbedtls_base64_encode(encoded, sizeof(encoded)-1, &encodedSize,
                          (const unsigned char*)pending.c_str(), pending.length());
    encoded[encodedSize] = 0;
    cJSON *packet = cJSON_CreateObject();
    cJSON_AddStringToObject(packet, "sensor_mode", HAVEN_CSI_ONLY ? "csi_only" : "radar");
    cJSON_AddStringToObject(packet, "moduleId", pairedModule.c_str());
    cJSON_AddStringToObject(packet, "boot", boot);
    cJSON_AddNumberToObject(packet, "sequence", (double)sequence);
    cJSON_AddNumberToObject(packet, "age_ms", pending.length() ? millis()-pendingSince : 0);
    cJSON_AddStringToObject(packet, "data", (const char*)encoded);
    cJSON_AddItemToObject(packet,"csi",csiBatch());
    cJSON_AddItemToObject(packet,"radar_uart",radarBatch());
    cJSON_AddNumberToObject(packet,"radar_dropped_bytes",radarDropped.load());
    cJSON_AddNumberToObject(packet,"csi_dropped",csiDropped.load());
    char *payload = cJSON_PrintUnformatted(packet);
    WiFiClientSecure tls;
    tls.setCACert(HAVEN_ROOT_CA);
    HTTPClient http;
    http.setConnectTimeout(1000); http.setTimeout(1000);
    int code = -1; String response;
    if (payload && http.begin(tls, HAVEN_EXCHANGE_URL)) {
      http.addHeader("Content-Type", "application/json");
      http.addHeader("Authorization", String("Bearer ") + pairedToken);
      code = http.POST((uint8_t*)payload, strlen(payload));
      if (code == 200) response = http.getString();
    }
    http.end(); free(payload); cJSON_Delete(packet);
    if (code == 401) {
      // A sensor or pairing may have been removed in Haven. Keep the TLS trust
      // and Wi-Fi configuration, but request explicit enrollment again rather
      // than retrying a revoked credential forever.
      Preferences saved;
      if (saved.begin("haven", false)) {
        saved.remove("module"); saved.remove("token"); saved.remove("server");
        saved.end();
      }
      pairedModule = ""; pairedToken = "";
      collectWifiLogs = false;
      pending = "";
      ::Serial.println("[WIFI] Pairing was rejected; awaiting Haven enrollment");
      vTaskDelay(pdMS_TO_TICKS(2000));
      continue;
    }
    if (code == 200) {
      cJSON *reply = cJSON_Parse(response.c_str());
      cJSON *ack = cJSON_GetObjectItemCaseSensitive(reply, "accepted");
      cJSON *commands = cJSON_GetObjectItemCaseSensitive(reply, "commands");
      if (cJSON_IsNumber(ack) && ack->valuedouble == (double)sequence && cJSON_IsArray(commands)) {
        cJSON *item;
        cJSON_ArrayForEach(item, commands) {
          if (cJSON_IsString(item) && strlen(item->valuestring) < 129) {
            char cmd[129] = {}; strlcpy(cmd, item->valuestring, sizeof(cmd));
            if (xQueueSend(incomingCommands, cmd, 0) != pdTRUE) linkOverflow = true;
          } else linkOverflow = true;
        }
        sequence++; pending = ""; lastExchangeMs = millis();
      }
      cJSON_Delete(reply);
    }
    vTaskDelay(pdMS_TO_TICKS(100));
  }
}

static void beginWifiLink() {
  linkMutex = xSemaphoreCreateMutex();
  incomingCommands = xQueueCreate(32, 129);
  if (!HAVEN_CSI_ONLY) radarQueue=xQueueCreate(8,sizeof(RadarChunk));
  if (!linkMutex || !incomingCommands || (!HAVEN_CSI_ONLY && !radarQueue)) { Diag.println("[ERROR] Wi-Fi queue allocation failed"); return; }
  pairedModule = HAVEN_MODULE_ID; pairedToken = HAVEN_DEVICE_TOKEN;
  if (pairedToken.isEmpty()) {
    Preferences saved; saved.begin("haven", true);
    if (saved.getString("server", "") == String(HAVEN_EXCHANGE_URL)) {
      pairedModule = saved.getString("module", ""); pairedToken = saved.getString("token", "");
    }
    saved.end();
  }
  if (!strlen(HAVEN_WIFI_SSID) || !strlen(HAVEN_ROOT_CA) || strncmp(HAVEN_EXCHANGE_URL, "https://", 8)) {
    Diag.println("[WIFI] Configure secrets.h before network use"); return;
  }
  if (xTaskCreatePinnedToCore(wifiTask, "haven_wifi", 24576, nullptr, 1, nullptr, 1) != pdPASS)
    Diag.println("[ERROR] Wi-Fi task allocation failed");
}
