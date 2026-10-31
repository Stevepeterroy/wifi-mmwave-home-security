#pragma once
#include "esp_wifi.h"
#include "ping/ping_sock.h"
#include "esp_netif.h"
struct CsiSample { uint32_t sequence, ms; int8_t rssi; uint8_t channel, firstInvalid; uint16_t length; int8_t iq[128]; };
static QueueHandle_t csiQueue;
static uint8_t csiRouter[6];
static std::atomic<uint32_t> csiCount{0}, csiDropped{0};
static bool csiStarted=false;
static void receiveCsi(void*, wifi_csi_info_t* info) {
  if (!info || !info->buf || info->len != 128 || memcmp(info->mac,csiRouter,6)) return;
  static uint32_t lastSampleMs=0;
  uint32_t now=millis();if(now-lastSampleMs<50)return;lastSampleMs=now;
  CsiSample sample={};sample.sequence=++csiCount;sample.ms=now;
  sample.rssi=info->rx_ctrl.rssi;sample.channel=info->rx_ctrl.channel;
  sample.firstInvalid=info->first_word_invalid;sample.length=info->len;
  memcpy(sample.iq,info->buf,128);
  if (xQueueSend(csiQueue,&sample,0)!=pdTRUE) ++csiDropped;
}
static void startCsi() {
  if (csiStarted || WiFi.status()!=WL_CONNECTED) return;
  wifi_ap_record_t ap={};if(esp_wifi_sta_get_ap_info(&ap)!=ESP_OK)return;
  csiQueue=xQueueCreate(64,sizeof(CsiSample));if(!csiQueue)return;
  memcpy(csiRouter,ap.bssid,6);
  wifi_csi_config_t config={};config.lltf_en=true;config.htltf_en=false;
  config.stbc_htltf2_en=false;config.ltf_merge_en=true;config.channel_filter_en=true;
  if(esp_wifi_set_csi_config(&config)!=ESP_OK || esp_wifi_set_csi_rx_cb(receiveCsi,nullptr)!=ESP_OK || esp_wifi_set_csi(true)!=ESP_OK)return;
  esp_wifi_set_ps(WIFI_PS_NONE);
  esp_ping_config_t ping=ESP_PING_DEFAULT_CONFIG();ping.count=0;ping.interval_ms=50;ping.data_size=1;
  esp_netif_ip_info_t ip={};esp_netif_get_ip_info(esp_netif_get_handle_from_ifkey("WIFI_STA_DEF"),&ip);
  ping.target_addr.type=ESP_IPADDR_TYPE_V4;ping.target_addr.u_addr.ip4.addr=ip.gw.addr;
  esp_ping_callbacks_t callbacks={};esp_ping_handle_t handle;
  if(esp_ping_new_session(&ping,&callbacks,&handle)==ESP_OK)esp_ping_start(handle);
  csiStarted=true;::Serial.println("[CSI] Router LLTF acquisition enabled, 20 Hz ping stimulus");
}
static cJSON* csiBatch() {
  cJSON* batch=cJSON_CreateArray();CsiSample sample;
  for(int n=0;n<16 && csiQueue && xQueueReceive(csiQueue,&sample,0)==pdTRUE;n++) {
    if(millis()-sample.ms>1000){++csiDropped;continue;}
    cJSON* item=cJSON_CreateObject();cJSON_AddNumberToObject(item,"sequence",sample.sequence);
    cJSON_AddNumberToObject(item,"device_ms",sample.ms);cJSON_AddNumberToObject(item,"age_ms",millis()-sample.ms);
    cJSON_AddNumberToObject(item,"rssi",sample.rssi);cJSON_AddNumberToObject(item,"channel",sample.channel);
    cJSON_AddBoolToObject(item,"first_word_invalid",sample.firstInvalid);
    cJSON* iq=cJSON_CreateArray();for(int i=0;i<128;i++)cJSON_AddItemToArray(iq,cJSON_CreateNumber(sample.iq[i]));
    cJSON_AddItemToObject(item,"iq",iq);cJSON_AddItemToArray(batch,item);
  }
  return batch;
}
